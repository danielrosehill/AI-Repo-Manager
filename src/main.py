"""Entry point for AI Repo Manager application."""

import sys

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from .config import config_manager
from .ui.main_window import MainWindow


def main():
    """Main entry point."""
    # Enable high DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("AI Repo Manager")
    app.setOrganizationName("AI Repo Manager")

    # Load configuration from ~/.config/ai-repo-manager/settings.json
    config_manager.load()

    # Create and show main window
    window = MainWindow(config_manager)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
