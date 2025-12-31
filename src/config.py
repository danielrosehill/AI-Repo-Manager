"""Configuration management for AI Repo Manager."""

import json
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class Config:
    """Application configuration."""

    # Repository Base Path (default for file browsers)
    repository_base: str = ""  # Default directory for file browser dialogs

    # GitHub Paths
    repos_base_path: str = ""  # GitHub repos (primary)
    github_public_path: str = ""  # GitHub public repos
    github_private_path: str = ""  # GitHub private repos

    # Other Paths
    work_repos_path: str = ""
    forks_path: str = ""  # Forked repositories
    docs_path: str = ""  # Documentation repositories

    # Hugging Face Paths (two slots each for flexibility)
    hf_datasets_path: str = ""  # Datasets path 1
    hf_datasets_path_2: str = ""  # Datasets path 2
    hf_models_path: str = ""  # Models path 1
    hf_models_path_2: str = ""  # Models path 2
    hf_spaces_path: str = ""  # Spaces path 1
    hf_spaces_path_2: str = ""  # Spaces path 2

    # Custom Paths (list of additional directories to scan)
    custom_repo_paths: list = field(default_factory=list)

    # API Keys
    github_pat: str = ""
    openrouter_key: str = ""
    hf_token: str = ""

    # Model settings
    embedding_model: str = "google/gemini-embedding-001"
    chat_model: str = "google/gemini-2.5-flash"

    # View settings
    default_view_mode: str = "all"  # "all", "public", "private"

    # Window geometry (for persistence)
    window_geometry: dict = field(default_factory=dict)

    # App paths
    config_dir: Path = field(default_factory=lambda: Path.home() / ".config" / "ai-repo-manager")
    data_dir: Path = field(default_factory=lambda: Path.home() / ".local" / "share" / "ai-repo-manager")

    def __post_init__(self):
        """Ensure paths are Path objects."""
        if isinstance(self.config_dir, str):
            self.config_dir = Path(self.config_dir)
        if isinstance(self.data_dir, str):
            self.data_dir = Path(self.data_dir)


class ConfigManager:
    """Manages loading and saving configuration."""

    def __init__(self):
        self.config = Config()
        self._settings_file: Path | None = None

    def load(self) -> Config:
        """Load configuration from settings file."""
        # Ensure directories exist
        self.config.config_dir.mkdir(parents=True, exist_ok=True)
        self.config.data_dir.mkdir(parents=True, exist_ok=True)

        # Load settings file
        self._settings_file = self.config.config_dir / "settings.json"
        if self._settings_file.exists():
            self._load_settings_file()

        return self.config

    def _load_settings_file(self):
        """Load settings from JSON file."""
        try:
            with open(self._settings_file, "r") as f:
                settings = json.load(f)

            # Repository base path
            if "repository_base" in settings:
                self.config.repository_base = settings["repository_base"]

            # GitHub paths
            if "repos_base_path" in settings:
                self.config.repos_base_path = settings["repos_base_path"]
            if "github_public_path" in settings:
                self.config.github_public_path = settings["github_public_path"]
            if "github_private_path" in settings:
                self.config.github_private_path = settings["github_private_path"]

            # Other paths
            if "work_repos_path" in settings:
                self.config.work_repos_path = settings["work_repos_path"]
            if "forks_path" in settings:
                self.config.forks_path = settings["forks_path"]
            if "docs_path" in settings:
                self.config.docs_path = settings["docs_path"]

            # Hugging Face paths
            if "hf_datasets_path" in settings:
                self.config.hf_datasets_path = settings["hf_datasets_path"]
            if "hf_datasets_path_2" in settings:
                self.config.hf_datasets_path_2 = settings["hf_datasets_path_2"]
            if "hf_models_path" in settings:
                self.config.hf_models_path = settings["hf_models_path"]
            if "hf_models_path_2" in settings:
                self.config.hf_models_path_2 = settings["hf_models_path_2"]
            if "hf_spaces_path" in settings:
                self.config.hf_spaces_path = settings["hf_spaces_path"]
            if "hf_spaces_path_2" in settings:
                self.config.hf_spaces_path_2 = settings["hf_spaces_path_2"]

            # Custom paths
            if "custom_repo_paths" in settings:
                self.config.custom_repo_paths = settings["custom_repo_paths"]

            # API keys
            if "github_pat" in settings:
                self.config.github_pat = settings["github_pat"]
            if "openrouter_key" in settings:
                self.config.openrouter_key = settings["openrouter_key"]
            if "hf_token" in settings:
                self.config.hf_token = settings["hf_token"]

            # Model settings
            if "embedding_model" in settings:
                self.config.embedding_model = settings["embedding_model"]
            if "chat_model" in settings:
                self.config.chat_model = settings["chat_model"]

            # View settings
            if "window_geometry" in settings:
                self.config.window_geometry = settings["window_geometry"]
            if "default_view_mode" in settings:
                self.config.default_view_mode = settings["default_view_mode"]
        except (json.JSONDecodeError, IOError):
            pass

    def save(self):
        """Save settings to JSON file."""
        if not self._settings_file:
            self._settings_file = self.config.config_dir / "settings.json"

        settings = {
            # Repository base path
            "repository_base": self.config.repository_base,
            # GitHub paths
            "repos_base_path": self.config.repos_base_path,
            "github_public_path": self.config.github_public_path,
            "github_private_path": self.config.github_private_path,
            # Other paths
            "work_repos_path": self.config.work_repos_path,
            "forks_path": self.config.forks_path,
            "docs_path": self.config.docs_path,
            # Hugging Face paths
            "hf_datasets_path": self.config.hf_datasets_path,
            "hf_datasets_path_2": self.config.hf_datasets_path_2,
            "hf_models_path": self.config.hf_models_path,
            "hf_models_path_2": self.config.hf_models_path_2,
            "hf_spaces_path": self.config.hf_spaces_path,
            "hf_spaces_path_2": self.config.hf_spaces_path_2,
            # Custom paths
            "custom_repo_paths": self.config.custom_repo_paths,
            # API keys
            "github_pat": self.config.github_pat,
            "openrouter_key": self.config.openrouter_key,
            "hf_token": self.config.hf_token,
            # Model settings
            "embedding_model": self.config.embedding_model,
            "chat_model": self.config.chat_model,
            # View settings
            "window_geometry": self.config.window_geometry,
            "default_view_mode": self.config.default_view_mode,
        }

        self.config.config_dir.mkdir(parents=True, exist_ok=True)
        with open(self._settings_file, "w") as f:
            json.dump(settings, f, indent=2)

    def update(self, **kwargs):
        """Update configuration values."""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
        self.save()

    def is_configured(self) -> bool:
        """Check if minimum configuration is present."""
        # Check for at least one repository source
        has_github = bool(self.config.github_pat and (
            self.config.repos_base_path or
            self.config.github_public_path or
            self.config.github_private_path
        ))
        has_huggingface = bool(self.config.hf_token and (
            self.config.hf_datasets_path or
            self.config.hf_datasets_path_2 or
            self.config.hf_models_path or
            self.config.hf_models_path_2 or
            self.config.hf_spaces_path or
            self.config.hf_spaces_path_2
        ))
        has_work = bool(self.config.work_repos_path)
        has_forks = bool(self.config.forks_path)
        has_docs = bool(self.config.docs_path)
        has_custom = bool(self.config.custom_repo_paths)

        # Check for embedding capability
        has_openrouter = bool(self.config.openrouter_key)

        # Need at least one source AND embedding capability
        return has_openrouter and (has_github or has_huggingface or has_work or has_forks or has_docs or has_custom)

    def has_github_configured(self) -> bool:
        """Check if GitHub is configured."""
        return bool(self.config.github_pat and (
            self.config.repos_base_path or
            self.config.github_public_path or
            self.config.github_private_path
        ))

    def has_huggingface_configured(self) -> bool:
        """Check if Hugging Face is configured."""
        return bool(self.config.hf_token and (
            self.config.hf_datasets_path or
            self.config.hf_datasets_path_2 or
            self.config.hf_models_path or
            self.config.hf_models_path_2 or
            self.config.hf_spaces_path or
            self.config.hf_spaces_path_2
        ))

    def has_work_repos_configured(self) -> bool:
        """Check if work repos path is configured."""
        return bool(self.config.work_repos_path)

    def has_forks_configured(self) -> bool:
        """Check if forks path is configured."""
        return bool(self.config.forks_path)

    def has_docs_configured(self) -> bool:
        """Check if docs path is configured."""
        return bool(self.config.docs_path)

    def has_custom_paths_configured(self) -> bool:
        """Check if custom paths are configured."""
        return bool(self.config.custom_repo_paths)


# Global config manager instance
config_manager = ConfigManager()
