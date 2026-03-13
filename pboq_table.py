from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView, QMenu
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction, QColor
import pboq_constants as const

class PBOQTable(QTableWidget):
    """Custom table widget for PBOQ viewing with context menus and specialized logic."""
    
    # Signals for communication with the main dialog
    linkRequested = pyqtSignal(int)      # dest_rowid
    clearRequested = pyqtSignal(int)     # dest_rowid
    cellUpdated = pyqtSignal(int, int, str) # rowid, col_idx, new_value
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setAlternatingRowColors(True)
        self.setWordWrap(False)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        
        # Fixed 24px row height (matching Excel default)
        self.verticalHeader().setMinimumSectionSize(24)
        self.verticalHeader().setDefaultSectionSize(24)
        self.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)

    def _show_context_menu(self, pos):
        """Shows a context menu for the Bill Amount column."""
        # This will need to know which column is "Bill Amount"
        # We can store that or let the parent handle it via signals
        # For now, let's keep it simple and just emit a signal with the clicked cell info
        item = self.itemAt(pos)
        if not item: return
        
        row = item.row()
        col = item.column()
        
        # We need the rowid which is stored in Column 0's UserRole
        rowid_item = self.item(row, 0)
        if not rowid_item: return
        rowid = rowid_item.data(Qt.ItemDataRole.UserRole)
        
        # Pass the context menu request to the parent to check if it's the right column
        # Or let the table know which column it's supposed to handle
        self.parent()._handle_context_menu(self, pos, row, col, rowid)

    def get_column_default_color(self, col_idx):
        if col_idx < 4: return const.COL_COLOR_BLUE
        if col_idx < 6: return const.COL_COLOR_YELLOW
        if col_idx < 8: return const.COL_COLOR_RED
        return None

    def apply_column_colors(self, num_display_cols):
        for r in range(self.rowCount()):
            for c in range(min(num_display_cols, self.columnCount())):
                color = self.get_column_default_color(c)
                if color:
                    item = self.item(r, c)
                    if not item:
                        item = QTableWidgetItem()
                        self.setItem(r, c, item)
                    item.setBackground(color)

    def set_row_hidden_by_text(self, search_text):
        for row in range(self.rowCount()):
            row_texts = []
            for col in range(self.columnCount()):
                item = self.item(row, col)
                if item:
                    row_texts.append(item.text().lower())
            
            full_row_text = " ".join(row_texts)
            self.setRowHidden(row, search_text not in full_row_text if search_text else False)

    def set_word_wrap_enabled(self, enabled):
        """Toggles word wrap and updates row heights accordingly."""
        self.setWordWrap(enabled)
        vh = self.verticalHeader()
        if enabled:
            # Allow rows to be resized by content
            vh.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
            self.resizeRowsToContents()
        else:
            # Revert to fixed 24px height
            vh.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
            vh.setDefaultSectionSize(24)
            for r in range(self.rowCount()):
                self.setRowHeight(r, 24)
