"""Repository list widget with table view."""

import asyncio
import re
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTableView,
    QHeaderView,
    QMenu,
    QLineEdit,
    QLabel,
    QAbstractItemView,
    QCheckBox,
    QStyledItemDelegate,
    QPushButton,
    QStyle,
)
from PyQt6.QtCore import (
    Qt,
    QAbstractTableModel,
    QModelIndex,
    QSortFilterProxyModel,
    pyqtSignal,
    QRect,
    QSize,
    QTimer,
    QThread,
)
from PyQt6.QtGui import QAction, QPainter, QColor, QBrush, QPen, QFont, QIcon

from ..models.repository import Repository

if TYPE_CHECKING:
    from ..services.openrouter_service import OpenRouterService
    from ..services.vector_store import VectorStore


class SemanticSearchWorker(QThread):
    """Worker thread for running semantic search in background."""

    results_ready = pyqtSignal(dict)  # full_name -> similarity_score
    error = pyqtSignal(str)

    def __init__(
        self,
        openrouter: "OpenRouterService",
        vector_store: "VectorStore",
        query_text: str,
    ):
        super().__init__()
        self.openrouter = openrouter
        self.vector_store = vector_store
        self.query_text = query_text

    def run(self):
        """Execute semantic search."""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                scores = loop.run_until_complete(self._search())
                self.results_ready.emit(scores)
            finally:
                loop.close()
        except Exception as e:
            self.error.emit(str(e))

    async def _search(self) -> dict[str, float]:
        """Run the embedding and vector search."""
        # Create embedding for query
        query_embedding = await self.openrouter.create_embedding(self.query_text)
        # Get semantic scores for all repos
        scores = self.vector_store.get_semantic_scores(query_embedding, max_results=500)
        return scores


def kebab_to_title(name: str) -> str:
    """Convert kebab-case or snake_case to Title Case."""
    # Replace hyphens and underscores with spaces
    readable = re.sub(r'[-_]', ' ', name)
    # Title case each word
    return readable.title()


class RepositoryTableView(QTableView):
    """Custom table view with consistent styling."""

    def __init__(self, parent=None):
        super().__init__(parent)
        # Use standard grid lines for clean layout
        self.setShowGrid(True)
        # Set uniform row heights
        self.verticalHeader().setDefaultSectionSize(36)


class VisibilityDelegate(QStyledItemDelegate):
    """Custom delegate to render visibility as colored pills."""

    def paint(self, painter: QPainter, option, index: QModelIndex):
        """Paint the visibility pill."""
        value = index.data(Qt.ItemDataRole.DisplayRole)
        if value not in ("Public", "Private"):
            super().paint(painter, option, index)
            return

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Colors
        if value == "Private":
            bg_color = QColor("#fef3c7")  # Amber/yellow background
            text_color = QColor("#92400e")  # Dark amber text
        else:
            bg_color = QColor("#d1fae5")  # Green background
            text_color = QColor("#065f46")  # Dark green text

        # Calculate pill dimensions
        text = value
        font = painter.font()
        font.setPointSize(11)
        painter.setFont(font)

        text_width = painter.fontMetrics().horizontalAdvance(text)
        pill_width = text_width + 20
        pill_height = 24

        # Center the pill in the cell
        x = option.rect.x() + (option.rect.width() - pill_width) // 2
        y = option.rect.y() + (option.rect.height() - pill_height) // 2

        pill_rect = QRect(x, y, pill_width, pill_height)

        # Draw pill background
        painter.setBrush(QBrush(bg_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(pill_rect, 10, 10)

        # Draw text
        painter.setPen(QPen(text_color))
        painter.drawText(pill_rect, Qt.AlignmentFlag.AlignCenter, text)

        painter.restore()

    def sizeHint(self, option, index: QModelIndex) -> QSize:
        return QSize(90, 36)


class OpenButtonDelegate(QStyledItemDelegate):
    """Custom delegate to render open folder button."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._click_callback = None

    def set_click_callback(self, callback):
        """Set callback for button clicks."""
        self._click_callback = callback

    def paint(self, painter: QPainter, option, index: QModelIndex):
        """Paint the open folder button."""
        repo = index.data(Qt.ItemDataRole.UserRole)
        if not repo or not repo.is_local:
            # Show nothing for non-local repos
            return

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Button dimensions
        btn_size = 24
        x = option.rect.x() + (option.rect.width() - btn_size) // 2
        y = option.rect.y() + (option.rect.height() - btn_size) // 2

        btn_rect = QRect(x, y, btn_size, btn_size)

        # Draw button background on hover
        if option.state & QStyle.StateFlag.State_MouseOver:
            painter.setBrush(QBrush(QColor("#e5e7eb")))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(btn_rect, 4, 4)

        # Draw folder icon
        folder_color = QColor("#007acc")
        painter.setPen(QPen(folder_color, 1.5))
        painter.setBrush(QBrush(folder_color.lighter(150)))

        # Folder body
        fx, fy = x + 4, y + 7
        fw, fh = 16, 11
        painter.drawRoundedRect(fx, fy, fw, fh, 2, 2)

        # Folder tab
        painter.setBrush(QBrush(folder_color.lighter(130)))
        from PyQt6.QtGui import QPolygon
        from PyQt6.QtCore import QPoint
        tab = QPolygon([
            QPoint(fx + 1, fy),
            QPoint(fx + 6, fy),
            QPoint(fx + 8, fy - 3),
            QPoint(fx + 1, fy - 3),
        ])
        painter.drawPolygon(tab)

        painter.restore()

    def sizeHint(self, option, index: QModelIndex) -> QSize:
        return QSize(60, 36)

    def editorEvent(self, event, model, option, index):
        """Handle click events."""
        from PyQt6.QtCore import QEvent
        if event.type() == QEvent.Type.MouseButtonRelease:
            repo = index.data(Qt.ItemDataRole.UserRole)
            if repo and repo.is_local and self._click_callback:
                self._click_callback(repo)
                return True
        return False


class RepositoryTableModel(QAbstractTableModel):
    """Table model for repositories."""

    COLUMNS = ["Name", "Visibility", "Created", "Open"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._repositories: list[Repository] = []

    def set_repositories(self, repos: list[Repository]):
        """Set the repository list."""
        self.beginResetModel()
        self._repositories = repos
        self.endResetModel()

    def get_repository(self, row: int) -> Optional[Repository]:
        """Get repository at row."""
        if 0 <= row < len(self._repositories):
            return self._repositories[row]
        return None

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._repositories)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self.COLUMNS)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        repo = self._repositories[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return kebab_to_title(repo.name)
            elif col == 1:
                return "Private" if repo.is_private else "Public"
            elif col == 2:
                return repo.created_at.strftime("%b %d")
            elif col == 3:
                return ""  # VS Code button column

        elif role == Qt.ItemDataRole.ToolTipRole:
            if col == 0:
                return f"{repo.full_name}\n{repo.html_url}"
            elif col == 3 and repo.is_local:
                return "Open in VS Code"

        elif role == Qt.ItemDataRole.UserRole:
            return repo

        # For sorting - use raw values
        elif role == Qt.ItemDataRole.UserRole + 1:
            if col == 0:
                return repo.name.lower()
            elif col == 1:
                return 1 if repo.is_private else 0
            elif col == 2:
                return repo.created_at.timestamp()

        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.COLUMNS[section]
        return None


class RepositoryFilterModel(QSortFilterProxyModel):
    """Filter proxy for repository search and visibility filtering with hybrid semantic search."""

    # Threshold for including semantic-only matches (no keyword match)
    SEMANTIC_THRESHOLD = 0.4

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.setSortRole(Qt.ItemDataRole.UserRole + 1)  # Use sort role for proper sorting
        self._filter_text = ""
        self._show_public = True
        self._show_private = True
        self._semantic_scores: dict[str, float] = {}  # full_name -> score
        self._use_semantic_sorting = False

    def set_filter_text(self, text: str):
        """Set the filter text."""
        self._filter_text = text.lower()
        self.invalidateFilter()

    def set_semantic_scores(self, scores: dict[str, float]):
        """Set semantic similarity scores from vector search."""
        self._semantic_scores = scores
        self._use_semantic_sorting = bool(scores) and bool(self._filter_text)
        self.invalidateFilter()
        # Re-sort if we have semantic scores
        if self._use_semantic_sorting:
            self.invalidate()

    def clear_semantic_scores(self):
        """Clear semantic scores (e.g., when query changes)."""
        self._semantic_scores = {}
        self._use_semantic_sorting = False

    def set_visibility_filter(self, show_public: bool, show_private: bool):
        """Set visibility filter using checkbox states."""
        self._show_public = show_public
        self._show_private = show_private
        self.invalidateFilter()

    def _get_keyword_match(self, repo: Repository) -> bool:
        """Check if repo matches keyword filter."""
        if not self._filter_text:
            return True
        searchable = f"{repo.name} {repo.description or ''} {' '.join(repo.topics)}".lower()
        return self._filter_text in searchable

    def _get_hybrid_score(self, repo: Repository) -> float:
        """
        Calculate hybrid score combining keyword and semantic matching.
        Score range: 0.0 to 1.0
        """
        semantic_score = self._semantic_scores.get(repo.full_name, 0.0)
        keyword_match = self._get_keyword_match(repo)

        if keyword_match and semantic_score > 0:
            # Both match: weighted combination (semantic 70%, keyword boost 30%)
            return semantic_score * 0.7 + 0.3
        elif keyword_match:
            # Keyword only: base score
            return 0.3
        elif semantic_score >= self.SEMANTIC_THRESHOLD:
            # Semantic only (above threshold): semantic score
            return semantic_score * 0.7
        else:
            # No match
            return 0.0

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        model = self.sourceModel()
        repo = model.get_repository(source_row)
        if not repo:
            return False

        # Check visibility filter
        if repo.is_private and not self._show_private:
            return False
        if not repo.is_private and not self._show_public:
            return False

        # If no filter text, show all
        if not self._filter_text:
            return True

        # Hybrid filtering: accept if keyword matches OR semantic score is high enough
        keyword_match = self._get_keyword_match(repo)
        if keyword_match:
            return True

        # Check semantic score if available
        if self._semantic_scores:
            semantic_score = self._semantic_scores.get(repo.full_name, 0.0)
            if semantic_score >= self.SEMANTIC_THRESHOLD:
                return True

        return False

    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:
        """Custom sorting - use hybrid scores when available, otherwise default sort."""
        # If we have semantic scores and a filter, sort by hybrid score
        if self._use_semantic_sorting and self._filter_text:
            left_repo = self.sourceModel().get_repository(left.row())
            right_repo = self.sourceModel().get_repository(right.row())
            if left_repo and right_repo:
                left_score = self._get_hybrid_score(left_repo)
                right_score = self._get_hybrid_score(right_repo)
                # Higher scores first (descending)
                return left_score > right_score

        # Default sorting
        left_data = self.sourceModel().data(left, Qt.ItemDataRole.UserRole + 1)
        right_data = self.sourceModel().data(right, Qt.ItemDataRole.UserRole + 1)

        if left_data is None or right_data is None:
            return super().lessThan(left, right)

        return left_data < right_data


class PaginationProxyModel(QSortFilterProxyModel):
    """Proxy model that handles pagination on top of filtered/sorted data."""

    PAGE_SIZE = 10
    page_changed = pyqtSignal(int, int)  # current_page (1-indexed), total_pages

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_page = 0

    def get_total_count(self) -> int:
        """Get total count of items from source."""
        return self.sourceModel().rowCount() if self.sourceModel() else 0

    def get_total_pages(self) -> int:
        """Get total number of pages."""
        total = self.get_total_count()
        if total == 0:
            return 1
        return (total + self.PAGE_SIZE - 1) // self.PAGE_SIZE

    def get_current_page(self) -> int:
        """Get current page (0-indexed)."""
        return self._current_page

    def set_page(self, page: int):
        """Set current page (0-indexed)."""
        total_pages = self.get_total_pages()
        new_page = max(0, min(page, total_pages - 1))
        if new_page != self._current_page:
            self._current_page = new_page
            self.invalidateFilter()
            self._emit_page_changed()

    def next_page(self):
        """Go to next page."""
        if self._current_page < self.get_total_pages() - 1:
            self.set_page(self._current_page + 1)

    def prev_page(self):
        """Go to previous page."""
        if self._current_page > 0:
            self.set_page(self._current_page - 1)

    def reset_page(self):
        """Reset to first page."""
        if self._current_page != 0:
            self._current_page = 0
            self.invalidateFilter()
            self._emit_page_changed()

    def _emit_page_changed(self):
        """Emit page changed signal."""
        self.page_changed.emit(self._current_page + 1, self.get_total_pages())

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        """Only accept rows within the current page bounds."""
        start_idx = self._current_page * self.PAGE_SIZE
        end_idx = start_idx + self.PAGE_SIZE
        return start_idx <= source_row < end_idx

    def get_visible_repos_with_dates(self) -> list[tuple[int, Repository, str]]:
        """Get list of (proxy_row, repo, date_str) for visible rows."""
        result = []
        for proxy_row in range(self.rowCount()):
            proxy_index = self.index(proxy_row, 0)
            source_index = self.mapToSource(proxy_index)
            # Get the repo from the filter model's source (the table model)
            filter_model = self.sourceModel()
            if filter_model:
                table_source_index = filter_model.mapToSource(source_index)
                table_model = filter_model.sourceModel()
                if table_model:
                    repo = table_model.get_repository(table_source_index.row())
                    if repo:
                        date_str = repo.created_at.strftime("%B %d, %Y")
                        result.append((proxy_row, repo, date_str))
        return result


class RepositoryListWidget(QWidget):
    """Widget displaying the repository list with search, pagination, and actions."""

    repository_selected = pyqtSignal(Repository)
    open_requested = pyqtSignal(Repository)
    claude_code_requested = pyqtSignal(Repository)
    delete_requested = pyqtSignal(Repository)
    view_github_requested = pyqtSignal(Repository)

    # Debounce delay for semantic search (milliseconds)
    SEMANTIC_SEARCH_DELAY = 500

    def __init__(self, parent=None):
        super().__init__(parent)

        # Services for semantic search (set via set_services)
        self._openrouter: Optional["OpenRouterService"] = None
        self._vector_store: Optional["VectorStore"] = None
        self._semantic_worker: Optional[SemanticSearchWorker] = None

        # Debounce timer for semantic search
        self._semantic_timer = QTimer(self)
        self._semantic_timer.setSingleShot(True)
        self._semantic_timer.timeout.connect(self._trigger_semantic_search)

        # Track current search query for semantic search
        self._pending_semantic_query = ""

        self._setup_ui()

    def _setup_ui(self):
        """Set up the widget UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Filter bar
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(12)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search repositories...")
        self.search_edit.textChanged.connect(self._on_search_changed)
        filter_layout.addWidget(self.search_edit)

        # Visibility filter checkboxes
        self.public_checkbox = QCheckBox("Public")
        self.public_checkbox.setChecked(True)
        self.public_checkbox.stateChanged.connect(self._on_visibility_changed)
        filter_layout.addWidget(self.public_checkbox)

        self.private_checkbox = QCheckBox("Private")
        self.private_checkbox.setChecked(True)
        self.private_checkbox.stateChanged.connect(self._on_visibility_changed)
        filter_layout.addWidget(self.private_checkbox)

        self.count_label = QLabel("0 repositories")
        filter_layout.addWidget(self.count_label)

        # Semantic search indicator (shows magnifying glass during async search)
        self.semantic_indicator = QLabel("")
        self.semantic_indicator.setStyleSheet("font-size: 16px;")
        self.semantic_indicator.setFixedWidth(24)
        filter_layout.addWidget(self.semantic_indicator)

        layout.addLayout(filter_layout)

        # Table view
        self.table_view = RepositoryTableView()
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table_view.setAlternatingRowColors(False)  # We handle row separation via delegates
        self.table_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self._show_context_menu)
        self.table_view.doubleClicked.connect(self._on_double_click)
        self.table_view.setMouseTracking(True)  # Enable hover for VS Code button
        self.table_view.verticalHeader().setVisible(False)

        # Set up models: TableModel -> FilterModel -> PaginationModel
        self.model = RepositoryTableModel(self)
        self.filter_model = RepositoryFilterModel(self)
        self.filter_model.setSourceModel(self.model)
        self.pagination_model = PaginationProxyModel(self)
        self.pagination_model.setSourceModel(self.filter_model)
        self.table_view.setModel(self.pagination_model)

        # Set up custom delegates
        self.visibility_delegate = VisibilityDelegate(self)
        self.table_view.setItemDelegateForColumn(1, self.visibility_delegate)

        self.open_delegate = OpenButtonDelegate(self)
        self.open_delegate.set_click_callback(lambda repo: self.open_requested.emit(repo))
        self.table_view.setItemDelegateForColumn(3, self.open_delegate)

        # Configure header - Name stretches, others fixed
        header = self.table_view.horizontalHeader()
        header.setStretchLastSection(False)  # Don't stretch last column
        header.setMinimumSectionSize(60)  # Minimum width for any column

        # Set resize modes - Name stretches to fill available space
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # Name - stretches
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)    # Visibility - fixed
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)    # Created date - fixed
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)    # Open button - fixed

        # Set fixed column widths for non-stretching columns
        header.resizeSection(1, 90)    # Visibility column
        header.resizeSection(2, 80)    # Created date column
        header.resizeSection(3, 60)    # Open column

        header.sectionClicked.connect(self._on_header_clicked)

        # Sort by created date (column 2) descending by default
        self.filter_model.sort(2, Qt.SortOrder.DescendingOrder)
        self._current_sort_column = 2
        self._current_sort_order = Qt.SortOrder.DescendingOrder

        layout.addWidget(self.table_view)

        # Pagination controls
        pagination_layout = QHBoxLayout()
        pagination_layout.setContentsMargins(0, 4, 0, 0)

        pagination_layout.addStretch()

        self.prev_btn = QPushButton("← Previous")
        self.prev_btn.setFixedWidth(90)
        self.prev_btn.clicked.connect(self._on_prev_page)
        pagination_layout.addWidget(self.prev_btn)

        self.page_label = QLabel("Page 1 of 1")
        self.page_label.setMinimumWidth(100)
        self.page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pagination_layout.addWidget(self.page_label)

        self.next_btn = QPushButton("Next →")
        self.next_btn.setFixedWidth(90)
        self.next_btn.clicked.connect(self._on_next_page)
        pagination_layout.addWidget(self.next_btn)

        pagination_layout.addStretch()

        layout.addLayout(pagination_layout)

        # Connect pagination signals
        self.pagination_model.page_changed.connect(self._on_page_changed)

        # Connect selection after model is set
        self.table_view.selectionModel().selectionChanged.connect(self._on_selection_changed)

        # Connect filter model changes to reset pagination
        self.filter_model.layoutChanged.connect(self._on_filter_changed)


    def _on_header_clicked(self, column: int):
        """Handle header click for sorting."""
        if column == self._current_sort_column:
            # Toggle sort order
            if self._current_sort_order == Qt.SortOrder.AscendingOrder:
                self._current_sort_order = Qt.SortOrder.DescendingOrder
            else:
                self._current_sort_order = Qt.SortOrder.AscendingOrder
        else:
            self._current_sort_column = column
            # Default to descending for date, ascending for others
            if column == 2:
                self._current_sort_order = Qt.SortOrder.DescendingOrder
            else:
                self._current_sort_order = Qt.SortOrder.AscendingOrder

        self.filter_model.sort(self._current_sort_column, self._current_sort_order)
        self.pagination_model.reset_page()

    def _on_filter_changed(self):
        """Handle filter model layout changes."""
        self.pagination_model.reset_page()
        self._update_count()
        self._update_pagination_buttons()

    def _on_prev_page(self):
        """Go to previous page."""
        self.pagination_model.prev_page()

    def _on_next_page(self):
        """Go to next page."""
        self.pagination_model.next_page()

    def _on_page_changed(self, current_page: int, total_pages: int):
        """Handle page change."""
        self.page_label.setText(f"Page {current_page} of {total_pages}")
        self._update_pagination_buttons()

    def _update_pagination_buttons(self):
        """Update pagination button states."""
        current = self.pagination_model.get_current_page()
        total = self.pagination_model.get_total_pages()
        self.prev_btn.setEnabled(current > 0)
        self.next_btn.setEnabled(current < total - 1)

    def _get_repo_from_pagination_index(self, pagination_index: QModelIndex) -> Optional[Repository]:
        """Get repository from a pagination proxy index."""
        if not pagination_index.isValid():
            return None
        filter_index = self.pagination_model.mapToSource(pagination_index)
        source_index = self.filter_model.mapToSource(filter_index)
        return self.model.get_repository(source_index.row())

    def set_repositories(self, repos: list[Repository]):
        """Update the repository list."""
        self.model.set_repositories(repos)
        # Re-apply sort after loading data
        self.filter_model.sort(self._current_sort_column, self._current_sort_order)
        self.pagination_model.reset_page()
        self._update_count()
        self._update_pagination_buttons()
        # Emit initial page state
        self.pagination_model._emit_page_changed()

    def set_default_view_mode(self, mode: str):
        """Set the default view mode (all, public, private)."""
        if mode == "public":
            self.public_checkbox.setChecked(True)
            self.private_checkbox.setChecked(False)
        elif mode == "private":
            self.public_checkbox.setChecked(False)
            self.private_checkbox.setChecked(True)
        else:  # "all"
            self.public_checkbox.setChecked(True)
            self.private_checkbox.setChecked(True)

    def _update_count(self):
        """Update the repository count label."""
        filtered = self.filter_model.rowCount()
        total = self.model.rowCount()
        if filtered == total:
            self.count_label.setText(f"{total} repositories")
        else:
            self.count_label.setText(f"{filtered} of {total} repositories")

    def _on_search_changed(self, text: str):
        """Handle search text change with semantic search."""
        # Clear previous state
        self.filter_model.clear_semantic_scores()
        self.semantic_indicator.setText("")

        # Cancel any pending semantic search
        self._semantic_timer.stop()
        if self._semantic_worker and self._semantic_worker.isRunning():
            self._semantic_worker.terminate()
            self._semantic_worker = None

        # Empty query - show all repos
        if not text:
            self.filter_model.set_filter_text("")
            self.pagination_model.reset_page()
            self._update_count()
            self._update_pagination_buttons()
            self.pagination_model._emit_page_changed()
            return

        # Set filter text immediately (for keyword matching while semantic loads)
        self.filter_model.set_filter_text(text)
        self.pagination_model.reset_page()
        self._update_count()
        self._update_pagination_buttons()
        self.pagination_model._emit_page_changed()

        # Use semantic search (with debounce) if available
        if self._can_semantic_search():
            self._pending_semantic_query = text
            self.semantic_indicator.setText("🔍")
            self._semantic_timer.start(self.SEMANTIC_SEARCH_DELAY)

    def _on_visibility_changed(self):
        """Handle visibility filter checkbox change."""
        show_public = self.public_checkbox.isChecked()
        show_private = self.private_checkbox.isChecked()
        self.filter_model.set_visibility_filter(show_public, show_private)
        self.pagination_model.reset_page()
        self._update_count()
        self._update_pagination_buttons()
        self.pagination_model._emit_page_changed()

    def _on_selection_changed(self, selected, deselected):
        """Handle selection change."""
        indexes = self.table_view.selectionModel().selectedRows()
        if indexes:
            repo = self._get_repo_from_pagination_index(indexes[0])
            if repo:
                self.repository_selected.emit(repo)

    def _on_double_click(self, index: QModelIndex):
        """Handle double click on row."""
        repo = self._get_repo_from_pagination_index(index)
        if repo and repo.is_local:
            self.open_requested.emit(repo)

    def _show_context_menu(self, position):
        """Show context menu for repository actions."""
        index = self.table_view.indexAt(position)
        if not index.isValid():
            return

        repo = self._get_repo_from_pagination_index(index)
        if not repo:
            return

        menu = QMenu(self)

        if repo.is_local:
            open_action = QAction("Open in VS Code", self)
            open_action.triggered.connect(lambda: self.open_requested.emit(repo))
            menu.addAction(open_action)

            claude_action = QAction("Open in Claude Code", self)
            claude_action.triggered.connect(lambda: self.claude_code_requested.emit(repo))
            menu.addAction(claude_action)

        github_action = QAction("View on GitHub", self)
        github_action.triggered.connect(lambda: self.view_github_requested.emit(repo))
        menu.addAction(github_action)

        menu.addSeparator()

        if repo.is_local:
            delete_action = QAction("Delete Local Copy", self)
            delete_action.triggered.connect(lambda: self.delete_requested.emit(repo))
            menu.addAction(delete_action)

        menu.exec(self.table_view.viewport().mapToGlobal(position))

    def get_selected_repository(self) -> Optional[Repository]:
        """Get the currently selected repository."""
        indexes = self.table_view.selectionModel().selectedRows()
        if indexes:
            return self._get_repo_from_pagination_index(indexes[0])
        return None

    def set_services(
        self,
        openrouter: "OpenRouterService",
        vector_store: "VectorStore",
    ):
        """Set services for semantic search functionality."""
        self._openrouter = openrouter
        self._vector_store = vector_store

    def _can_semantic_search(self) -> bool:
        """Check if semantic search is available."""
        return self._openrouter is not None and self._vector_store is not None

    def _trigger_semantic_search(self):
        """Start the semantic search worker (called after debounce delay)."""
        if not self._can_semantic_search():
            return

        query = self._pending_semantic_query
        if not query:
            return

        # Check if current search text still matches (user may have changed it)
        current_text = self.search_edit.text()
        if current_text != query:
            return

        self.semantic_indicator.setText("🔍")

        # Create and start worker
        self._semantic_worker = SemanticSearchWorker(
            self._openrouter,
            self._vector_store,
            query,
        )
        self._semantic_worker.results_ready.connect(self._on_semantic_results)
        self._semantic_worker.error.connect(self._on_semantic_error)
        self._semantic_worker.start()

    def _on_semantic_results(self, scores: dict[str, float]):
        """Handle semantic search results."""
        # Verify the query hasn't changed while searching
        current_text = self.search_edit.text()
        if current_text != self._pending_semantic_query:
            self.semantic_indicator.setText("")
            return

        # Apply semantic scores to filter model
        self.filter_model.set_semantic_scores(scores)
        self.pagination_model.reset_page()
        self._update_count()
        self._update_pagination_buttons()
        self.pagination_model._emit_page_changed()

        # Clear the indicator
        self.semantic_indicator.setText("")

    def _on_semantic_error(self, error: str):
        """Handle semantic search error."""
        # Silently fail - keyword search still works
        self.semantic_indicator.setText("")

