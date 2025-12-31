"""Settings dialog for configuring the application."""

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLineEdit,
    QComboBox,
    QPushButton,
    QLabel,
    QFileDialog,
    QMessageBox,
    QGroupBox,
    QScrollArea,
    QWidget,
    QTabWidget,
)
from PyQt6.QtCore import Qt

from ..config import ConfigManager
from ..model_display import (
    get_embedding_models,
    get_chat_models,
    get_display_name,
    get_model_id,
)


class SettingsDialog(QDialog):
    """Dialog for configuring application settings."""

    def __init__(self, config_manager: ConfigManager, parent=None, database=None, vector_store=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.config = config_manager.config
        self.database = database
        self.vector_store = vector_store

        self.setWindowTitle("Settings")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)
        self.setModal(True)

        self._setup_ui()
        self._load_values()

    def _setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Create tab widget for organized settings
        tab_widget = QTabWidget()
        layout.addWidget(tab_widget)

        # Sources tab
        sources_tab = self._create_sources_tab()
        tab_widget.addTab(sources_tab, "Repository Sources")

        # API Keys tab
        api_tab = self._create_api_tab()
        tab_widget.addTab(api_tab, "API Keys")

        # Models tab
        models_tab = self._create_models_tab()
        tab_widget.addTab(models_tab, "Models")

        # Maintenance tab
        maintenance_tab = self._create_maintenance_tab()
        tab_widget.addTab(maintenance_tab, "Maintenance")

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._save)
        button_layout.addWidget(save_btn)

        layout.addLayout(button_layout)

    def _create_sources_tab(self) -> QWidget:
        """Create the repository sources tab."""
        # Create scrollable area for many path fields
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)

        # Repository Base group
        base_group = QGroupBox("Repository Base")
        base_layout = QFormLayout(base_group)

        self.repository_base_edit = QLineEdit()
        self.repository_base_edit.setPlaceholderText("/home/user/repos")
        browse_base_btn = QPushButton("Browse...")
        browse_base_btn.clicked.connect(lambda: self._browse_path(self.repository_base_edit, "Repository Base", use_base=False))

        base_path_layout = QHBoxLayout()
        base_path_layout.addWidget(self.repository_base_edit)
        base_path_layout.addWidget(browse_base_btn)
        base_layout.addRow("Base Path:", base_path_layout)

        base_note = QLabel("Default starting directory for all file browsers below")
        base_note.setStyleSheet("color: gray; font-size: 10px;")
        base_layout.addRow("", base_note)

        layout.addWidget(base_group)

        # GitHub group
        github_group = QGroupBox("GitHub")
        github_layout = QFormLayout(github_group)

        # Primary GitHub path
        self.repos_path_edit = QLineEdit()
        self.repos_path_edit.setPlaceholderText("/home/user/repos/github")
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(lambda: self._browse_path(self.repos_path_edit, "GitHub Repos"))

        path_layout = QHBoxLayout()
        path_layout.addWidget(self.repos_path_edit)
        path_layout.addWidget(browse_btn)
        github_layout.addRow("GitHub Repos:", path_layout)

        # GitHub Public path
        self.github_public_edit = QLineEdit()
        self.github_public_edit.setPlaceholderText("/home/user/repos/github/public")
        browse_gh_public_btn = QPushButton("Browse...")
        browse_gh_public_btn.clicked.connect(lambda: self._browse_path(self.github_public_edit, "GitHub Public"))

        gh_public_layout = QHBoxLayout()
        gh_public_layout.addWidget(self.github_public_edit)
        gh_public_layout.addWidget(browse_gh_public_btn)
        github_layout.addRow("GitHub Public:", gh_public_layout)

        # GitHub Private path
        self.github_private_edit = QLineEdit()
        self.github_private_edit.setPlaceholderText("/home/user/repos/github/private")
        browse_gh_private_btn = QPushButton("Browse...")
        browse_gh_private_btn.clicked.connect(lambda: self._browse_path(self.github_private_edit, "GitHub Private"))

        gh_private_layout = QHBoxLayout()
        gh_private_layout.addWidget(self.github_private_edit)
        gh_private_layout.addWidget(browse_gh_private_btn)
        github_layout.addRow("GitHub Private:", gh_private_layout)

        layout.addWidget(github_group)

        # Other Repos group
        other_group = QGroupBox("Other Repositories")
        other_layout = QFormLayout(other_group)

        # Work repos
        self.work_repos_edit = QLineEdit()
        self.work_repos_edit.setPlaceholderText("/home/user/repos/work")
        browse_work_btn = QPushButton("Browse...")
        browse_work_btn.clicked.connect(lambda: self._browse_path(self.work_repos_edit, "Work Repos"))

        work_path_layout = QHBoxLayout()
        work_path_layout.addWidget(self.work_repos_edit)
        work_path_layout.addWidget(browse_work_btn)
        other_layout.addRow("Work Repos:", work_path_layout)

        # Forks path
        self.forks_edit = QLineEdit()
        self.forks_edit.setPlaceholderText("/home/user/repos/forks")
        browse_forks_btn = QPushButton("Browse...")
        browse_forks_btn.clicked.connect(lambda: self._browse_path(self.forks_edit, "Forks"))

        forks_layout = QHBoxLayout()
        forks_layout.addWidget(self.forks_edit)
        forks_layout.addWidget(browse_forks_btn)
        other_layout.addRow("Forks:", forks_layout)

        # Docs path
        self.docs_edit = QLineEdit()
        self.docs_edit.setPlaceholderText("/home/user/repos/documentation")
        browse_docs_btn = QPushButton("Browse...")
        browse_docs_btn.clicked.connect(lambda: self._browse_path(self.docs_edit, "Docs"))

        docs_layout = QHBoxLayout()
        docs_layout.addWidget(self.docs_edit)
        docs_layout.addWidget(browse_docs_btn)
        other_layout.addRow("Docs:", docs_layout)

        layout.addWidget(other_group)

        # Hugging Face group
        hf_group = QGroupBox("Hugging Face")
        hf_layout = QFormLayout(hf_group)

        # Datasets path 1
        self.hf_datasets_edit = QLineEdit()
        self.hf_datasets_edit.setPlaceholderText("/home/user/repos/hugging-face/datasets")
        browse_datasets_btn = QPushButton("Browse...")
        browse_datasets_btn.clicked.connect(lambda: self._browse_path(self.hf_datasets_edit, "HF Datasets 1"))

        datasets_layout = QHBoxLayout()
        datasets_layout.addWidget(self.hf_datasets_edit)
        datasets_layout.addWidget(browse_datasets_btn)
        hf_layout.addRow("Datasets 1:", datasets_layout)

        # Datasets path 2
        self.hf_datasets_edit_2 = QLineEdit()
        self.hf_datasets_edit_2.setPlaceholderText("/home/user/repos/hugging-face/datasets-2")
        browse_datasets_btn_2 = QPushButton("Browse...")
        browse_datasets_btn_2.clicked.connect(lambda: self._browse_path(self.hf_datasets_edit_2, "HF Datasets 2"))

        datasets_layout_2 = QHBoxLayout()
        datasets_layout_2.addWidget(self.hf_datasets_edit_2)
        datasets_layout_2.addWidget(browse_datasets_btn_2)
        hf_layout.addRow("Datasets 2:", datasets_layout_2)

        # Models path 1
        self.hf_models_edit = QLineEdit()
        self.hf_models_edit.setPlaceholderText("/home/user/repos/hugging-face/models")
        browse_models_btn = QPushButton("Browse...")
        browse_models_btn.clicked.connect(lambda: self._browse_path(self.hf_models_edit, "HF Models 1"))

        models_layout = QHBoxLayout()
        models_layout.addWidget(self.hf_models_edit)
        models_layout.addWidget(browse_models_btn)
        hf_layout.addRow("Models 1:", models_layout)

        # Models path 2
        self.hf_models_edit_2 = QLineEdit()
        self.hf_models_edit_2.setPlaceholderText("/home/user/repos/hugging-face/models-2")
        browse_models_btn_2 = QPushButton("Browse...")
        browse_models_btn_2.clicked.connect(lambda: self._browse_path(self.hf_models_edit_2, "HF Models 2"))

        models_layout_2 = QHBoxLayout()
        models_layout_2.addWidget(self.hf_models_edit_2)
        models_layout_2.addWidget(browse_models_btn_2)
        hf_layout.addRow("Models 2:", models_layout_2)

        # Spaces path 1
        self.hf_spaces_edit = QLineEdit()
        self.hf_spaces_edit.setPlaceholderText("/home/user/repos/hugging-face/spaces")
        browse_spaces_btn = QPushButton("Browse...")
        browse_spaces_btn.clicked.connect(lambda: self._browse_path(self.hf_spaces_edit, "HF Spaces 1"))

        spaces_layout = QHBoxLayout()
        spaces_layout.addWidget(self.hf_spaces_edit)
        spaces_layout.addWidget(browse_spaces_btn)
        hf_layout.addRow("Spaces 1:", spaces_layout)

        # Spaces path 2
        self.hf_spaces_edit_2 = QLineEdit()
        self.hf_spaces_edit_2.setPlaceholderText("/home/user/repos/hugging-face/spaces-2")
        browse_spaces_btn_2 = QPushButton("Browse...")
        browse_spaces_btn_2.clicked.connect(lambda: self._browse_path(self.hf_spaces_edit_2, "HF Spaces 2"))

        spaces_layout_2 = QHBoxLayout()
        spaces_layout_2.addWidget(self.hf_spaces_edit_2)
        spaces_layout_2.addWidget(browse_spaces_btn_2)
        hf_layout.addRow("Spaces 2:", spaces_layout_2)

        # Note about privacy inference
        privacy_note = QLabel("Note: Privacy is inferred from path names containing 'private'")
        privacy_note.setStyleSheet("color: gray; font-size: 10px;")
        hf_layout.addRow("", privacy_note)

        layout.addWidget(hf_group)

        # View settings group
        view_group = QGroupBox("View Settings")
        view_layout = QFormLayout(view_group)

        self.default_view_combo = QComboBox()
        self.default_view_combo.addItem("All Repositories", "all")
        self.default_view_combo.addItem("Public Only", "public")
        self.default_view_combo.addItem("Private Only", "private")
        view_layout.addRow("Default View:", self.default_view_combo)

        layout.addWidget(view_group)

        layout.addStretch()

        scroll.setWidget(tab)
        return scroll

    def _create_api_tab(self) -> QWidget:
        """Create the API keys tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)

        # GitHub API group
        github_api_group = QGroupBox("GitHub")
        github_api_layout = QFormLayout(github_api_group)

        self.github_token_edit = QLineEdit()
        self.github_token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.github_token_edit.setPlaceholderText("ghp_...")

        github_token_layout = QHBoxLayout()
        github_token_layout.addWidget(self.github_token_edit)

        test_github_btn = QPushButton("Test")
        test_github_btn.clicked.connect(self._test_github)
        github_token_layout.addWidget(test_github_btn)

        github_api_layout.addRow("GitHub Token:", github_token_layout)
        layout.addWidget(github_api_group)

        # Hugging Face API group
        hf_api_group = QGroupBox("Hugging Face")
        hf_api_layout = QFormLayout(hf_api_group)

        self.hf_token_edit = QLineEdit()
        self.hf_token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.hf_token_edit.setPlaceholderText("hf_...")

        hf_token_layout = QHBoxLayout()
        hf_token_layout.addWidget(self.hf_token_edit)

        test_hf_btn = QPushButton("Test")
        test_hf_btn.clicked.connect(self._test_huggingface)
        hf_token_layout.addWidget(test_hf_btn)

        hf_api_layout.addRow("HF Token:", hf_token_layout)
        layout.addWidget(hf_api_group)

        # OpenRouter API group
        openrouter_group = QGroupBox("OpenRouter (for embeddings)")
        openrouter_layout = QFormLayout(openrouter_group)

        self.openrouter_key_edit = QLineEdit()
        self.openrouter_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.openrouter_key_edit.setPlaceholderText("sk-or-...")

        openrouter_key_layout = QHBoxLayout()
        openrouter_key_layout.addWidget(self.openrouter_key_edit)

        test_openrouter_btn = QPushButton("Test")
        test_openrouter_btn.clicked.connect(self._test_openrouter)
        openrouter_key_layout.addWidget(test_openrouter_btn)

        openrouter_layout.addRow("OpenRouter Key:", openrouter_key_layout)
        layout.addWidget(openrouter_group)

        layout.addStretch()
        return tab

    def _create_models_tab(self) -> QWidget:
        """Create the models tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)

        models_group = QGroupBox("AI Models")
        models_layout = QFormLayout(models_group)

        self.embedding_model_combo = QComboBox()
        for model_id, display_name in get_embedding_models():
            self.embedding_model_combo.addItem(display_name, model_id)
        self.embedding_model_combo.setEditable(True)
        models_layout.addRow("Embedding Model:", self.embedding_model_combo)

        self.chat_model_combo = QComboBox()
        for model_id, display_name in get_chat_models():
            self.chat_model_combo.addItem(display_name, model_id)
        self.chat_model_combo.setEditable(True)
        models_layout.addRow("Chat Model:", self.chat_model_combo)

        layout.addWidget(models_group)

        layout.addStretch()
        return tab

    def _create_maintenance_tab(self) -> QWidget:
        """Create the maintenance tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)

        # Reindex group
        reindex_group = QGroupBox("Reindex Repositories")
        reindex_layout = QVBoxLayout(reindex_group)

        reindex_label = QLabel(
            "Force a complete re-indexing of all repositories. "
            "This will regenerate embeddings for all repos, which may take some time."
        )
        reindex_label.setWordWrap(True)
        reindex_layout.addWidget(reindex_label)

        reindex_btn = QPushButton("Force Re-index All Repositories")
        reindex_btn.clicked.connect(self._force_reindex)
        reindex_layout.addWidget(reindex_btn)

        layout.addWidget(reindex_group)

        # Clear data group
        clear_group = QGroupBox("Clear Data")
        clear_layout = QVBoxLayout(clear_group)

        clear_label = QLabel(
            "Clear all repository data and start fresh. "
            "This will delete all cached data including embeddings."
        )
        clear_label.setWordWrap(True)
        clear_layout.addWidget(clear_label)

        clear_btn = QPushButton("Clear All Data")
        clear_btn.setStyleSheet("background-color: #ff4444; color: white;")
        clear_btn.clicked.connect(self._clear_all_data)
        clear_layout.addWidget(clear_btn)

        layout.addWidget(clear_group)

        layout.addStretch()
        return tab

    def _load_values(self):
        """Load current config values into the form."""
        # Repository base
        self.repository_base_edit.setText(self.config.repository_base)

        # GitHub paths
        self.repos_path_edit.setText(self.config.repos_base_path)
        self.github_public_edit.setText(self.config.github_public_path)
        self.github_private_edit.setText(self.config.github_private_path)

        # Other repos
        self.work_repos_edit.setText(self.config.work_repos_path)
        self.forks_edit.setText(self.config.forks_path)
        self.docs_edit.setText(self.config.docs_path)

        # Hugging Face paths
        self.hf_datasets_edit.setText(self.config.hf_datasets_path)
        self.hf_datasets_edit_2.setText(self.config.hf_datasets_path_2)
        self.hf_models_edit.setText(self.config.hf_models_path)
        self.hf_models_edit_2.setText(self.config.hf_models_path_2)
        self.hf_spaces_edit.setText(self.config.hf_spaces_path)
        self.hf_spaces_edit_2.setText(self.config.hf_spaces_path_2)

        # API keys
        self.github_token_edit.setText(self.config.github_pat)
        self.hf_token_edit.setText(self.config.hf_token)
        self.openrouter_key_edit.setText(self.config.openrouter_key)

        # Set model combos - find by model ID stored in userData
        idx = self.embedding_model_combo.findData(self.config.embedding_model)
        if idx >= 0:
            self.embedding_model_combo.setCurrentIndex(idx)
        else:
            # Custom model - show the display name
            self.embedding_model_combo.setCurrentText(get_display_name(self.config.embedding_model))

        idx = self.chat_model_combo.findData(self.config.chat_model)
        if idx >= 0:
            self.chat_model_combo.setCurrentIndex(idx)
        else:
            # Custom model - show the display name
            self.chat_model_combo.setCurrentText(get_display_name(self.config.chat_model))

        # Set default view mode
        idx = self.default_view_combo.findData(self.config.default_view_mode)
        if idx >= 0:
            self.default_view_combo.setCurrentIndex(idx)

    def _browse_path(self, line_edit: QLineEdit, title: str, use_base: bool = True):
        """Open directory picker for a path.

        Args:
            line_edit: The line edit to update with the selected path
            title: Title for the dialog
            use_base: If True, use repository_base as default directory
        """
        # Determine starting directory
        if line_edit.text():
            start_dir = line_edit.text()
        elif use_base and self.repository_base_edit.text():
            start_dir = self.repository_base_edit.text()
        else:
            start_dir = str(self.config.config_dir.parent)

        path = QFileDialog.getExistingDirectory(
            self,
            f"Select {title} Directory",
            start_dir,
        )
        if path:
            line_edit.setText(path)

    def _browse_repos_path(self):
        """Open directory picker for repos path (legacy method)."""
        self._browse_path(self.repos_path_edit, "Repository Base")

    def _test_github(self):
        """Test GitHub API connection."""
        from ..services.github_service import GitHubService

        token = self.github_token_edit.text()
        if not token:
            QMessageBox.warning(self, "Warning", "Please enter a GitHub token first.")
            return

        try:
            service = GitHubService(token, self.repos_path_edit.text() or "/tmp")
            success, message = service.test_connection()

            if success:
                QMessageBox.information(self, "Success", message)
            else:
                QMessageBox.warning(self, "Connection Failed", message)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Connection test failed: {e}")

    def _test_huggingface(self):
        """Test Hugging Face API connection."""
        token = self.hf_token_edit.text()
        if not token:
            QMessageBox.warning(self, "Warning", "Please enter a Hugging Face token first.")
            return

        try:
            from ..services.huggingface_service import HuggingFaceService

            service = HuggingFaceService(
                token,
                datasets_path=self.hf_datasets_edit.text(),
                models_path=self.hf_models_edit.text(),
                spaces_path=self.hf_spaces_edit.text(),
            )
            success, message = service.test_connection()

            if success:
                QMessageBox.information(self, "Success", message)
            else:
                QMessageBox.warning(self, "Connection Failed", message)
        except ImportError:
            QMessageBox.warning(
                self,
                "Missing Dependency",
                "huggingface_hub is required for Hugging Face integration.\n\n"
                "Install it with: pip install huggingface_hub"
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Connection test failed: {e}")

    def _test_openrouter(self):
        """Test OpenRouter API connection."""
        import asyncio
        from ..services.openrouter_service import OpenRouterService

        key = self.openrouter_key_edit.text()
        if not key:
            QMessageBox.warning(self, "Warning", "Please enter an OpenRouter key first.")
            return

        async def test():
            service = OpenRouterService(key)
            try:
                result = await service.test_connection()
                return result
            finally:
                await service.close()

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                success, message = loop.run_until_complete(test())
            finally:
                loop.close()

            if success:
                QMessageBox.information(self, "Success", message)
            else:
                QMessageBox.warning(self, "Connection Failed", message)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Connection test failed: {e}")

    def _force_reindex(self):
        """Force re-indexing of all repositories."""
        reply = QMessageBox.question(
            self,
            "Confirm Re-index",
            "This will mark all repositories for re-embedding.\n\n"
            "The next 'Update Repos' will regenerate all embeddings.\n\n"
            "Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                if self.database:
                    self.database.clear_all_embeddings()
                    QMessageBox.information(
                        self,
                        "Success",
                        "All repositories marked for re-embedding.\n\n"
                        "Click 'Update Repos' to regenerate embeddings."
                    )
                else:
                    QMessageBox.warning(
                        self,
                        "Warning",
                        "Database not available. Save settings and try again from main window."
                    )
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to clear embeddings: {e}")

    def _clear_all_data(self):
        """Clear all repository data."""
        reply = QMessageBox.warning(
            self,
            "Confirm Clear All Data",
            "This will DELETE all repository data including:\n"
            "- All cached repository information\n"
            "- All generated embeddings\n"
            "- Search index data\n\n"
            "This cannot be undone!\n\n"
            "Are you sure you want to continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            # Second confirmation
            reply2 = QMessageBox.warning(
                self,
                "Final Confirmation",
                "Are you REALLY sure? All data will be permanently deleted.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )

            if reply2 == QMessageBox.StandardButton.Yes:
                try:
                    import shutil

                    # Clear database
                    db_path = self.config.data_dir / "repositories.db"
                    if db_path.exists():
                        db_path.unlink()

                    # Clear vector store
                    chroma_path = self.config.data_dir / "chromadb"
                    if chroma_path.exists():
                        shutil.rmtree(chroma_path)

                    QMessageBox.information(
                        self,
                        "Success",
                        "All data has been cleared.\n\n"
                        "The application will need to be restarted."
                    )

                    # Close dialog and signal restart needed
                    self.accept()

                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to clear data: {e}")

    def _save(self):
        """Save settings and close dialog."""
        # Check if at least one source is configured with required API key
        has_github = bool(self.github_token_edit.text() and (
            self.repos_path_edit.text() or
            self.github_public_edit.text() or
            self.github_private_edit.text()
        ))
        has_huggingface = bool(
            self.hf_token_edit.text() and (
                self.hf_datasets_edit.text() or self.hf_datasets_edit_2.text() or
                self.hf_models_edit.text() or self.hf_models_edit_2.text() or
                self.hf_spaces_edit.text() or self.hf_spaces_edit_2.text()
            )
        )
        has_work = bool(self.work_repos_edit.text())
        has_forks = bool(self.forks_edit.text())
        has_docs = bool(self.docs_edit.text())

        if not (has_github or has_huggingface or has_work or has_forks or has_docs):
            QMessageBox.warning(
                self,
                "Warning",
                "Please configure at least one repository source:\n\n"
                "- GitHub: Path + Token\n"
                "- Hugging Face: Path(s) + Token\n"
                "- Work Repos, Forks, or Docs: Path only"
            )
            return

        # Check for OpenRouter key (required for embeddings)
        if not self.openrouter_key_edit.text():
            QMessageBox.warning(
                self,
                "Warning",
                "OpenRouter API key is required for generating embeddings."
            )
            return

        # Get model IDs - use userData if available, else treat text as model ID
        embedding_model = self.embedding_model_combo.currentData()
        if embedding_model is None:
            # Custom entry - try to resolve display name to ID, or use as-is
            embedding_model = get_model_id(
                self.embedding_model_combo.currentText(), "embedding"
            )

        chat_model = self.chat_model_combo.currentData()
        if chat_model is None:
            # Custom entry - try to resolve display name to ID, or use as-is
            chat_model = get_model_id(
                self.chat_model_combo.currentText(), "chat"
            )

        # Get default view mode
        default_view_mode = self.default_view_combo.currentData() or "all"

        # Update all config
        self.config_manager.update(
            # Repository base
            repository_base=self.repository_base_edit.text(),
            # GitHub
            repos_base_path=self.repos_path_edit.text(),
            github_public_path=self.github_public_edit.text(),
            github_private_path=self.github_private_edit.text(),
            github_pat=self.github_token_edit.text(),
            # Other repos
            work_repos_path=self.work_repos_edit.text(),
            forks_path=self.forks_edit.text(),
            docs_path=self.docs_edit.text(),
            # Hugging Face
            hf_datasets_path=self.hf_datasets_edit.text(),
            hf_datasets_path_2=self.hf_datasets_edit_2.text(),
            hf_models_path=self.hf_models_edit.text(),
            hf_models_path_2=self.hf_models_edit_2.text(),
            hf_spaces_path=self.hf_spaces_edit.text(),
            hf_spaces_path_2=self.hf_spaces_edit_2.text(),
            hf_token=self.hf_token_edit.text(),
            # OpenRouter
            openrouter_key=self.openrouter_key_edit.text(),
            # Models
            embedding_model=embedding_model,
            chat_model=chat_model,
            # View
            default_view_mode=default_view_mode,
        )

        self.accept()
