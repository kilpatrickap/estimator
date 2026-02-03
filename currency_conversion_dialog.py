from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, 
                             QTableWidgetItem, QHeaderView, QDateEdit, QLineEdit,
                             QPushButton, QLabel, QDialogButtonBox, QMessageBox, QComboBox)
from PyQt6.QtCore import QDate, Qt
from PyQt6.QtGui import QDoubleValidator
from database import DatabaseManager

class CurrencyConversionDialog(QDialog):
    def __init__(self, estimate, parent=None):
        super().__init__(parent)
        self.estimate = estimate
        self.db_manager = DatabaseManager()
        self.setWindowTitle(f"Exchange Rates: {estimate.project_name}")
        self.setMinimumSize(600, 400)

        layout = QVBoxLayout(self)
        
        info_label = QLabel(f"Base Currency: <b>{self.estimate.currency}</b>")
        layout.addWidget(info_label)
        
        description = QLabel("List of currencies used in this estimate. Set the exchange rate for each to convert to base currency.")
        description.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(description)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Currency", "Conversion Rate", "Operator", "Effective Date"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        self.populate_table()

        # Buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.save_rates)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def get_used_currencies(self):
        """Finds all unique currencies used in the estimate tasks, excluding the base currency."""
        used = set()
        for task in self.estimate.tasks:
            for m in task.materials:
                if 'currency' in m and m['currency'] != self.estimate.currency:
                    used.add(m['currency'])
            for l in task.labor:
                if 'currency' in l and l['currency'] != self.estimate.currency:
                    used.add(l['currency'])
            for e in task.equipment:
                if 'currency' in e and e['currency'] != self.estimate.currency:
                    used.add(e['currency'])
        return sorted(list(used))

    def populate_table(self):
        currencies = self.get_used_currencies()
        self.table.setRowCount(len(currencies))
        
        for row, curr in enumerate(currencies):
            # Currency Name
            curr_item = QTableWidgetItem(curr)
            curr_item.setFlags(curr_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 0, curr_item)

            # Rate Input
            rate_data = self.estimate.exchange_rates.get(curr, {'rate': 1.0, 'date': QDate.currentDate().toString("yyyy-MM-dd"), 'operator': '*'})
            
            rate_edit = QLineEdit(str(rate_data['rate']))
            validator = QDoubleValidator(0.0001, 1000000.0, 4)
            validator.setNotation(QDoubleValidator.Notation.StandardNotation)
            rate_edit.setValidator(validator)
            self.table.setCellWidget(row, 1, rate_edit)

            # Operator Combo
            op_combo = QComboBox()
            op_combo.addItem("Multiply (*)", "*")
            op_combo.addItem("Divide (/)", "/")
            
            current_op = rate_data.get('operator', '*')
            index = 0 if current_op == '*' else 1
            op_combo.setCurrentIndex(index)
            self.table.setCellWidget(row, 2, op_combo)

            # Date Input
            date_edit = QDateEdit()
            date_edit.setCalendarPopup(True)
            date_edit.setDisplayFormat("dd-MM-yy")
            date_val = QDate.fromString(rate_data['date'], "yyyy-MM-dd")
            if date_val.isValid():
                date_edit.setDate(date_val)
            else:
                date_edit.setDate(QDate.currentDate())
            self.table.setCellWidget(row, 3, date_edit)

    def save_rates(self):
        new_rates = {}
        for row in range(self.table.rowCount()):
            curr = self.table.item(row, 0).text()
            rate_edit = self.table.cellWidget(row, 1)
            op_combo = self.table.cellWidget(row, 2)
            date_edit = self.table.cellWidget(row, 3)
            
            try:
                rate = float(rate_edit.text())
            except ValueError:
                rate = 1.0
            
            operator = op_combo.currentData()
            date_str = date_edit.date().toString("yyyy-MM-dd")
            new_rates[curr] = {'rate': rate, 'date': date_str, 'operator': operator}
        
        self.estimate.exchange_rates = new_rates
        self.accept()

