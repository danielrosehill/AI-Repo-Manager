"""Progress dialog for sync operations."""

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QFrame,
)
from PyQt6.QtCore import Qt, pyqtSignal


# Stage definitions
STAGES = [
    ("Repository Sync", "Syncing repositories from GitHub"),
    ("Copying READMEs", "Fetching README content"),
    ("Generating Embeddings", "Creating vector embeddings"),
]


class ProgressDialog(QDialog):
    """Modal dialog showing sync progress with cancel option."""

    cancel_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Syncing Repositories")
        self.setModal(True)
        self.setMinimumWidth(500)
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.CustomizeWindowHint |
            Qt.WindowType.WindowTitleHint
        )

        self._current_stage = 0
        self._total_stages = len(STAGES)
        self._stage_labels: list[QLabel] = []
        self._setup_ui()
        self._cancelled = False

    def _setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # Stage progress section
        stages_frame = QFrame()
        stages_frame.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border-radius: 8px;
                padding: 8px;
            }
        """)
        stages_layout = QVBoxLayout(stages_frame)
        stages_layout.setSpacing(8)
        stages_layout.setContentsMargins(16, 12, 16, 12)

        # Stage header
        header = QLabel("Sync Progress")
        header.setStyleSheet("font-weight: bold; font-size: 13px; color: #333;")
        stages_layout.addWidget(header)

        # Create stage labels
        for i, (stage_name, _) in enumerate(STAGES):
            stage_label = QLabel(f"○  Stage {i + 1}: {stage_name}")
            stage_label.setStyleSheet("color: #888; font-size: 12px;")
            stages_layout.addWidget(stage_label)
            self._stage_labels.append(stage_label)

        layout.addWidget(stages_frame)

        # Current task label
        self.status_label = QLabel("Preparing sync...")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("font-size: 12px; margin-top: 8px;")
        layout.addWidget(self.status_label)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(0)  # Indeterminate initially
        self.progress_bar.setTextVisible(True)
        layout.addWidget(self.progress_bar)

        # Progress details
        self.detail_label = QLabel("")
        self.detail_label.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(self.detail_label)

        # Cancel button
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self._on_cancel)
        button_layout.addWidget(self.cancel_btn)

        layout.addLayout(button_layout)

    def _on_cancel(self):
        """Handle cancel button click."""
        self._cancelled = True
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setText("Cancelling...")
        self.status_label.setText("Cancelling sync...")
        self.cancel_requested.emit()

    def is_cancelled(self) -> bool:
        """Check if cancel was requested."""
        return self._cancelled

    def set_total(self, total: int):
        """Set the total number of items."""
        self.progress_bar.setMaximum(total)

    def update_progress(self, message: str, current: int, total: int):
        """Update progress display."""
        self.status_label.setText(message)

        if total > 0:
            self.progress_bar.setMaximum(total)
            self.progress_bar.setValue(current)
            self.detail_label.setText(f"{current} of {total}")
        else:
            self.progress_bar.setMaximum(0)  # Indeterminate
            self.detail_label.setText("")

    def set_phase(self, phase: str):
        """Set the current phase label."""
        self.setWindowTitle(f"Syncing Repositories - {phase}")

    def set_stage(self, stage: int):
        """Set the current stage (1-indexed).

        Updates the visual display to show:
        - Completed stages with green checkmarks
        - Current stage with blue indicator
        - Pending stages with gray circles
        """
        self._current_stage = stage

        for i, label in enumerate(self._stage_labels):
            stage_num = i + 1
            stage_name = STAGES[i][0]

            if stage_num < stage:
                # Completed stage
                label.setText(f"✓  Stage {stage_num}: {stage_name}")
                label.setStyleSheet("color: #28a745; font-size: 12px; font-weight: bold;")
            elif stage_num == stage:
                # Current stage
                label.setText(f"●  Stage {stage_num} of {self._total_stages}: {stage_name}")
                label.setStyleSheet("color: #007bff; font-size: 12px; font-weight: bold;")
            else:
                # Pending stage
                label.setText(f"○  Stage {stage_num}: {stage_name}")
                label.setStyleSheet("color: #888; font-size: 12px;")

        self.setWindowTitle(f"Syncing Repositories - Stage {stage} of {self._total_stages}")

    def complete_all_stages(self):
        """Mark all stages as complete."""
        for i, label in enumerate(self._stage_labels):
            stage_num = i + 1
            stage_name = STAGES[i][0]
            label.setText(f"✓  Stage {stage_num}: {stage_name}")
            label.setStyleSheet("color: #28a745; font-size: 12px; font-weight: bold;")

        self.status_label.setText("All stages complete!")
        self.status_label.setStyleSheet("font-size: 12px; margin-top: 8px; color: #28a745; font-weight: bold;")
        self.setWindowTitle("Syncing Repositories - Complete")
        self.detail_label.setText("")
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(100)

    def finish(self):
        """Close the dialog on completion."""
        self.accept()
