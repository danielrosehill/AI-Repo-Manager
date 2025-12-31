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

    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.config = config_manager.config

        self.setWindowTitle("Settings")
        self.setMinimumWidth(500)
        self.setModal(True)

        self._setup_ui()
        self._load_values()

    def _setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # Paths group
        paths_group = QGroupBox("Paths")
        paths_layout = QFormLayout(paths_group)

        self.repos_path_edit = QLineEdit()
        self.repos_path_edit.setPlaceholderText("/home/user/repos")
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_repos_path)

        path_layout = QHBoxLayout()
        path_layout.addWidget(self.repos_path_edit)
        path_layout.addWidget(browse_btn)
        paths_layout.addRow("Repository Base Path:", path_layout)

        layout.addWidget(paths_group)

        # API Keys group
        api_group = QGroupBox("API Keys")
        api_layout = QFormLayout(api_group)

        self.github_token_edit = QLineEdit()
        self.github_token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.github_token_edit.setPlaceholderText("ghp_...")
        api_layout.addRow("GitHub Token:", self.github_token_edit)

        self.openrouter_key_edit = QLineEdit()
        self.openrouter_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.openrouter_key_edit.setPlaceholderText("sk-or-...")
        api_layout.addRow("OpenRouter Key:", self.openrouter_key_edit)

        layout.addWidget(api_group)

        # Models group
        models_group = QGroupBox("Models")
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

        # View settings group
        view_group = QGroupBox("View Settings")
        view_layout = QFormLayout(view_group)

        self.default_view_combo = QComboBox()
        self.default_view_combo.addItem("All Repositories", "all")
        self.default_view_combo.addItem("Public Only", "public")
        self.default_view_combo.addItem("Private Only", "private")
        view_layout.addRow("Default View:", self.default_view_combo)

        layout.addWidget(view_group)

        # Test connection buttons
        test_layout = QHBoxLayout()

        test_github_btn = QPushButton("Test GitHub Connection")
        test_github_btn.clicked.connect(self._test_github)
        test_layout.addWidget(test_github_btn)

        test_openrouter_btn = QPushButton("Test OpenRouter Connection")
        test_openrouter_btn.clicked.connect(self._test_openrouter)
        test_layout.addWidget(test_openrouter_btn)

        layout.addLayout(test_layout)

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

    def _load_values(self):
        """Load current config values into the form."""
        self.repos_path_edit.setText(self.config.repos_base_path)
        self.github_token_edit.setText(self.config.github_pat)
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

    def _browse_repos_path(self):
        """Open directory picker for repos path."""
        path = QFileDialog.getExistingDirectory(
            self,
            "Select Repository Base Directory",
            self.repos_path_edit.text() or str(self.config.config_dir.parent),
        )
        if path:
            self.repos_path_edit.setText(path)

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
            success, message = asyncio.get_event_loop().run_until_complete(test())

            if success:
                QMessageBox.information(self, "Success", message)
            else:
                QMessageBox.warning(self, "Connection Failed", message)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Connection test failed: {e}")

    def _save(self):
        """Save settings and close dialog."""
        # Validate required fields
        if not self.repos_path_edit.text():
            QMessageBox.warning(self, "Warning", "Repository base path is required.")
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

        # Update all config including API keys
        self.config_manager.update(
            repos_base_path=self.repos_path_edit.text(),
            github_pat=self.github_token_edit.text(),
            openrouter_key=self.openrouter_key_edit.text(),
            embedding_model=embedding_model,
            chat_model=chat_model,
            default_view_mode=default_view_mode,
        )

        self.accept()
