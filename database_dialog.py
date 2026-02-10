# database_dialog.py

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QTabWidget, QWidget, QPushButton,
                             QTableWidget, QTableWidgetItem, QHBoxLayout, QMessageBox,
                             QLineEdit, QFormLayout, QDialogButtonBox, QLabel, QHeaderView,
                             QComboBox, QDateEdit, QMenu)
from PyQt6.QtCore import QDate, Qt
from database import DatabaseManager


class DatabaseManagerDialog(QDialog):
    """Dialog for managing the global cost library (Materials, Labor, Equipment)."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.db_manager = DatabaseManager()
        self.setWindowTitle("Manage Cost Database")
        self.setMinimumSize(1100, 750)
        self.is_loading = False

        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # Tab configuration: (Tab Name, Table Name, Column Headers)
        self.tab_configs = [
            ("Materials", "materials", ["ID", "Material", "Unit", "Currency", "Price", "Date", "Location", "Contact", "Remarks"]),
            ("Labor", "labor", ["ID", "Labor", "Unit", "Currency", "Rate", "Date", "Location", "Contact", "Remarks"]),
            ("Equipment", "equipment", ["ID", "Equipment", "Unit", "Currency", "Rate", "Date", "Location", "Contact", "Remarks"]),
            ("Plant", "plant", ["ID", "Plant", "Unit", "Currency", "Rate", "Date", "Location", "Contact", "Remarks"])
        ]

        self.tables = {}
        for title, table_name, headers in self.tab_configs:
            tab_widget = QWidget()
            self._setup_tab(tab_widget, table_name, headers)
            self.tabs.addTab(tab_widget, title)

    def _setup_tab(self, tab, table_name, headers):
        layout = QVBoxLayout(tab)

        # Search
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search:"))
        search_input = QLineEdit(placeholderText="Type to filter...")
        search_layout.addWidget(search_input)
        layout.addLayout(search_layout)

        # Table
        table = QTableWidget(columnCount=len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setEditTriggers(QTableWidget.EditTrigger.DoubleClicked | 
                            QTableWidget.EditTrigger.EditKeyPressed | 
                            QTableWidget.EditTrigger.AnyKeyPressed)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.setWordWrap(True)
        table.setColumnHidden(0, True) # ID
        table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        table.customContextMenuRequested.connect(lambda pos, t=table_name: self.show_context_menu(pos, t))
        layout.addWidget(table)
        self.tables[table_name] = table

        # Connect signals
        search_input.textChanged.connect(lambda text, tbl=table: self.filter_table(text, tbl))
        table.itemChanged.connect(lambda item: self.on_item_changed(item, table_name))
        
        self.load_data(table_name)

    def filter_table(self, text, table):
        query = text.lower()
        for row in range(table.rowCount()):
            table.setRowHidden(row, query not in table.item(row, 1).text().lower())

    def load_data(self, table_name):
        """Loads and formats library data into the tab table."""
        self.is_loading = True
        table = self.tables[table_name]
        table.setRowCount(0)
        items = self.db_manager.get_items(table_name)
        
        # Column indices for special widgets
        is_mat = (table_name == "materials")
        curr_col = 3
        date_col = 5
        price_col = 4

        for row_idx, row_data in enumerate(items):
            table.insertRow(row_idx)
            for col_idx, data in enumerate(row_data):
                item_id = int(row_data[0])
                
                if col_idx == curr_col:
                    self._add_currency_widget(table, row_idx, col_idx, data, table_name, item_id)
                elif col_idx == date_col:
                    self._add_date_widget(table, row_idx, col_idx, data, table_name, item_id)
                else:
                    # Formatting numbers
                    display = f"{float(data):.2f}" if col_idx == price_col and data is not None else str(data or "")
                    table.setItem(row_idx, col_idx, QTableWidgetItem(display))
        
        self._adjust_widths(table, table_name)
        self.is_loading = False

    def on_item_changed(self, item, table_name):
        if self.is_loading: return
        
        table = item.tableWidget()
        row = item.row()
        col = item.column()
        
        # Get ID
        id_item = table.item(row, 0)
        if not id_item: return
        item_id = int(id_item.text())
        
        new_value = item.text().strip()
        
        # Define field mapping for column indices
        # Indices: 1:Name, 2:Unit, 4:Price/Rate, 6:Location, 7:Contact, 8:Remarks
        field_map = {
            1: 'trade' if table_name == 'labor' else 'name',
            2: 'unit',
            4: 'rate' if table_name in ['labor', 'equipment', 'plant'] else 'price',
            6: 'location',
            7: 'contact',
            8: 'remarks'
        }
        
        column_name = field_map.get(col)
        if not column_name: return
        
        # Numeric validation for column 4
        if col == 4:
            try:
                new_value = float(new_value or 0)
                # Re-format the cell to show 2 decimals
                self.is_loading = True # Prevent recursion
                item.setText(f"{new_value:.2f}")
                self.is_loading = False
            except ValueError:
                QMessageBox.warning(self, "Invalid Input", "Please enter a valid number.")
                self.load_data(table_name) # Revert
                return

        self.db_manager.update_item_field(table_name, column_name, new_value, item_id)

    def show_context_menu(self, pos, table_name):
        table = self.tables[table_name]
        menu = QMenu(self)
        
        singular = table_name[:-1] if table_name.endswith('s') else table_name
        
        # Select row on right-click
        item = table.itemAt(pos)
        if item:
            table.selectRow(item.row())
        
        add_action = menu.addAction(f"Add new {singular.capitalize()}")
        add_action.triggered.connect(lambda: self.add_item(table_name))
        
        # Actions for selected row
        if item:
            menu.addSeparator()
            dup_action = menu.addAction(f"Duplicate {singular.capitalize()}")
            dup_action.triggered.connect(lambda: self.duplicate_item(table_name))
            
            delete_action = menu.addAction(f"Delete selected {singular.capitalize()}")
            delete_action.triggered.connect(lambda: self.delete_item(table_name))
            
        menu.exec(table.viewport().mapToGlobal(pos))

    def _add_currency_widget(self, table, row, col, current_val, table_name, item_id):
        combo = QComboBox()
        currencies = ["USD ($)", "EUR (€)", "GBP (£)", "JPY (¥)", "CAD ($)", "GHS (₵)", "CNY (¥)", "INR (₹)"]
        combo.addItems(currencies)
        combo.setCurrentText(str(current_val or "GHS (₵)"))
        combo.currentTextChanged.connect(lambda text: self.db_manager.update_item_currency(table_name, item_id, text))
        table.setCellWidget(row, col, combo)
        table.setItem(row, col, QTableWidgetItem(combo.currentText())) # For search/sort

    def _add_date_widget(self, table, row, col, current_val, table_name, item_id):
        date_edit = QDateEdit(calendarPopup=True, displayFormat="dd-MM-yy")
        qdate = QDate.fromString(str(current_val), "yyyy-MM-dd")
        date_edit.setDate(qdate if qdate.isValid() else QDate.currentDate())
        date_edit.dateChanged.connect(lambda d: self.db_manager.update_item_date(table_name, item_id, d.toString("yyyy-MM-dd")))
        table.setCellWidget(row, col, date_edit)
        table.setItem(row, col, QTableWidgetItem(date_edit.date().toString("yyyy-MM-dd")))

    def _adjust_widths(self, table, table_name):
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        
        # Ensure widget columns have enough space for drop-down arrows
        col_indices = [3, 5]
        for col in col_indices:
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
            table.setColumnWidth(col, 120)
        
        header.setStretchLastSection(True)
        table.resizeRowsToContents()

    def add_item(self, table_name):
        """Adds a new empty placeholder item to the database and a row to the table for inline editing."""
        now = QDate.currentDate().toString("yyyy-MM-dd")
        default_curr = self.db_manager.get_setting('currency', 'GHS (₵)')
        
        # Create a placeholder record to get an ID. 
        # Materials: name, unit, currency, price, date, location, contact, remarks (8 items)
        # Labor/Equip: trade/name, unit, currency, rate, date, location, contact, remarks (8 items)
        placeholder_data = ("New Item...", "", default_curr, 0.0, now, "", "", "")
        
        item_id = self.db_manager.add_item(table_name, placeholder_data)
        if item_id:
            table = self.tables[table_name]
            new_row_idx = table.rowCount()
            self.is_loading = True
            table.insertRow(new_row_idx)
            
            # ID (hidden)
            table.setItem(new_row_idx, 0, QTableWidgetItem(str(item_id)))
            
            # Fields
            table.setItem(new_row_idx, 1, QTableWidgetItem("New Item...")) # Name/Trade
            table.setItem(new_row_idx, 2, QTableWidgetItem("")) # Unit
            self._add_currency_widget(table, new_row_idx, 3, default_curr, table_name, item_id)
            table.setItem(new_row_idx, 4, QTableWidgetItem("0.00")) # Price/Rate
            self._add_date_widget(table, new_row_idx, 5, now, table_name, item_id)
            table.setItem(new_row_idx, 6, QTableWidgetItem("")) # Location
            table.setItem(new_row_idx, 7, QTableWidgetItem("")) # Contact
            table.setItem(new_row_idx, 8, QTableWidgetItem("")) # Remarks
            
            self.is_loading = False
            self._adjust_widths(table, table_name)
            
            # Highlight and scroll to the new row
            table.scrollToBottom()
            table.selectRow(new_row_idx)
            
            # Start editing the name cell immediately
            table.editItem(table.item(new_row_idx, 1))
        else:
            QMessageBox.warning(self, "Error", "Failed to create a new item placeholder.")

    def duplicate_item(self, table_name):
        """Duplicates the currently selected item."""
        table = self.tables[table_name]
        row = table.currentRow()
        if row < 0: return

        # Extract data from the selected row
        item_id = int(table.item(row, 0).text())
        
        # Scrape current data from the table (some might be in widgets)
        def get_val(r, c):
            w = table.cellWidget(r, c)
            if hasattr(w, 'currentText'): return w.currentText()
            if hasattr(w, 'date'): return w.date().toString("yyyy-MM-dd")
            item = table.item(r, c)
            return item.text().strip() if item else ""

        name = get_val(row, 1) + " (Copy)"
        unit = get_val(row, 2)
        curr = get_val(row, 3)
        rate = get_val(row, 4)
        date = get_val(row, 5)
        loc = get_val(row, 6)
        con = get_val(row, 7)
        rem = get_val(row, 8)

        # Convert rate to float for DB insertion
        try:
            rate_val = float(rate or 0)
        except ValueError:
            rate_val = 0.0

        copy_data = (name, unit, curr, rate_val, date, loc, con, rem)
        
        new_id = self.db_manager.add_item(table_name, copy_data)
        if new_id:
            # Add to the bottom
            new_row_idx = table.rowCount()
            self.is_loading = True
            table.insertRow(new_row_idx)
            
            table.setItem(new_row_idx, 0, QTableWidgetItem(str(new_id)))
            table.setItem(new_row_idx, 1, QTableWidgetItem(name))
            table.setItem(new_row_idx, 2, QTableWidgetItem(unit))
            self._add_currency_widget(table, new_row_idx, 3, curr, table_name, new_id)
            table.setItem(new_row_idx, 4, QTableWidgetItem(f"{rate_val:.2f}"))
            self._add_date_widget(table, new_row_idx, 5, date, table_name, new_id)
            table.setItem(new_row_idx, 6, QTableWidgetItem(loc))
            table.setItem(new_row_idx, 7, QTableWidgetItem(con))
            table.setItem(new_row_idx, 8, QTableWidgetItem(rem))
            
            self.is_loading = False
            self._adjust_widths(table, table_name)
            table.scrollToBottom()
            table.selectRow(new_row_idx)
        else:
            QMessageBox.warning(self, "Error", "Failed to duplicate item.")

    def delete_item(self, table_name):
        table = self.tables[table_name]
        row = table.currentRow()
        if row < 0: return
        
        item_id = int(table.item(row, 0).text())
        name = table.item(row, 1).text()
        
        if QMessageBox.question(self, "Delete", f"Delete '{name}'?") == QMessageBox.StandardButton.Yes:
            self.db_manager.delete_item(table_name, item_id)
            self.load_data(table_name)
