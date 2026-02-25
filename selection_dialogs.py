from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QPushButton, QMessageBox
)
from database import DatabaseManager

class CostSelectionDialog(QDialog):
    """Simplified dialog to select a cost from the global database."""
    def __init__(self, table_name, parent=None):
        super().__init__(parent)
        self.table_name = table_name
        self.selected_item = None
        
        singular = table_name[:-1] if table_name.endswith('s') else table_name
        self.setWindowTitle(f"Select {singular.capitalize()} from Database")
        self.setMinimumSize(420, 400)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Search
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Type to filter...")
        self.search_input.textChanged.connect(self.filter_table)
        search_layout.addWidget(self.search_input)
        layout.addLayout(search_layout)
        
        # Table
        self.table = QTableWidget()
        self.db_manager = DatabaseManager("construction_costs.db")
        self.load_data()
        
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setDefaultSectionSize(22)
        self.table.doubleClicked.connect(self.accept)
        
        layout.addWidget(self.table)
        
        # Buttons
        btns = QHBoxLayout()
        btns.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        select_btn = QPushButton("Select")
        select_btn.clicked.connect(self.accept)
        select_btn.setStyleSheet("background-color: #2e7d32; color: white; font-weight: bold;")
        
        btns.addWidget(cancel_btn)
        btns.addWidget(select_btn)
        layout.addLayout(btns)

    def load_data(self):
        items = self.db_manager.get_items(self.table_name)
        if not items:
            return
            
        # Headers based on table
        if self.table_name == "materials":
            headers = ["Name", "Unit", "Currency", "Price"]
            keys = ["name", "unit", "currency", "price"]
        elif self.table_name == "labor":
            headers = ["Trade", "Unit", "Currency", "Rate"]
            keys = ["trade", "unit", "currency", "rate"]
        else: # equipment
            headers = ["Name", "Unit", "Currency", "Rate"]
            keys = ["name", "unit", "currency", "rate"]
            
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setRowCount(len(items))
        
        self.full_data = []
        for r, row in enumerate(items):
            item_dict = dict(row)
            self.full_data.append(item_dict)
            for c, key in enumerate(keys):
                val = item_dict.get(key, "")
                if isinstance(val, float):
                    val = f"{val:,.2f}"
                self.table.setItem(r, c, QTableWidgetItem(str(val)))
                
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setStretchLastSection(True)

    def filter_table(self, text):
        query = text.lower()
        for row in range(self.table.rowCount()):
            match = False
            for col in range(self.table.columnCount()):
                if query in self.table.item(row, col).text().lower():
                    match = True
                    break
            self.table.setRowHidden(row, not match)

    def accept(self):
        row = self.table.currentRow()
        if row >= 0:
            self.selected_item = self.full_data[row]
            super().accept()
        else:
            QMessageBox.warning(self, "Selection Error", "Please select an item.")

class RateSelectionDialog(QDialog):
    """Dialog to select a rate build-up from the rates database."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Rate from Database")
        self.setMinimumSize(700, 400)
        self.selected_rate_id = None
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Search
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Type to filter...")
        self.search_input.textChanged.connect(self.filter_table)
        search_layout.addWidget(self.search_input)
        layout.addLayout(search_layout)
        
        # Table
        self.table = QTableWidget()
        self.db_manager = DatabaseManager("construction_rates.db")
        self.load_data()
        
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setDefaultSectionSize(22)
        self.table.doubleClicked.connect(self.accept)
        
        layout.addWidget(self.table)

    def load_data(self):
        rates = self.db_manager.get_rates_data()
        headers = ["Rate Code", "Description", "Unit", "Base Curr", "Net Rate", "Gross Rate"]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setRowCount(0)
        
        self.full_data = [] # To hold (db_id, row_data)
        for r, row_data in enumerate(rates):
            self.table.insertRow(r)
            self.full_data.append((row_data['id'], row_data))
            
            items = [
                row_data['rate_code'], row_data['project_name'], row_data['unit'], row_data['currency'], 
                f"{row_data['net_total']:,.2f}" if row_data['net_total'] is not None else "0.00",
                f"{row_data['grand_total']:,.2f}" if row_data['grand_total'] is not None else "0.00"
            ]
            for c, val in enumerate(items):
                item = QTableWidgetItem(str(val))
                self.table.setItem(r, c, item)
                
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setStretchLastSection(True)

    def filter_table(self, text):
        query = text.lower()
        for row in range(self.table.rowCount()):
            match = False
            for col in range(self.table.columnCount()):
                val = self.table.item(row, col)
                if val and query in val.text().lower():
                    match = True
                    break
            self.table.setRowHidden(row, not match)

    def accept(self):
        row = self.table.currentRow()
        if row >= 0:
            self.selected_rate_id = self.full_data[row][0]
            super().accept()
        else:
            QMessageBox.warning(self, "Selection Error", "Please select a rate.")
