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
            ("Equipment", "equipment", ["ID", "Equipment", "Unit", "Currency", "Rate", "Date", "Location", "Contact", "Remarks"])
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

        # Actions
        btn_layout = QHBoxLayout()
        singular = table_name[:-1] if table_name.endswith('s') else table_name
        
        actions = [
            (f"Add {singular.capitalize()}", lambda _, t=table_name: self.add_item(t)),
            ("Edit Selected", lambda _, t=table_name: self.edit_item(t)),
            ("Delete Selected", lambda _, t=table_name: self.delete_item(t))
        ]

        for text, slot in actions:
            btn = QPushButton(text)
            btn.clicked.connect(slot)
            btn_layout.addWidget(btn)
        
        layout.addLayout(btn_layout)

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
            4: 'rate' if table_name in ['labor', 'equipment'] else 'price',
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
        
        add_action = menu.addAction(f"Add new {singular.capitalize()}")
        add_action.triggered.connect(lambda: self.add_item(table_name))
        
        # Only show delete if a row is selected
        if table.itemAt(pos):
            menu.addSeparator()
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
            # We insert at the top for visibility
            table = self.tables[table_name]
            self.is_loading = True
            table.insertRow(0)
            
            # ID (hidden)
            table.setItem(0, 0, QTableWidgetItem(str(item_id)))
            
            # Fields
            table.setItem(0, 1, QTableWidgetItem("New Item...")) # Name/Trade
            table.setItem(0, 2, QTableWidgetItem("")) # Unit
            self._add_currency_widget(table, 0, 3, default_curr, table_name, item_id)
            table.setItem(0, 4, QTableWidgetItem("0.00")) # Price/Rate
            self._add_date_widget(table, 0, 5, now, table_name, item_id)
            table.setItem(0, 6, QTableWidgetItem("")) # Location
            table.setItem(0, 7, QTableWidgetItem("")) # Contact
            table.setItem(0, 8, QTableWidgetItem("")) # Remarks
            
            self.is_loading = False
            self._adjust_widths(table, table_name)
            
            # Highlight and scroll to the new row
            table.scrollToTop()
            table.selectRow(0)
            
            # Optionally start editing the name cell immediately
            table.editItem(table.item(0, 1))
        else:
            QMessageBox.warning(self, "Error", "Failed to create a new item placeholder.")

    def edit_item(self, table_name):
        table = self.tables[table_name]
        row = table.currentRow()
        if row < 0: return QMessageBox.warning(self, "Selection Error", "Select an item.")

        item_id = int(table.item(row, 0).text())
        # Re-fetch data or scrape from table
        current_data = []
        for i in range(1, table.columnCount()):
            w = table.cellWidget(row, i)
            if hasattr(w, 'currentText'): current_data.append(w.currentText())
            elif hasattr(w, 'date'): current_data.append(w.date().toString("yyyy-MM-dd"))
            else: current_data.append(table.item(row, i).text())

        dialog = ItemDialog(table_name, self, current_data)
        if dialog.exec():
            data = dialog.get_data()
            if data:
                self.db_manager.update_item(table_name, item_id, data)
                self.load_data(table_name)

    def delete_item(self, table_name):
        table = self.tables[table_name]
        row = table.currentRow()
        if row < 0: return
        
        item_id = int(table.item(row, 0).text())
        name = table.item(row, 1).text()
        
        if QMessageBox.question(self, "Delete", f"Delete '{name}'?") == QMessageBox.StandardButton.Yes:
            self.db_manager.delete_item(table_name, item_id)
            self.load_data(table_name)


class ItemDialog(QDialog):
    """Dialog for metadata entry in the cost library."""
    def __init__(self, table_name, parent=None, data=None):
        super().__init__(parent)
        singular = table_name[:-1] if table_name.endswith('s') else table_name
        self.setWindowTitle(f"{'Edit' if data else 'Add'} {singular.capitalize()}")
        self.setMinimumWidth(500)
        
        self.layout = QFormLayout(self)
        self.inputs = []
        
        # Field mapping
        fields = [("Name", QLineEdit), ("Unit", QLineEdit), ("Currency", QComboBox), ("Price/Rate", QLineEdit), ("Date", QDateEdit), ("Location", QLineEdit), ("Contact", QLineEdit), ("Remarks", QLineEdit)]

        for i, (label, widget_class) in enumerate(fields):
            w = widget_class()
            if isinstance(w, QComboBox):
                w.addItems(["USD ($)", "EUR (€)", "GBP (£)", "JPY (¥)", "CAD ($)", "GHS (₵)", "CNY (¥)", "INR (₹)"])
                if data: w.setCurrentText(str(data[i]))
                else: w.setCurrentText(DatabaseManager().get_setting('currency', 'GHS (₵)'))
            elif isinstance(w, QDateEdit):
                w.setCalendarPopup(True)
                w.setDisplayFormat("dd-MM-yy")
                qdate = QDate.fromString(str(data[i] if data else ""), "yyyy-MM-dd")
                w.setDate(qdate if qdate.isValid() else QDate.currentDate())
            elif data:
                w.setText(str(data[i]))
            
            self.layout.addRow(label, w)
            self.inputs.append(w)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.layout.addRow(buttons)

    def get_data(self):
        vals = []
        for w in self.inputs:
            if hasattr(w, 'currentText'): vals.append(w.currentText())
            elif hasattr(w, 'date'): vals.append(w.date().toString("yyyy-MM-dd"))
            else: vals.append(w.text().strip())
        
        # Basic Validation
        if not vals[0]: 
            QMessageBox.warning(self, "Error", "Name is required.")
            return None
        
        try:
            # Price/Rate is always at index 3 now: Name(0), Unit(1), Currency(2), Price/Rate(3)
            p_idx = 3
            vals[p_idx] = float(vals[p_idx] or 0)
            return tuple(vals)
        except ValueError:
            QMessageBox.warning(self, "Error", "Price/Rate must be a number.")
            return None
