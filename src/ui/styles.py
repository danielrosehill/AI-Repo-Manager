"""QSS Styles for the application."""

MAIN_STYLESHEET = """
QMainWindow {
    background-color: #ffffff;
}

QTableView {
    font-size: 12pt;
    background-color: #ffffff;
    border: none;
    selection-background-color: #e8f4fd;
    selection-color: #1f2937;
}

QTableView::item {
    padding: 8px 12px;
    border: none;
}

QTableView::item:selected {
    background-color: #e8f4fd;
}

QHeaderView::section {
    font-size: 11pt;
    font-weight: 500;
    padding: 8px 12px;
    background-color: #fafafa;
    border: none;
    border-bottom: 1px solid #e5e7eb;
    color: #6b7280;
}

QLabel {
    font-size: 11pt;
    color: #374151;
}

QLineEdit {
    font-size: 11pt;
    padding: 8px 12px;
    border: 1px solid #d1d5db;
    border-radius: 6px;
    background-color: #ffffff;
}

QLineEdit:focus {
    border-color: #3b82f6;
    outline: none;
}

QCheckBox {
    font-size: 11pt;
    spacing: 6px;
    color: #374151;
}

QPushButton {
    font-size: 11pt;
    padding: 6px 12px;
    border: 1px solid #d1d5db;
    border-radius: 6px;
    background-color: #ffffff;
    color: #374151;
}

QPushButton:hover {
    background-color: #f9fafb;
    border-color: #9ca3af;
}

QPushButton:pressed {
    background-color: #f3f4f6;
}

QPushButton:disabled {
    background-color: #f3f4f6;
    color: #9ca3af;
}

QToolBar {
    background-color: #fafafa;
    border-bottom: 1px solid #e5e7eb;
    spacing: 8px;
    padding: 4px 8px;
}

QToolButton {
    font-size: 11pt;
    padding: 6px 12px;
    border: 1px solid transparent;
    border-radius: 6px;
    background-color: transparent;
}

QToolButton:hover {
    background-color: #f3f4f6;
    border-color: #d1d5db;
}

QStatusBar {
    background-color: #fafafa;
    border-top: 1px solid #e5e7eb;
    color: #6b7280;
    font-size: 10pt;
}

QProgressBar {
    border: 1px solid #d1d5db;
    border-radius: 4px;
    background-color: #f3f4f6;
    text-align: center;
}

QProgressBar::chunk {
    background-color: #3b82f6;
    border-radius: 3px;
}
"""
