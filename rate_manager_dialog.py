from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, 
                             QTableWidgetItem, QHeaderView, QLabel, QLineEdit, QPushButton, QWidget)
from PyQt6.QtCore import Qt
from database import DatabaseManager

class RateManagerDialog(QDialog):
    """Dialog for viewing and managing saved rates in construction_rates.db."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manage Rate Database")
        self.setMinimumSize(1000, 600)
        self.db_manager = DatabaseManager()
        
        self._init_ui()
        self.load_rates()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        # Header Section
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        main_label = QLabel("Archived Project Rates")
        main_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #2e7d32;")
        header_layout.addWidget(main_label)
        header_layout.addStretch()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by Rate-ID or Description...")
        self.search_input.setFixedWidth(400)
        self.search_input.textChanged.connect(self.filter_rates)
        header_layout.addWidget(self.search_input)
        layout.addWidget(header_widget)

        # Table
        self.table = QTableWidget()
        headers = ["Rate-ID", "Description", "Unit", "Base Currency", "Rate", "Date", "Remarks"]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        
        # Responsive Header Sizing
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        # Set specific columns to stretch/resize
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch) # Description
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch) # Remarks
        
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setWordWrap(True)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setStyleSheet("QTableWidget { border: 1px solid #e0e0e0; border-radius: 8px; }")
        
        layout.addWidget(self.table)

        # Bottom Actions
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton("Close Manager")
        close_btn.setMinimumHeight(40)
        close_btn.setFixedWidth(150)
        close_btn.clicked.connect(self.close)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    def load_rates(self):
        """Loads data from construction_rates.db into the table."""
        rates = self.db_manager.get_rates_data()
        self.table.setRowCount(0)
        
        for row_idx, row_data in enumerate(rates):
            self.table.insertRow(row_idx)
            for col_idx, data in enumerate(row_data):
                # Format Rate as currency if it's the 4th index (grand_total)
                if col_idx == 4:
                    display_text = f"{float(data):,.2f}" if data is not None else "0.00"
                else:
                    display_text = str(data) if data is not None else ""
                
                item = QTableWidgetItem(display_text)
                if col_idx in [0, 4]: # Rate ID and Price bold
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                
                if col_idx == 4: # Align rate to right
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                
                self.table.setItem(row_idx, col_idx, item)
        
        # Initial fit for non-stretched columns
        for i in [0, 2, 3, 5]:
            self.table.resizeColumnToContents(i)

    def filter_rates(self, text):
        query = text.lower()
        for row in range(self.table.rowCount()):
            id_match = query in self.table.item(row, 0).text().lower()
            desc_match = query in self.table.item(row, 1).text().lower()
            self.table.setRowHidden(row, not (id_match or desc_match))
