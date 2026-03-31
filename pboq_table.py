from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView, QMenu
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction, QColor
import pboq_constants as const

class PBOQTable(QTableWidget):
    """Custom table widget for PBOQ viewing with context menus and specialized logic."""
    
    # Signals for communication with the main dialog
    cellUpdated = pyqtSignal(int, int, str) # rowid, col_idx, new_value
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_dialog = parent
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
        """Shows a context menu for the clicked column."""
        # pos from customContextMenuRequested is already in viewport coordinates
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
        if self.main_dialog and hasattr(self.main_dialog, '_handle_context_menu'):
            self.main_dialog._handle_context_menu(self, pos, row, col, rowid)

    def get_column_default_color(self, col_idx):
        if col_idx < 4: return const.COL_COLOR_BLUE # Ref, Desc, Qty, Unit
        if col_idx < 6: return const.COL_COLOR_YELLOW # Bill Rate/Amt
        if col_idx < 8: return const.COL_COLOR_GREEN # Gross Rate/Code
        return const.COL_COLOR_PURPLE # Plug Rate/Code and others

    def get_role_color(self, role):
        if role in ['ref', 'desc', 'qty', 'unit']: return const.COL_COLOR_BLUE
        if role in ['bill_rate', 'bill_amount']: return const.COL_COLOR_YELLOW
        if role in ['rate', 'rate_code']: return const.COL_COLOR_GREEN
        if role in ['plug_rate', 'plug_code']: return const.COL_COLOR_PURPLE
        if role in ['prov_sum', 'prov_sum_code']: return const.COLOR_PROV_SUM
        if role in ['pc_sum', 'pc_sum_code']: return const.COL_COLOR_LIME
        if role in ['sub_package', 'sub_name', 'sub_rate', 'sub_markup', 'sub_category', 'sub_code']: return const.COL_COLOR_ORANGE
        return None

    def apply_column_colors(self, mappings, num_display_cols):
        """Applies identifying pastel colors based on column roles from mappings."""
        map_inv = {v: k for k, v in mappings.items() if v >= 0}
        for r in range(self.rowCount()):
            for c in range(min(num_display_cols, self.columnCount())):
                role = map_inv.get(c)
                color = self.get_role_color(role) if role else self.get_column_default_color(c)
                
                if color:
                    item = self.item(r, c)
                    if not item:
                        item = QTableWidgetItem()
                        self.setItem(r, c, item)
                    
                    # Don't overwrite special formatting (Orange/Lime/Yellow features)
                    existing_bg = item.background().color()
                    if existing_bg.isValid() and existing_bg.name().lower() not in ["#ffffff", "#000000", "#f5f7f9"]:
                        # If it's one of the other PASTEL colors, we CAN overwrite it (in case mapping changed)
                        is_pastel = existing_bg.name().lower() in [const.COL_COLOR_BLUE.name().lower(), 
                                                                    const.COL_COLOR_YELLOW.name().lower(), 
                                                                    const.COL_COLOR_RED.name().lower(),
                                                                    const.COL_COLOR_PURPLE.name().lower(),
                                                                    const.COL_COLOR_GREEN.name().lower(),
                                                                    const.COL_COLOR_ORANGE.name().lower(),
                                                                    const.COLOR_PROV_SUM.name().lower(),
                                                                    const.COL_COLOR_LIME.name().lower()]
                        if not is_pastel: continue # Keep feature colors (Orange, Lime, etc.)
                        
                        # Special Case: If this is the Bill Rate or Bill Amount column and it's already Green or Purple, 
                        # it means it's a linked rate. Preserve this color for visual consistency.
                        if role in ['bill_rate', 'bill_amount'] and existing_bg.name().lower() in [const.COL_COLOR_GREEN.name().lower(), 
                                                                               const.COL_COLOR_PURPLE.name().lower(),
                                                                               const.COL_COLOR_ORANGE.name().lower(),
                                                                               const.COLOR_PROV_SUM.name().lower()]:
                            continue

                        
                    item.setBackground(color)

    def apply_column_alignment(self, left_enabled, mappings):
        """Forces Left alignment for non-standard columns if enabled, otherwise reverts to Right."""
        map_inv = {v: k for k, v in mappings.items() if v >= 0}
        excludes = [mappings.get('ref', -1), mappings.get('desc', -1), mappings.get('qty', -1), mappings.get('unit', -1)]
        
        # 1. Update Cell Alignment
        for r in range(self.rowCount()):
            for c in range(self.columnCount()):
                item = self.item(r, c)
                if not item: continue
                
                if c in excludes:
                    # Keep default for these
                    role = map_inv.get(c)
                    if role == 'unit':
                        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    elif role == 'qty':
                        item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    else: # ref, desc
                        item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                else:
                    # Pricing columns
                    if left_enabled:
                        item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                    else:
                        item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        # 2. Update Header Alignment
        for c in range(self.columnCount()):
            item = self.horizontalHeaderItem(c)
            if not item: continue
            
            if c in excludes:
                role = map_inv.get(c)
                if role == 'unit':
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                elif role in ['ref', 'desc']:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                else:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            else:
                if left_enabled:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                else:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

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
