"""Main application window."""

import asyncio
import subprocess
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Optional


def _format_relative_time(dt: datetime) -> str:
    """Format datetime as relative time (today, yesterday, X days ago)."""
    now = datetime.now()
    # Compare dates only (ignore time)
    today = now.date()
    sync_date = dt.date()
    delta = (today - sync_date).days

    if delta == 0:
        return "today"
    elif delta == 1:
        return "yesterday"
    else:
        return f"{delta} days ago"

from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QToolBar,
    QStatusBar,
    QMessageBox,
    QProgressBar,
    QLabel,
    QMenu,
    QSystemTrayIcon,
    QApplication,
    QFrame,
)
from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QAction, QIcon, QColor

from .styles import MAIN_STYLESHEET
from .repo_list import RepositoryListWidget
from .settings_dialog import SettingsDialog
from .progress_dialog import ProgressDialog
from ..config import ConfigManager
from ..models.repository import Repository
from ..services.database import Database
from ..services.github_service import GitHubService
from ..services.openrouter_service import OpenRouterService
from ..services.vector_store import VectorStore


class ApiHealthCheckWorker(QThread):
    """Worker thread for checking API connection health."""

    # Signals: (service_name, is_connected, message)
    github_status = pyqtSignal(bool, str)
    huggingface_status = pyqtSignal(bool, str)

    def __init__(self, config: "Config"):
        super().__init__()
        self.config = config

    def run(self):
        """Check API connections."""
        # Check GitHub
        if self.config.github_pat:
            try:
                from ..services.github_service import GitHubService
                service = GitHubService(self.config.github_pat, self.config.repos_base_path or "")
                success, message = service.test_connection()
                self.github_status.emit(success, message)
            except Exception as e:
                self.github_status.emit(False, str(e))
        else:
            self.github_status.emit(False, "Not configured")

        # Check Hugging Face
        if self.config.hf_token:
            try:
                from ..services.huggingface_service import HuggingFaceService
                service = HuggingFaceService(self.config.hf_token)
                success, message = service.test_connection()
                self.huggingface_status.emit(success, message)
            except Exception as e:
                self.huggingface_status.emit(False, str(e))
        else:
            self.huggingface_status.emit(False, "Not configured")


class UpdateReposWorker(QThread):
    """Worker thread for updating repositories and embeddings from multiple sources."""

    progress = pyqtSignal(str, int, int)  # message, current, total
    stage_changed = pyqtSignal(int)  # stage number (1-indexed)
    all_stages_complete = pyqtSignal()
    finished = pyqtSignal(list, int, int)  # repos, total_synced, changed_count
    error = pyqtSignal(str)

    def __init__(
        self,
        config: "Config",
        openrouter_service: OpenRouterService,
        vector_store: VectorStore,
        database: Database,
    ):
        super().__init__()
        self.config = config
        self.openrouter = openrouter_service
        self.vector_store = vector_store
        self.database = database

    def run(self):
        """Execute the update pipeline."""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                repos, total, changed = loop.run_until_complete(self._update_repos())
                self.finished.emit(repos, total, changed)
            finally:
                loop.close()
        except Exception as e:
            self.error.emit(str(e))

    async def _update_repos(self) -> tuple[list[Repository], int, int]:
        """Update repositories with incremental sync from all sources."""
        total_repos = 0
        changed_repos = 0

        def progress_cb(msg, current, total):
            self.progress.emit(msg, current, total)

        # Stage 1: Sync from all configured sources
        self.stage_changed.emit(1)

        # 1a: GitHub - sync from all configured GitHub paths
        github_paths = [
            (self.config.repos_base_path, "github"),
            (self.config.github_public_path, "github"),
            (self.config.github_private_path, "github"),
        ]
        for path, source in github_paths:
            if self.config.github_pat and path:
                self.progress.emit(f"Syncing repositories from GitHub ({path})...", 0, 0)
                try:
                    github_service = GitHubService(
                        self.config.github_pat,
                        path,
                    )
                    gh_total, gh_changed = github_service.sync_repos_to_database(
                        self.database, progress_cb
                    )
                    total_repos += gh_total
                    changed_repos += gh_changed
                except Exception as e:
                    self.progress.emit(f"GitHub sync error: {e}", 0, 0)

        # 1b: Hugging Face - check all path slots
        if self.config.hf_token and (
            self.config.hf_datasets_path or self.config.hf_datasets_path_2 or
            self.config.hf_models_path or self.config.hf_models_path_2 or
            self.config.hf_spaces_path or self.config.hf_spaces_path_2
        ):
            self.progress.emit("Syncing repositories from Hugging Face...", 0, 0)
            try:
                from ..services.huggingface_service import HuggingFaceService

                hf_service = HuggingFaceService(
                    self.config.hf_token,
                    datasets_path=self.config.hf_datasets_path,
                    datasets_path_2=self.config.hf_datasets_path_2,
                    models_path=self.config.hf_models_path,
                    models_path_2=self.config.hf_models_path_2,
                    spaces_path=self.config.hf_spaces_path,
                    spaces_path_2=self.config.hf_spaces_path_2,
                )
                hf_total, hf_changed = hf_service.sync_repos_to_database(
                    self.database, progress_cb
                )
                total_repos += hf_total
                changed_repos += hf_changed
            except ImportError:
                self.progress.emit("Hugging Face: huggingface_hub not installed", 0, 0)
            except Exception as e:
                self.progress.emit(f"Hugging Face sync error: {e}", 0, 0)

        # 1c: Local repo scans (work, forks, docs)
        local_sources = [
            (self.config.work_repos_path, "work", "work repositories"),
            (self.config.forks_path, "forks", "forked repositories"),
            (self.config.docs_path, "docs", "documentation repositories"),
        ]
        for path, source_name, display_name in local_sources:
            if path:
                self.progress.emit(f"Scanning {display_name}...", 0, 0)
                try:
                    from ..services.huggingface_service import LocalRepoService

                    local_service = LocalRepoService(
                        path,
                        source_name=source_name
                    )
                    local_total, local_changed = local_service.sync_repos_to_database(
                        self.database, progress_cb
                    )
                    total_repos += local_total
                    changed_repos += local_changed
                except Exception as e:
                    self.progress.emit(f"{display_name.capitalize()} scan error: {e}", 0, 0)

        # Stage 2: Get repos that need embedding and fetch READMEs
        repos_to_embed = self.database.get_repos_needing_embedding()
        embed_count = len(repos_to_embed)

        self.stage_changed.emit(2)

        if embed_count > 0:
            self.progress.emit(f"Fetching READMEs for {embed_count} repositories...", 0, embed_count)

            # Fetch READMEs based on source
            readmes = {}

            # Group repos by source for efficient fetching
            github_repos = [r for r in repos_to_embed if r.source == "github"]
            hf_repos = [r for r in repos_to_embed if r.source == "huggingface"]
            local_repos = [r for r in repos_to_embed if r.source in ("work", "forks", "docs", "local")]

            # Fetch GitHub READMEs
            if github_repos and self.config.github_pat:
                def readme_progress(msg, current, total):
                    self.progress.emit(msg, current, total)

                try:
                    github_service = GitHubService(
                        self.config.github_pat,
                        self.config.repos_base_path,
                    )
                    gh_readmes = github_service.fetch_readmes_parallel(
                        github_repos, readme_progress, max_workers=8
                    )
                    readmes.update(gh_readmes)
                except Exception:
                    pass

            # Fetch HF READMEs
            if hf_repos and self.config.hf_token:
                try:
                    from ..services.huggingface_service import HuggingFaceService

                    hf_service = HuggingFaceService(
                        self.config.hf_token,
                        datasets_path=self.config.hf_datasets_path,
                        datasets_path_2=self.config.hf_datasets_path_2,
                        models_path=self.config.hf_models_path,
                        models_path_2=self.config.hf_models_path_2,
                        spaces_path=self.config.hf_spaces_path,
                        spaces_path_2=self.config.hf_spaces_path_2,
                    )
                    hf_readmes = hf_service.fetch_readmes_parallel(
                        hf_repos, readme_progress, max_workers=8
                    )
                    readmes.update(hf_readmes)
                except Exception:
                    pass

            # Fetch local READMEs
            if local_repos:
                try:
                    from ..services.huggingface_service import LocalRepoService

                    local_service = LocalRepoService("", source_name="local")
                    local_readmes = local_service.fetch_readmes_parallel(
                        local_repos, readme_progress, max_workers=8
                    )
                    readmes.update(local_readmes)
                except Exception:
                    pass

            # Update database with fetched READMEs
            for repo in repos_to_embed:
                if repo.full_name in readmes:
                    repo.readme_content = readmes[repo.full_name]
                    self.database.update_readme(repo.full_name, repo.readme_content)

            # Stage 3: Generate embeddings in batches
            self.stage_changed.emit(3)
            self.progress.emit("Generating embeddings...", 0, embed_count)

            batch_size = 10
            for i in range(0, embed_count, batch_size):
                batch = repos_to_embed[i:i + batch_size]
                texts = [r.to_embedding_text() for r in batch]

                try:
                    embeddings = await self.openrouter.create_embeddings_batch(texts)

                    # Store in vector store
                    self.vector_store.upsert_repositories_batch(batch, embeddings)

                    # Mark as embedded in database
                    self.database.mark_embedded_batch([r.full_name for r in batch])

                    self.progress.emit(
                        f"Embedded {min(i + batch_size, embed_count)}/{embed_count} repositories",
                        min(i + batch_size, embed_count),
                        embed_count,
                    )
                except Exception as e:
                    self.progress.emit(f"Warning: Failed to embed batch: {e}", i, embed_count)
        else:
            # No repos to embed, still go through stage 3 briefly
            self.stage_changed.emit(3)
            self.progress.emit("No repositories need embedding updates", 0, 0)

        # All stages complete
        self.all_stages_complete.emit()

        await self.openrouter.close()

        # Return all repos from database
        all_repos = self.database.get_all_repositories()
        return all_repos, total_repos, changed_repos


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        self.config_manager = config_manager
        self.config = config_manager.config

        self.database: Optional[Database] = None
        self.github_service: Optional[GitHubService] = None
        self.openrouter_service: Optional[OpenRouterService] = None
        self.vector_store: Optional[VectorStore] = None

        self.current_worker: Optional[UpdateReposWorker] = None
        self.health_check_worker: Optional[ApiHealthCheckWorker] = None
        self.progress_dialog: Optional[ProgressDialog] = None
        self.repositories: list[Repository] = []

        self._setup_ui()
        self._setup_services()
        self._restore_geometry()

        # Check for first-run experience
        self._check_first_run()

        # Run API health checks on startup (after a short delay to let UI settle)
        QTimer.singleShot(1000, self._check_api_health)

    def _check_first_run(self):
        """Check if this is the first run and show setup dialog."""
        if not self.config_manager.is_configured():
            # Delay showing the dialog until after the window is shown
            QTimer.singleShot(500, self._show_first_run_dialog)

    def _show_first_run_dialog(self):
        """Show the first-run configuration dialog."""
        QMessageBox.information(
            self,
            "Welcome to AI Repo Manager",
            "Welcome! It looks like this is your first time using AI Repo Manager.\n\n"
            "Please configure at least one repository source and your API keys "
            "in the Settings dialog to get started.",
        )
        self._show_settings()

    def _setup_ui(self):
        """Set up the main window UI."""
        self.setWindowTitle("AI Repo Manager")
        self.setMinimumSize(600, 450)  # Compact size for 10 repos per page
        self.setStyleSheet(MAIN_STYLESHEET)

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QHBoxLayout(central_widget)
        layout.setContentsMargins(8, 8, 8, 8)

        # Repository list
        self.repo_list = RepositoryListWidget()
        self.repo_list.open_requested.connect(self._open_repository)
        self.repo_list.open_file_explorer_requested.connect(self._open_in_file_explorer)
        self.repo_list.open_console_requested.connect(self._open_in_console)
        self.repo_list.claude_code_requested.connect(self._open_in_claude_code)
        self.repo_list.delete_requested.connect(self._delete_repository)
        self.repo_list.view_github_requested.connect(self._view_on_github)

        layout.addWidget(self.repo_list)

        # Toolbar
        self._setup_toolbar()

        # Status bar
        self._setup_status_bar()

        # System tray
        self._setup_system_tray()

    def _setup_system_tray(self):
        """Set up the system tray icon."""
        self.tray_icon = QSystemTrayIcon(self)

        # Use standard application icon or create a simple one
        icon = QIcon.fromTheme("folder-github", QIcon.fromTheme("folder"))
        if icon.isNull():
            # Fallback: use application icon
            icon = QApplication.instance().windowIcon()
        self.tray_icon.setIcon(icon)
        self.tray_icon.setToolTip("AI Repo Manager")

        # Create tray menu
        tray_menu = QMenu()

        show_action = QAction("Show AI Repo Manager", self)
        show_action.triggered.connect(self._show_from_tray)
        tray_menu.addAction(show_action)

        tray_menu.addSeparator()

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self._quit_from_tray)
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()

    def _show_from_tray(self):
        """Show window from system tray."""
        self.show()
        self.raise_()
        self.activateWindow()

    def _on_tray_activated(self, reason):
        """Handle tray icon activation (click)."""
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            # Single click - toggle visibility
            if self.isVisible():
                self.hide()
            else:
                self._show_from_tray()

    def _setup_toolbar(self):
        """Set up the toolbar."""
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        # Update repos action
        self.update_action = QAction("Update Repos", self)
        self.update_action.setToolTip("Sync repositories from all sources and update embeddings")
        self.update_action.triggered.connect(self._update_repos)
        toolbar.addAction(self.update_action)

        toolbar.addSeparator()

        # Settings action
        settings_action = QAction("Settings", self)
        settings_action.setToolTip("Configure application settings")
        settings_action.triggered.connect(self._show_settings)
        toolbar.addAction(settings_action)

    def _setup_status_bar(self):
        """Set up the status bar."""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        self.status_label = QLabel("Ready")
        self.status_bar.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(200)
        self.progress_bar.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)

        # API health indicators (permanent widgets on the right side)
        # Create a container for the health indicators
        health_container = QWidget()
        health_layout = QHBoxLayout(health_container)
        health_layout.setContentsMargins(0, 0, 0, 0)
        health_layout.setSpacing(12)

        # GitHub indicator
        self.github_indicator = QLabel("GitHub: ⏳")
        self.github_indicator.setToolTip("Checking GitHub connection...")
        self.github_indicator.setStyleSheet("color: #6b7280;")  # Gray while checking
        health_layout.addWidget(self.github_indicator)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        health_layout.addWidget(separator)

        # Hugging Face indicator
        self.hf_indicator = QLabel("HF: ⏳")
        self.hf_indicator.setToolTip("Checking Hugging Face connection...")
        self.hf_indicator.setStyleSheet("color: #6b7280;")  # Gray while checking
        health_layout.addWidget(self.hf_indicator)

        self.status_bar.addPermanentWidget(health_container)

    def _setup_services(self):
        """Initialize services based on configuration."""
        if not self.config_manager.is_configured():
            self.status_label.setText("Not configured - please open Settings")
            return

        try:
            # Initialize database
            self.database = Database(self.config.data_dir / "repositories.db")

            # Initialize GitHub service only if configured
            if self.config_manager.has_github_configured():
                self.github_service = GitHubService(
                    self.config.github_pat,
                    self.config.repos_base_path,
                )

            self.openrouter_service = OpenRouterService(
                self.config.openrouter_key,
                self.config.embedding_model,
                self.config.chat_model,
            )

            self.vector_store = VectorStore(
                self.config.data_dir / "chromadb"
            )

            # Set services on repo list for semantic search
            self.repo_list.set_services(self.openrouter_service, self.vector_store)

            # Apply default view mode from settings
            self.repo_list.set_default_view_mode(self.config.default_view_mode)

            # Load repositories from database
            self.repositories = self.database.get_all_repositories()
            if self.repositories:
                self.repo_list.set_repositories(self.repositories)
                last_sync = self.database.get_last_sync_time()
                if last_sync:
                    relative_time = _format_relative_time(last_sync)
                    self.status_label.setText(
                        f"Loaded {len(self.repositories)} repositories (last sync: {relative_time})"
                    )
                else:
                    self.status_label.setText(f"Loaded {len(self.repositories)} repositories")
            else:
                self.status_label.setText("Ready - click 'Update Repos' to sync")

        except Exception as e:
            self.status_label.setText(f"Error: {e}")

    def _restore_geometry(self):
        """Restore window geometry from config."""
        geo = self.config.window_geometry
        if geo:
            if "x" in geo and "y" in geo:
                self.move(geo["x"], geo["y"])
            if "width" in geo and "height" in geo:
                self.resize(geo["width"], geo["height"])

    def _check_api_health(self):
        """Run API health checks in background."""
        if self.health_check_worker and self.health_check_worker.isRunning():
            return

        self.health_check_worker = ApiHealthCheckWorker(self.config)
        self.health_check_worker.github_status.connect(self._on_github_health)
        self.health_check_worker.huggingface_status.connect(self._on_hf_health)
        self.health_check_worker.start()

    @pyqtSlot(bool, str)
    def _on_github_health(self, connected: bool, message: str):
        """Handle GitHub health check result."""
        if connected:
            self.github_indicator.setText("GitHub: ✓")
            self.github_indicator.setStyleSheet("color: #22c55e;")  # Green
            self.github_indicator.setToolTip(message)
        elif "Not configured" in message:
            self.github_indicator.setText("GitHub: —")
            self.github_indicator.setStyleSheet("color: #6b7280;")  # Gray
            self.github_indicator.setToolTip("GitHub not configured")
        else:
            self.github_indicator.setText("GitHub: ✗")
            self.github_indicator.setStyleSheet("color: #ef4444;")  # Red
            self.github_indicator.setToolTip(f"Connection failed: {message}")

    @pyqtSlot(bool, str)
    def _on_hf_health(self, connected: bool, message: str):
        """Handle Hugging Face health check result."""
        if connected:
            self.hf_indicator.setText("HF: ✓")
            self.hf_indicator.setStyleSheet("color: #22c55e;")  # Green
            self.hf_indicator.setToolTip(message)
        elif "Not configured" in message:
            self.hf_indicator.setText("HF: —")
            self.hf_indicator.setStyleSheet("color: #6b7280;")  # Gray
            self.hf_indicator.setToolTip("Hugging Face not configured")
        else:
            self.hf_indicator.setText("HF: ✗")
            self.hf_indicator.setStyleSheet("color: #ef4444;")  # Red
            self.hf_indicator.setToolTip(f"Connection failed: {message}")

    def closeEvent(self, event):
        """Minimize to tray on close, save geometry."""
        # Save geometry
        geo = {
            "x": self.x(),
            "y": self.y(),
            "width": self.width(),
            "height": self.height(),
        }
        self.config_manager.update(window_geometry=geo)

        # Check if we're really quitting (from tray menu)
        if getattr(self, '_really_quit', False):
            # Actually quit - cleanup
            if self.tray_icon:
                self.tray_icon.hide()
            if self.database:
                self.database.close()
            event.accept()
        else:
            # Minimize to tray instead of closing
            event.ignore()
            self.hide()

    def _quit_from_tray(self):
        """Quit the application from system tray."""
        self._really_quit = True
        self.close()

    def _show_settings(self):
        """Show the settings dialog."""
        dialog = SettingsDialog(
            self.config_manager,
            self,
            database=self.database,
            vector_store=self.vector_store,
        )
        if dialog.exec():
            # Reinitialize services with new config
            self._setup_services()
            # Re-check API health with new settings
            self._check_api_health()

    def _update_repos(self):
        """Start the repository update process."""
        if not self.config_manager.is_configured():
            QMessageBox.warning(
                self,
                "Not Configured",
                "Please configure the application in Settings first.",
            )
            return

        if self.current_worker and self.current_worker.isRunning():
            return

        # Reinitialize services to ensure fresh state
        self._setup_services()

        if not all([self.openrouter_service, self.vector_store, self.database]):
            QMessageBox.warning(self, "Error", "Failed to initialize services.")
            return

        # Disable update button
        self.update_action.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate

        # Create and show progress dialog
        self.progress_dialog = ProgressDialog(self)

        # Create and start worker with config for multi-source sync
        self.current_worker = UpdateReposWorker(
            self.config,
            OpenRouterService(
                self.config.openrouter_key,
                self.config.embedding_model,
                self.config.chat_model,
            ),
            self.vector_store,
            self.database,
        )
        self.current_worker.progress.connect(self._on_update_progress)
        self.current_worker.stage_changed.connect(self._on_stage_changed)
        self.current_worker.all_stages_complete.connect(self._on_all_stages_complete)
        self.current_worker.finished.connect(self._on_update_finished)
        self.current_worker.error.connect(self._on_update_error)
        self.current_worker.start()

        # Show dialog (non-blocking due to worker thread)
        self.progress_dialog.show()

    @pyqtSlot(str, int, int)
    def _on_update_progress(self, message: str, current: int, total: int):
        """Handle update progress."""
        self.status_label.setText(message)
        if total > 0:
            self.progress_bar.setRange(0, total)
            self.progress_bar.setValue(current)
        else:
            self.progress_bar.setRange(0, 0)

        # Update progress dialog if open
        if self.progress_dialog:
            self.progress_dialog.update_progress(message, current, total)

    @pyqtSlot(int)
    def _on_stage_changed(self, stage: int):
        """Handle stage change."""
        if self.progress_dialog:
            self.progress_dialog.set_stage(stage)

    @pyqtSlot()
    def _on_all_stages_complete(self):
        """Handle all stages complete."""
        if self.progress_dialog:
            self.progress_dialog.complete_all_stages()

    @pyqtSlot(list, int, int)
    def _on_update_finished(self, repos: list[Repository], total: int, changed: int):
        """Handle update completion."""
        self.repositories = repos
        self.repo_list.set_repositories(repos)
        if changed > 0:
            self.status_label.setText(f"Synced {total} repositories ({changed} updated)")
        else:
            self.status_label.setText(f"Synced {total} repositories (no changes)")
        self.progress_bar.setVisible(False)
        self.update_action.setEnabled(True)

        # Close progress dialog after a brief delay to show completion
        if self.progress_dialog:
            QTimer.singleShot(1500, self.progress_dialog.finish)

    @pyqtSlot(str)
    def _on_update_error(self, error: str):
        """Handle update error."""
        self.status_label.setText(f"Error: {error}")
        self.progress_bar.setVisible(False)
        self.update_action.setEnabled(True)

        # Close progress dialog
        if self.progress_dialog:
            self.progress_dialog.close()

        QMessageBox.critical(self, "Update Failed", f"Failed to update repositories:\n\n{error}")

    def _open_repository(self, repo: Repository):
        """Open repository in VS Code."""
        if not repo.is_local or not repo.local_path:
            QMessageBox.warning(
                self,
                "Not Local",
                f"Repository '{repo.name}' is not cloned locally.",
            )
            return

        try:
            subprocess.Popen(["code", repo.local_path])
            self.status_label.setText(f"Opened {repo.name} in VS Code")
        except FileNotFoundError:
            QMessageBox.warning(
                self,
                "VS Code Not Found",
                "Could not find 'code' command. Make sure VS Code is installed and in PATH.",
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open repository: {e}")

    def _open_in_file_explorer(self, repo: Repository):
        """Open repository in file explorer (Dolphin on KDE)."""
        if not repo.is_local or not repo.local_path:
            QMessageBox.warning(
                self,
                "Not Local",
                f"Repository '{repo.name}' is not cloned locally.",
            )
            return

        try:
            # Try Dolphin first (KDE), then fall back to xdg-open
            subprocess.Popen(["dolphin", repo.local_path])
            self.status_label.setText(f"Opened {repo.name} in file explorer")
        except FileNotFoundError:
            try:
                subprocess.Popen(["xdg-open", repo.local_path])
                self.status_label.setText(f"Opened {repo.name} in file explorer")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to open file explorer: {e}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open file explorer: {e}")

    def _open_in_console(self, repo: Repository):
        """Open repository in Konsole terminal."""
        if not repo.is_local or not repo.local_path:
            QMessageBox.warning(
                self,
                "Not Local",
                f"Repository '{repo.name}' is not cloned locally.",
            )
            return

        try:
            subprocess.Popen(["konsole", "--workdir", repo.local_path])
            self.status_label.setText(f"Opened {repo.name} in Konsole")
        except FileNotFoundError:
            QMessageBox.warning(
                self,
                "Terminal Not Found",
                "Could not find 'konsole'. Make sure Konsole is installed.",
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open terminal: {e}")

    def _open_in_claude_code(self, repo: Repository):
        """Open repository in Claude Code terminal."""
        if not repo.is_local or not repo.local_path:
            QMessageBox.warning(
                self,
                "Not Local",
                f"Repository '{repo.name}' is not cloned locally.",
            )
            return

        try:
            subprocess.Popen([
                "konsole",
                "--workdir", repo.local_path,
                "-e", "claude"
            ])
            self.status_label.setText(f"Opened {repo.name} in Claude Code")
        except FileNotFoundError:
            QMessageBox.warning(
                self,
                "Terminal Not Found",
                "Could not find 'konsole'. Make sure Konsole is installed.",
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open Claude Code: {e}")

    def _delete_repository(self, repo: Repository):
        """Delete local repository after confirmation."""
        if not repo.is_local or not repo.local_path:
            return

        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete the local copy of '{repo.name}'?\n\n"
            f"Path: {repo.local_path}\n\n"
            "This action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            # Use generic delete for local repos
            import shutil
            try:
                shutil.rmtree(repo.local_path)

                # Update database
                if self.database:
                    self.database.update_local_path(repo.full_name, None)

                # Remove from vector store
                if self.vector_store:
                    self.vector_store.delete_repository(repo.full_name)

                # Refresh from database
                self.repositories = self.database.get_all_repositories()
                self.repo_list.set_repositories(self.repositories)
                self.status_label.setText(f"Deleted local copy of {repo.name}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete {repo.name}: {e}")

    def _view_on_github(self, repo: Repository):
        """Open repository on GitHub/Hugging Face in browser."""
        if repo.html_url:
            webbrowser.open(repo.html_url)
