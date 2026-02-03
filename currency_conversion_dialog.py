from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLineEdit, 
                             QDialogButtonBox, QLabel, QMessageBox, QDateEdit)
from PyQt6.QtCore import QDate
from PyQt6.QtGui import QDoubleValidator
from database import DatabaseManager

class CurrencyConversionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Currency Conversion")
        self.setMinimumWidth(400)
        self.db_manager = DatabaseManager()

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        # Selected Currency (Read-only, from settings)
        self.selected_currency = self.db_manager.get_setting('currency', 'GHS (₵)')
        self.currency_label = QLabel(self.selected_currency)
        self.currency_label.setStyleSheet("font-weight: bold; font-size: 14px;")

        # Conversion Rate
        self.rate_input = QLineEdit()
        self.rate_input.setPlaceholderText("e.g. 15.5")
        validator = QDoubleValidator(0.0001, 10000.0, 4)
        validator.setNotation(QDoubleValidator.Notation.StandardNotation)
        self.rate_input.setValidator(validator)
        
        # Load saved rate
        saved_rate = self.db_manager.get_setting('conversion_rate', '1.00')
        self.rate_input.setText(str(saved_rate))

        # Date
        self.date_input = QDateEdit()
        self.date_input.setCalendarPopup(True)
        self.date_input.setDisplayFormat("dd-MM-yy")
        
        saved_date = self.db_manager.get_setting('conversion_date')
        if saved_date:
            self.date_input.setDate(QDate.fromString(saved_date, "yyyy-MM-dd"))
        else:
            self.date_input.setDate(QDate.currentDate())

        form_layout.addRow("Selected Currency:", self.currency_label)
        form_layout.addRow("Conversion Rate:", self.rate_input)
        form_layout.addRow("Date:", self.date_input)

        layout.addLayout(form_layout)

        # Buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.save_data)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def save_data(self):
        try:
            rate_val = float(self.rate_input.text())
            date_val = self.date_input.date().toString("yyyy-MM-dd")

            self.db_manager.set_setting('conversion_rate', rate_val)
            self.db_manager.set_setting('conversion_date', date_val)

            QMessageBox.information(self, "Success", "Currency conversion details saved.")
            self.accept()
        except ValueError:
            QMessageBox.warning(self, "Error", "Please enter a valid numeric conversion rate.")
