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
)
from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QAction, QIcon

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


class UpdateReposWorker(QThread):
    """Worker thread for updating repositories and embeddings."""

    progress = pyqtSignal(str, int, int)  # message, current, total
    stage_changed = pyqtSignal(int)  # stage number (1-indexed)
    all_stages_complete = pyqtSignal()
    finished = pyqtSignal(list, int, int)  # repos, total_synced, changed_count
    error = pyqtSignal(str)

    def __init__(
        self,
        github_service: GitHubService,
        openrouter_service: OpenRouterService,
        vector_store: VectorStore,
        database: Database,
    ):
        super().__init__()
        self.github = github_service
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
        """Update repositories with incremental sync."""

        # Stage 1: Sync repos from GitHub to database
        self.stage_changed.emit(1)
        self.progress.emit("Syncing repositories from GitHub...", 0, 0)

        def progress_cb(msg, current, total):
            self.progress.emit(msg, current, total)

        total_repos, changed_repos = self.github.sync_repos_to_database(
            self.database, progress_cb
        )

        # Stage 2: Get repos that need embedding and fetch READMEs
        repos_to_embed = self.database.get_repos_needing_embedding()
        embed_count = len(repos_to_embed)

        self.stage_changed.emit(2)

        if embed_count > 0:
            self.progress.emit(f"Fetching READMEs for {embed_count} repositories...", 0, embed_count)

            # Fetch READMEs in parallel
            def readme_progress(msg, current, total):
                self.progress.emit(msg, current, total)

            readmes = self.github.fetch_readmes_parallel(
                repos_to_embed, readme_progress, max_workers=8
            )

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
        self.progress_dialog: Optional[ProgressDialog] = None
        self.repositories: list[Repository] = []

        self._setup_ui()
        self._setup_services()
        self._restore_geometry()

    def _setup_ui(self):
        """Set up the main window UI."""
        self.setWindowTitle("AI Repo Manager")
        self.setMinimumSize(1200, 700)
        self.setStyleSheet(MAIN_STYLESHEET)

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QHBoxLayout(central_widget)
        layout.setContentsMargins(8, 8, 8, 8)

        # Repository list
        self.repo_list = RepositoryListWidget()
        self.repo_list.open_requested.connect(self._open_repository)
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
        self.update_action.setToolTip("Sync repositories from GitHub and update embeddings")
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

    def _setup_services(self):
        """Initialize services based on configuration."""
        if not self.config_manager.is_configured():
            self.status_label.setText("Not configured - please open Settings")
            return

        try:
            # Initialize database
            self.database = Database(self.config.data_dir / "repositories.db")

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
        dialog = SettingsDialog(self.config_manager, self)
        if dialog.exec():
            # Reinitialize services with new config
            self._setup_services()

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

        if not all([self.github_service, self.openrouter_service, self.vector_store, self.database]):
            QMessageBox.warning(self, "Error", "Failed to initialize services.")
            return

        # Disable update button
        self.update_action.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate

        # Create and show progress dialog
        self.progress_dialog = ProgressDialog(self)

        # Create and start worker
        self.current_worker = UpdateReposWorker(
            self.github_service,
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
            if self.github_service and self.github_service.delete_local_repo(repo):
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
            else:
                QMessageBox.critical(self, "Error", f"Failed to delete {repo.name}")

    def _view_on_github(self, repo: Repository):
        """Open repository on GitHub in browser."""
        if repo.html_url:
            webbrowser.open(repo.html_url)
