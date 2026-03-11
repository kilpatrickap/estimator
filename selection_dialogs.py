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
        self.main_window = getattr(parent, 'main_window', None)
        self.setWindowTitle("Select Rate from Database")
        self.setMinimumSize(850, 450)
        self.selected_rate_id = None
        self.selected_db_path = None
        self.is_combined = False
        self.db_manager = None
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)
        
        # Header Section
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("Library(ies) :"))
        
        from PyQt6.QtWidgets import QComboBox
        self.library_combo = QComboBox()
        
        import os
        project_dir = ""
        if self.main_window:
            from database import DatabaseManager
            active_est = getattr(self.main_window, '_get_active_estimate_window', lambda: None)()
            if active_est and type(active_est).__name__ == "EstimateWindow":
                project_dir = os.path.dirname(active_est.db_path) if active_est.db_path else ""
                if project_dir and os.path.basename(project_dir) == "Project Database":
                    project_dir = os.path.dirname(project_dir)
            if not project_dir and hasattr(self.main_window, 'db_manager'):
                project_dir = self.main_window.db_manager.get_setting('last_project_dir', '')
                if project_dir and os.path.basename(project_dir) == "Project Database":
                    project_dir = os.path.dirname(project_dir)
                    
        if project_dir and os.path.exists(project_dir):
            lib_dir = os.path.join(project_dir, "Imported Library")
            if os.path.exists(lib_dir):
                for f in os.listdir(lib_dir):
                    if f.endswith('.db'):
                        self.library_combo.addItem(f, os.path.join(lib_dir, f))
                        
            pdb_dir = os.path.join(project_dir, "Project Database")
            if os.path.exists(pdb_dir):
                for f in os.listdir(pdb_dir):
                    if f.endswith('.db'):
                        self.library_combo.addItem(f"Project Database - {f}", os.path.join(pdb_dir, f))
                        break
                        
        if self.library_combo.count() == 0:
            if os.path.exists("construction_rates.db"):
                self.library_combo.addItem("Default Library", "construction_rates.db")
                
        self.library_combo.currentIndexChanged.connect(self._change_library)
        header_layout.addWidget(self.library_combo)
        
        self.combine_btn = QPushButton("Combine Libraries")
        self.combine_btn.setStyleSheet("padding: 4px 10px; font-weight: bold; background-color: #2e7d32; color: white;")
        self.combine_btn.clicked.connect(self._combine_libraries)
        header_layout.addWidget(self.combine_btn)
        
        header_layout.addStretch()
        
        header_layout.addWidget(QLabel("Search:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Type to filter...")
        self.search_input.setFixedWidth(250)
        self.search_input.textChanged.connect(self.filter_table)
        header_layout.addWidget(self.search_input)
        layout.addLayout(header_layout)
        
        # Table
        self.table = QTableWidget()
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
        
        if self.library_combo.count() > 0:
            from database import DatabaseManager
            self.db_manager = DatabaseManager(self.library_combo.currentData())
            self.load_data()

    def _change_library(self):
        self.is_combined = False
        self.combine_btn.setText("Combine Libraries")
        db_path = self.library_combo.currentData()
        if db_path:
            from database import DatabaseManager
            self.db_manager = DatabaseManager(db_path)
            self.load_data()

    def _combine_libraries(self):
        self.is_combined = not self.is_combined
        if self.is_combined:
            self.combine_btn.setText("Un-Combine Libraries")
        else:
            self.combine_btn.setText("Combine Libraries")
            db_path = self.library_combo.currentData()
            if db_path:
                from database import DatabaseManager
                self.db_manager = DatabaseManager(db_path)
        self.load_data()

    def load_data(self):
        if not self.db_manager and not self.is_combined:
            return
            
        headers = ["Library", "Rate Code", "Description", "Unit", "Base Curr", "Net Rate", "Gross Rate"]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setRowCount(0)
        
        all_rates = []
        from database import DatabaseManager
        
        if self.is_combined:
            for i in range(self.library_combo.count()):
                lib_name = self.library_combo.itemText(i)
                lib_path = self.library_combo.itemData(i)
                if lib_path:
                    db = DatabaseManager(lib_path)
                    rates = db.get_rates_data()
                    for r in rates:
                        if not isinstance(r, dict):
                            r = dict(r)
                        r['_library_name'] = lib_name
                        r['_library_path'] = lib_path
                        all_rates.append(r)
        else:
            if self.db_manager:
                rates = self.db_manager.get_rates_data()
                lib_name = self.library_combo.currentText()
                lib_path = self.library_combo.currentData()
                for r in rates:
                    if not isinstance(r, dict):
                        r = dict(r)
                    r['_library_name'] = lib_name
                    r['_library_path'] = lib_path
                    all_rates.append(r)
                
        self.full_data = [] # To hold (db_id, row_data, db_path)
        for r, row_data in enumerate(all_rates):
            self.table.insertRow(r)
            self.full_data.append((row_data['id'], row_data, row_data['_library_path']))
            
            items = [
                row_data.get('_library_name', ''),
                row_data.get('rate_code', ''), 
                row_data.get('project_name', ''), 
                row_data.get('unit', ''), 
                row_data.get('currency', ''), 
                f"{row_data.get('net_total', 0.0):,.2f}" if row_data.get('net_total') is not None else "0.00",
                f"{row_data.get('grand_total', 0.0):,.2f}" if row_data.get('grand_total') is not None else "0.00"
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
            self.selected_db_path = self.full_data[row][2]
            super().accept()
        else:
            QMessageBox.warning(self, "Selection Error", "Please select a rate.")
