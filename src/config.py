"""Configuration management for AI Repo Manager."""

import json
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class Config:
    """Application configuration."""

    # Paths
    repos_base_path: str = ""

    # API Keys
    github_pat: str = ""
    openrouter_key: str = ""

    # Model settings
    embedding_model: str = "google/gemini-embedding-001"
    chat_model: str = "google/gemini-2.5-flash"

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

            if "repos_base_path" in settings:
                self.config.repos_base_path = settings["repos_base_path"]
            if "github_pat" in settings:
                self.config.github_pat = settings["github_pat"]
            if "openrouter_key" in settings:
                self.config.openrouter_key = settings["openrouter_key"]
            if "embedding_model" in settings:
                self.config.embedding_model = settings["embedding_model"]
            if "chat_model" in settings:
                self.config.chat_model = settings["chat_model"]
            if "window_geometry" in settings:
                self.config.window_geometry = settings["window_geometry"]
        except (json.JSONDecodeError, IOError):
            pass

    def save(self):
        """Save settings to JSON file."""
        if not self._settings_file:
            self._settings_file = self.config.config_dir / "settings.json"

        settings = {
            "repos_base_path": self.config.repos_base_path,
            "github_pat": self.config.github_pat,
            "openrouter_key": self.config.openrouter_key,
            "embedding_model": self.config.embedding_model,
            "chat_model": self.config.chat_model,
            "window_geometry": self.config.window_geometry,
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
        return bool(
            self.config.github_pat
            and self.config.openrouter_key
            and self.config.repos_base_path
        )


# Global config manager instance
config_manager = ConfigManager()
