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
        self.setMinimumSize(500, 300)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)
        
        info_label = QLabel(f"Base Currency: <b>{self.estimate.currency}</b>")
        layout.addWidget(info_label)
        
        description = QLabel("List of currencies used in this estimate. Set the exchange rate for each to convert to base currency.")
        description.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(description)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Currency", "Conversion Rate", "Operator", "Effective Date"])
        
        # Columns 1, 2, 3 contain widgets, so we set widths manually
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        
        self.table.setColumnWidth(1, 150) # Conversion Rate
        self.table.setColumnWidth(2, 180) # Operator
        
        self.table.verticalHeader().setDefaultSectionSize(30)
        layout.addWidget(self.table)

        self.populate_table()

        self.populate_table()
        
        # Connect table changes to state change signal if we had one
        # For now, we'll just rely on the global save triggering save()
        
    def save(self):
        self.save_rates()
        # Find the parent windows to trigger a refresh and database save
        p = self.parent()
        while p:
            if hasattr(p, 'refresh_view'):
                p.refresh_view()
                # Persist to database via parent's save method
                if hasattr(p, 'save_estimate'):
                    p.save_estimate()
                elif hasattr(p, 'save_changes'):
                    p.save_changes()
                break
            p = p.parent()
        return True

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
        self.populate_table() # Refresh table to ensure values match internal state

