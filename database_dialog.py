# database_dialog.py

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QTabWidget, QWidget, QPushButton,
                             QTableWidget, QTableWidgetItem, QHBoxLayout, QMessageBox,
                             QLineEdit, QFormLayout, QDialogButtonBox, QLabel, QHeaderView,
                             QComboBox)
from database import DatabaseManager


class DatabaseManagerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.db_manager = DatabaseManager()
        self.setWindowTitle("Manage Cost Database")
        self.setMinimumSize(1000, 700)

        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # Create tabs
        self.materials_tab = QWidget()
        self.labor_tab = QWidget()
        self.equipment_tab = QWidget()
        self.tabs.addTab(self.materials_tab, "Materials")
        self.tabs.addTab(self.labor_tab, "Labor")
        self.tabs.addTab(self.equipment_tab, "Equipment")

        # Setup UI for each tab
        self._setup_tab(self.materials_tab, "materials", ["ID", "Material", "Unit", "Currency", "Price"])
        self._setup_tab(self.labor_tab, "labor", ["ID", "Labor", "Currency", "Rate per Hour"])
        self._setup_tab(self.equipment_tab, "equipment", ["ID", "Equipment", "Currency", "Rate per Hour"])

    def _setup_tab(self, tab, table_name, headers):
        layout = QVBoxLayout(tab)

        # --- START OF CHANGE: Add Search Bar ---
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search:"))
        search_input = QLineEdit()
        search_input.setPlaceholderText("Type to filter...")
        search_layout.addWidget(search_input)
        layout.addLayout(search_layout)
        # --- END OF CHANGE ---

        table = QTableWidget()
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setStretchLastSection(True)
        table.setShowGrid(True)
        table.setColumnHidden(0, True)
        layout.addWidget(table)
        setattr(self, f"{table_name}_table", table)

        btn_layout = QHBoxLayout()
        singular_name = table_name[:-1] if table_name.endswith('s') else table_name
        add_btn = QPushButton(f"Add {singular_name.capitalize()}")
        edit_btn = QPushButton(f"Edit Selected")
        delete_btn = QPushButton(f"Delete Selected")
        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(edit_btn)
        btn_layout.addWidget(delete_btn)
        layout.addLayout(btn_layout)

        # Connect signals
        search_input.textChanged.connect(lambda text, tbl=table: self.filter_table(text, tbl))
        add_btn.clicked.connect(lambda: self.add_item(table_name))
        edit_btn.clicked.connect(lambda: self.edit_item(table_name))
        delete_btn.clicked.connect(lambda: self.delete_item(table_name))

        self.load_data(table_name)

    # --- START OF CHANGE: Add Filter Method ---
    def filter_table(self, text, table):
        """Hides or shows rows based on the search text."""
        search_text = text.lower()
        for row in range(table.rowCount()):
            # Column 1 is always the main name/trade column
            item_text = table.item(row, 1).text().lower()
            if search_text in item_text:
                table.setRowHidden(row, False)
            else:
                table.setRowHidden(row, True)
        
        # Recalculate widths after filtering
        self._adjust_table_widths(table)
    # --- END OF CHANGE ---

    def load_data(self, table_name):
        table = getattr(self, f"{table_name}_table")
        table.setRowCount(0)
        items = self.db_manager.get_items(table_name)
        for row_num, row_data in enumerate(items):
            table.insertRow(row_num)
            for col_num, data in enumerate(row_data):
                # Check for Currency column: Materials is col 3, Labor/Equip is col 2
                is_currency_col = (table_name == "materials" and col_num == 3) or \
                                 (table_name in ["labor", "equipment"] and col_num == 2)
                
                if is_currency_col: # Currency column
                    combo = QComboBox()
                    currencies = ["USD ($)", "EUR (€)", "GBP (£)", "JPY (¥)", "CAD ($)", "GHS (₵)", "CNY (¥)", "INR (₹)"]
                    combo.addItems(currencies)
                    combo.setCurrentText(str(data) if data else "GHS (₵)")
                    
                    # Connect change to update database
                    item_id = int(row_data[0])
                    combo.currentTextChanged.connect(lambda text, tid=item_id, tbl=table_name: 
                                                   self._update_currency(tbl, tid, text))
                    
                    table.setCellWidget(row_num, col_num, combo)
                    # Also set an item so sorting/filtering works (though it might be hidden)
                    item = QTableWidgetItem(str(data))
                    table.setItem(row_num, col_num, item)
                else:
                    # Format price/rate (last column) to 2 decimal places
                    if col_num == len(row_data) - 1:
                        try:
                            display_text = f"{float(data):.2f}"
                        except (ValueError, TypeError):
                            display_text = str(data)
                    else:
                        display_text = str(data)
                        
                    item = QTableWidgetItem(display_text)
                    table.setItem(row_num, col_num, item)
        
        self._adjust_table_widths(table)

    def _update_currency(self, table_name, item_id, new_currency):
        """Updates the currency in the database when changed in the table."""
        self.db_manager.update_item_currency(table_name, item_id, new_currency)
        
        # We also need to update the hidden QTableWidgetItem for the currency column
        # so that it stays in sync for filtering or if cellWidget is removed.
        table = getattr(self, f"{table_name}_table")
        currency_col = 3 if table_name == "materials" else 2
        
        for row in range(table.rowCount()):
            id_item = table.item(row, 0)
            if id_item and int(id_item.text()) == item_id:
                hidden_item = table.item(row, currency_col)
                if hidden_item:
                    hidden_item.setText(new_currency)
                break

    def _adjust_table_widths(self, table):
        """Helper to resize columns to contents and reset to interactive."""
        for i in range(table.columnCount()):
            table.resizeColumnToContents(i)
        
        # Reset to interactive to allow user adjustment
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        table.horizontalHeader().setStretchLastSection(True)

    def add_item(self, table_name):
        dialog = ItemDialog(table_name, self)
        if dialog.exec():
            data = dialog.get_data()
            if data:
                if not self.db_manager.add_item(table_name, data):
                    QMessageBox.warning(self, "Error", "An item with this name already exists.")
                self.load_data(table_name)

    def edit_item(self, table_name):
        table = getattr(self, f"{table_name}_table")
        selected_row = table.currentRow()
        if selected_row < 0:
            QMessageBox.warning(self, "Selection Error", "Please select an item to edit.")
            return

        item_id = int(table.item(selected_row, 0).text())
        current_data = []
        for i in range(1, table.columnCount()):
            widget = table.cellWidget(selected_row, i)
            if isinstance(widget, QComboBox):
                current_data.append(widget.currentText())
            else:
                item = table.item(selected_row, i)
                current_data.append(item.text() if item else "")

        dialog = ItemDialog(table_name, self, current_data)
        if dialog.exec():
            new_data = dialog.get_data()
            if new_data:
                self.db_manager.update_item(table_name, item_id, new_data)
                self.load_data(table_name)

    def delete_item(self, table_name):
        table = getattr(self, f"{table_name}_table")
        selected_row = table.currentRow()
        if selected_row < 0:
            QMessageBox.warning(self, "Selection Error", "Please select an item to delete.")
            return

        item_id = int(table.item(selected_row, 0).text())
        item_name = table.item(selected_row, 1).text()

        reply = QMessageBox.question(self, "Confirm Delete", f"Are you sure you want to delete '{item_name}'?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.db_manager.delete_item(table_name, item_id)
            self.load_data(table_name)


class ItemDialog(QDialog):
    """A generic dialog to add/edit materials, labor, or equipment."""

    def __init__(self, table_name, parent=None, data=None):
        super().__init__(parent)
        singular_name = table_name[:-1] if table_name.endswith('s') else table_name
        self.setWindowTitle(f"{'Edit' if data else 'Add'} {singular_name.capitalize()}")
        self.resize(600, 300) # Widen the window by 2x

        self.layout = QFormLayout(self)
        self.inputs = []

        if table_name == "materials":
            self.fields = [("Material", QLineEdit), ("Unit", QLineEdit), ("Currency", QComboBox), ("Price", QLineEdit)]
        elif table_name == "labor":
            self.fields = [("Labor", QLineEdit), ("Currency", QComboBox), ("Rate per Hour", QLineEdit)]
        elif table_name == "equipment":
            self.fields = [("Equipment", QLineEdit), ("Currency", QComboBox), ("Rate per Hour", QLineEdit)]
        else:
            self.fields = []

        for i, (label, widget_class) in enumerate(self.fields):
            widget = widget_class()
            if widget_class == QComboBox and label == "Currency":
                currencies = ["USD ($)", "EUR (€)", "GBP (£)", "JPY (¥)", "CAD ($)", "GHS (₵)", "CNY (¥)", "INR (₹)"]
                widget.addItems(currencies)
                if data:
                    widget.setCurrentText(str(data[i]))
                else:
                    widget.setCurrentText("GHS (₵)")
            elif data:
                widget.setText(str(data[i]))
            
            self.layout.addRow(label, widget)
            self.inputs.append(widget)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout.addWidget(self.button_box)

    def get_data(self):
        data = []
        for widget in self.inputs:
            if isinstance(widget, QComboBox):
                data.append(widget.currentText())
            else:
                data.append(widget.text())
                
        if not all(str(d).strip() for d in data):
            QMessageBox.warning(self, "Input Error", "All fields must be filled.")
            return None
        try:
            # Last field is always numeric (price/rate)
            data[-1] = float(data[-1])
            return tuple(data)
        except ValueError:
            QMessageBox.warning(self, "Input Error", "Price/Rate must be a valid number.")
            return None