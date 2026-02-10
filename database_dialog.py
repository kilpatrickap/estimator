# database_dialog.py

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QTabWidget, QWidget, QPushButton,
                             QTableWidget, QTableWidgetItem, QHBoxLayout, QMessageBox,
                             QLineEdit, QFormLayout, QDialogButtonBox, QLabel, QHeaderView,
                             QComboBox, QDateEdit, QMenu)
from PyQt6.QtCore import QDate, Qt
from database import DatabaseManager
from edit_item_dialog import EditItemDialog


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
            ("Plant", "plant", ["ID", "Plant", "Unit", "Currency", "Rate", "Date", "Location", "Contact", "Remarks"]),
            ("Indirect Costs", "indirect_costs", ["ID", "Description", "Unit", "Currency", "Amount", "Date"])
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
        table.itemChanged.connect(lambda item: self.on_item_changed(item, table_name))
        table.itemDoubleClicked.connect(lambda item: self.on_item_double_clicked(item, table_name))
        
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
            
            # DB indices: 0:id, 1:name, 2:unit, 3:curr, 4:val, 5:formula, 6:date, 7:loc, 8:con, 9:rem
            item_id = int(row_data[0])
            
            # Map DB to UI
            # 0:ID, 1:Name, 2:Unit
            table.setItem(row_idx, 0, QTableWidgetItem(str(row_data[0])))
            table.setItem(row_idx, 1, QTableWidgetItem(str(row_data[1] or "")))
            table.setItem(row_idx, 2, QTableWidgetItem(str(row_data[2] or "")))
            
            # 3:Currency (Widget)
            self._add_currency_widget(table, row_idx, curr_col, row_data[3], table_name, item_id)
            
            # 4:Price/Rate (Value + Formula in UserRole)
            val = row_data[4]
            formula = row_data[5]
            display = f"{float(val):.2f}" if val is not None else "0.00"
            val_item = QTableWidgetItem(display)
            val_item.setData(Qt.ItemDataRole.UserRole, formula)
            table.setItem(row_idx, price_col, val_item)
            
            # 5:Date (Widget)
            self._add_date_widget(table, row_idx, date_col, row_data[6], table_name, item_id)
            
            # 6-8: Location, Contact, Remarks (if applicable)
            if table_name != 'indirect_costs':
                table.setItem(row_idx, 6, QTableWidgetItem(str(row_data[7] or "")))
                table.setItem(row_idx, 7, QTableWidgetItem(str(row_data[8] or "")))
                table.setItem(row_idx, 8, QTableWidgetItem(str(row_data[9] or "")))
        
        self._adjust_widths(table, table_name)
        self.is_loading = False

    def on_item_double_clicked(self, item, table_name):
        """Intersects double-clicks on the price/rate column to open the formula editor."""
        if item.column() == 4: # Price/Rate/Amount column
            self.open_formula_editor(item, table_name)

    def open_formula_editor(self, item, table_name):
        """Opens the formula-based editor for library prices/rates."""
        table = item.tableWidget()
        row = item.row()
        item_id = int(table.item(row, 0).text())
        
        # Prepare data for dialog
        price_key = 'price' if table_name == 'materials' else ('amount' if table_name == 'indirect_costs' else 'rate')
        current_val = float(item.text().replace(',', ''))
        current_formula = item.data(Qt.ItemDataRole.UserRole)
        
        item_data = {
            'name': table.item(row, 1).text(),
            price_key: current_val,
            'formula': current_formula
        }
        
        dialog = EditItemDialog(item_data, table_name, "GHS (₵)", parent=self, is_library=True)
        if dialog.exec():
            new_val = item_data[price_key]
            new_formula = item_data.get('formula')
            
            # Update DB
            self.db_manager.update_item_field(table_name, price_key, new_val, item_id)
            self.db_manager.update_item_field(table_name, 'formula', new_formula, item_id)
            
            # Update UI
            self.is_loading = True
            item.setText(f"{new_val:.2f}")
            item.setData(Qt.ItemDataRole.UserRole, new_formula)
            self.is_loading = False

    def on_item_changed(self, item, table_name):
        if self.is_loading: return
        
        table = item.tableWidget()
        row = item.row()
        col = item.column()
        
        if col == 4:
            # If user manually typed a number, we should clear the formula
            item.setData(Qt.ItemDataRole.UserRole, None)
            self.db_manager.update_item_field(table_name, 'formula', None, int(table.item(row, 0).text()))
        
        # Get ID
        id_item = table.item(row, 0)
        if not id_item: return
        item_id = int(id_item.text())
        
        new_value = item.text().strip()
        
        # Define field mapping for column indices
        # Indices: 1:Name, 2:Unit, 4:Price/Rate, 6:Location, 7:Contact, 8:Remarks
        field_map = {
            1: 'trade' if table_name == 'labor' else ('description' if table_name == 'indirect_costs' else 'name'),
            2: 'unit',
            4: 'rate' if table_name in ['labor', 'equipment', 'plant'] else ('amount' if table_name == 'indirect_costs' else 'price'),
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
                QMessageBox.warning(self, "Error", "Invalid numeric value.")
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
        
        # Ensure widget columns (Currency and Date) have enough space but don't stretch
        for col in [3, 5]:
            if col < table.columnCount():
                header.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
                table.setColumnWidth(col, 120)

        # Stretch the primary descriptive column (Material/Labor/Equipment/Plant/Description)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        
        header.setStretchLastSection(False)
        table.resizeRowsToContents()

    def add_item(self, table_name):
        """Adds a new empty placeholder item to the database and a row to the table for inline editing."""
        now = QDate.currentDate().toString("yyyy-MM-dd")
        default_curr = self.db_manager.get_setting('currency', 'GHS (₵)')
        
        if table_name == 'indirect_costs':
            # name, unit, curr, amount, formula, date (6 items)
            placeholder_data = ("New Item...", "", default_curr, 0.0, None, now)
        else:
            # name/trade, unit, currency, price/rate, formula, date, location, contact, remarks (9 items)
            placeholder_data = ("New Item...", "", default_curr, 0.0, None, now, "", "", "")
        
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
            price_item = QTableWidgetItem("0.00")
            price_item.setData(Qt.ItemDataRole.UserRole, None)
            table.setItem(new_row_idx, 4, price_item)
            self._add_date_widget(table, new_row_idx, 5, now, table_name, item_id)
            if table_name != 'indirect_costs':
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

        # Convert rate to float for DB insertion
        try:
            rate_val = float(rate or 0)
        except ValueError:
            rate_val = 0.0

        formula = table.item(row, 4).data(Qt.ItemDataRole.UserRole)

        if table_name == 'indirect_costs':
            copy_data = (name, unit, curr, rate_val, formula, date)
        else:
            loc = get_val(row, 6)
            con = get_val(row, 7)
            rem = get_val(row, 8)
            copy_data = (name, unit, curr, rate_val, formula, date, loc, con, rem)
        
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
            rate_item = QTableWidgetItem(f"{rate_val:.2f}")
            rate_item.setData(Qt.ItemDataRole.UserRole, formula)
            table.setItem(new_row_idx, 4, rate_item)
            self._add_date_widget(table, new_row_idx, 5, date, table_name, new_id)
            if table_name != 'indirect_costs':
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
