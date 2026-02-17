from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, 
                             QTableWidgetItem, QHeaderView, QLabel, QLineEdit, QPushButton, QWidget, QMenu, QMessageBox)
from PyQt6.QtGui import QAction
from PyQt6.QtCore import Qt
from database import DatabaseManager
from rate_buildup_dialog import RateBuildUpDialog

class RateManagerDialog(QDialog):
    """Dialog for viewing and managing saved rates in construction_rates.db."""
    def __init__(self, main_window=None, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.setWindowTitle("Rate Database")
        self.setMinimumSize(850, 500)
        self.db_manager = DatabaseManager("construction_rates.db")
        self.is_loading = False
        
        self._init_ui()
        self.load_rates()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)

        # Header Section
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        main_label = QLabel("Historical Rates")
        main_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #2e7d32;")
        header_layout.addWidget(main_label)
        header_layout.addStretch()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by Rate Code or Description...")
        self.search_input.setFixedWidth(400)
        self.search_input.textChanged.connect(self.filter_rates)
        header_layout.addWidget(self.search_input)
        layout.addWidget(header_widget)

        # Table
        self.table = QTableWidget()
        headers = ["Rate Code", "Description", "Unit", "Base Currency", "Gross Rate", "Adj. Factor", "Date", "Notes"]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        
        # Responsive Header Sizing
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(True)
        
        self.table.setEditTriggers(QTableWidget.EditTrigger.AnyKeyPressed | 
                                   QTableWidget.EditTrigger.EditKeyPressed | 
                                   QTableWidget.EditTrigger.SelectedClicked)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setWordWrap(False)
        self.table.verticalHeader().setDefaultSectionSize(25)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setStyleSheet("QTableWidget { border: 1px solid #e0e0e0; border-radius: 4px; }")
        
        self.table.doubleClicked.connect(self.open_rate_buildup)
        self.table.itemChanged.connect(self.on_item_changed)
        
        # Context Menu
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        
        layout.addWidget(self.table)



    def load_rates(self):
        """Loads data from construction_rates.db into the table."""
        self.is_loading = True
        rates = self.db_manager.get_rates_data()
        self.table.setRowCount(0)
        
        for row_idx, row_data in enumerate(rates):
            self.table.insertRow(row_idx)
            # data_to_display starts from index 1 (skip internal ID)
            for col_idx, data in enumerate(row_data[1:]):
                # Row data indices (excluding lib-id at 0):
                # 0: rate_code, 1: project_name, 2: unit, 3: currency, 4: grand_total, 5: adj_factor, 6: date, 7: notes
                if col_idx == 4: # grand_total
                    display_text = f"{float(data):,.2f}" if data is not None else "0.00"
                elif col_idx == 5: # adjustment_factor
                    try:
                        val = float(data)
                        display_text = f"{val:.2f}" if val != 1.0 else "N/A"
                    except:
                        display_text = "N/A"
                else:
                    display_text = str(data) if data is not None else ""
                
                item = QTableWidgetItem(display_text)
                # Store the internal DB ID from row_data[0] in the first visible column's UserRole
                if col_idx == 0:
                    item.setData(Qt.ItemDataRole.UserRole, row_data[0])
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                
                if col_idx in [4, 5]: # Rate and Adj Factor
                    font = item.font()
                    font.setBold(True) if col_idx == 4 else None
                    item.setFont(font)
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                
                # Freeze all columns except Rate Code and Description
                if col_idx >= 2:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                
                self.table.setItem(row_idx, col_idx, item)
        
        # Initial fit for all columns
        for i in range(self.table.columnCount()):
            self.table.resizeColumnToContents(i)
            
        # Ensure description and notes had a bit of extra space to start
        current_desc_w = self.table.columnWidth(1)
        self.table.setColumnWidth(1, max(current_desc_w, 250))
        
        self.is_loading = False

    def open_rate_buildup(self, index):
        """Loads and shows the build-up for the selected rate."""
        row = index.row()
        db_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        
        if db_id:
            from database import DatabaseManager
            rates_db = DatabaseManager("construction_rates.db")
            estimate_obj = rates_db.load_estimate_details(db_id)
            if estimate_obj and self.main_window:
                self.main_window.open_rate_buildup_window(estimate_obj)
            else:
                dialog = RateBuildUpDialog(estimate_obj, main_window=self.main_window, parent=self)
                dialog.dataCommitted.connect(self.load_rates)
                dialog.exec()

    def filter_rates(self, text):
        query = text.lower()
        for row in range(self.table.rowCount()):
            item0 = self.table.item(row, 0)
            item1 = self.table.item(row, 1)
            if item0 and item1:
                id_match = query in item0.text().lower()
                desc_match = query in item1.text().lower()
                self.table.setRowHidden(row, not (id_match or desc_match))

    def on_item_changed(self, item):
        """Handles inline editing of Rate Code and Description."""
        if self.is_loading:
            return
            
        row = item.row()
        col = item.column()
        
        # Only handle Rate Code (0) and Description (1)
        if col not in [0, 1]:
            return
            
        db_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        if not db_id:
            return
            
        new_val = item.text().strip()
        field = "rate_code" if col == 0 else "project_name"
        
        if self.db_manager.update_estimate_field(db_id, field, new_val):
            # If Rate Code was changed, we might need to update the UserRole storage if it was the first column, 
            # but UserRole is on the item itself, so it's fine.
            pass
        else:
            QMessageBox.warning(self, "Error", f"Failed to update {field} in database.")
            # Revert UI? Better to just load_rates to be sure
            self.load_rates()

    def show_context_menu(self, pos):
        """Shows the context menu for the rate table."""
        menu = QMenu(self)
        
        new_action = QAction("New Rate", self)
        new_action.triggered.connect(self.new_rate)
        menu.addAction(new_action)
        
        selected_indexes = self.table.selectionModel().selectedRows()
        if selected_indexes:
            edit_action = QAction("Edit Rate", self)
            edit_action.triggered.connect(self.edit_rate)
            menu.addAction(edit_action)
            
            menu.addSeparator()
            
            duplicate_action = QAction("Duplicate Rate", self)
            duplicate_action.triggered.connect(self.duplicate_rate)
            menu.addAction(duplicate_action)
            
            delete_action = QAction("Delete Rate", self)
            delete_action.triggered.connect(self.delete_rate)
            menu.addAction(delete_action)
            
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def edit_rate(self):
        """Opens the build-up dialog for the selected rate."""
        selected_indexes = self.table.selectionModel().selectedRows()
        if selected_indexes:
            self.open_rate_buildup(selected_indexes[0])

    def new_rate(self):
        """Creates a new rate and opens the build-up dialog."""
        from models import Estimate
        from rate_buildup_dialog import RateBuildUpDialog
        
        new_est = Estimate("New Rate", "N/A", 15.0, 10.0)
        new_est.category = "Miscellaneous"
        new_est.rate_code = self.db_manager.generate_next_rate_code(new_est.category)
        
        dialog = RateBuildUpDialog(new_est, main_window=self.main_window, parent=self)
        dialog.dataCommitted.connect(self.load_rates)
        dialog.exec()

    def duplicate_rate(self):
        """Duplicates the selected rate."""
        selected_indexes = self.table.selectionModel().selectedRows()
        if not selected_indexes:
            return
            
        row = selected_indexes[0].row()
        db_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        
        if db_id:
            # Load full details to ensure we duplicate everything (tasks, items, etc.)
            original_estimate = self.db_manager.load_estimate_details(db_id)
            if original_estimate:
                original_estimate.id = None
                original_estimate.project_name = f"Copy of {original_estimate.project_name}"
                # Generate a new unique rate code
                category = getattr(original_estimate, 'category', "Miscellaneous")
                original_estimate.rate_code = self.db_manager.generate_next_rate_code(category)
                
                if self.db_manager.save_estimate(original_estimate):
                    self.load_rates()

    def delete_rate(self):
        """Deletes the selected rate after confirmation."""
        selected_indexes = self.table.selectionModel().selectedRows()
        if not selected_indexes:
            return
            
        row = selected_indexes[0].row()
        db_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        rate_code = self.table.item(row, 0).text()
        
        if db_id:
            reply = QMessageBox.question(self, 'Delete Rate',
                                       f"Are you sure you want to delete Rate {rate_code}?",
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                       QMessageBox.StandardButton.No)
            
            if reply == QMessageBox.StandardButton.Yes:
                if self.db_manager.delete_estimate(db_id):
                    self.load_rates()
