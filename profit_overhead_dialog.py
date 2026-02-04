from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLineEdit, 
                             QDialogButtonBox, QLabel, QMessageBox)
from PyQt6.QtGui import QDoubleValidator

class ProfitOverheadDialog(QDialog):
    def __init__(self, estimate, parent=None):
        super().__init__(parent)
        self.estimate = estimate
        self.setWindowTitle("Profit & Overheads")
        self.setMinimumWidth(350)

        layout = QVBoxLayout(self)
        
        info_label = QLabel(f"Settings for Project: <b>{self.estimate.project_name}</b>")
        layout.addWidget(info_label)

        form_layout = QFormLayout()

        # Overhead
        self.overhead_input = QLineEdit()
        pct_validator = QDoubleValidator(0.0, 100.0, 2)
        pct_validator.setNotation(QDoubleValidator.Notation.StandardNotation)
        self.overhead_input.setValidator(pct_validator)
        self.overhead_input.setText(f"{self.estimate.overhead_percent:.2f}")

        # Profit
        self.profit_input = QLineEdit()
        self.profit_input.setValidator(pct_validator)
        self.profit_input.setText(f"{self.estimate.profit_margin_percent:.2f}")

        form_layout.addRow("Overhead (%):", self.overhead_input)
        form_layout.addRow("Profit (%):", self.profit_input)

        layout.addLayout(form_layout)

        # Help text
        help_text = QLabel("Changes applied here only affect this specific estimate.")
        help_text.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(help_text)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.save_values)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def save_values(self):
        try:
            overhead = float(self.overhead_input.text())
            profit = float(self.profit_input.text())
            
            self.estimate.overhead_percent = overhead
            self.estimate.profit_margin_percent = profit
            
            self.accept()
        except ValueError:
            QMessageBox.warning(self, "Invalid Input", "Please enter valid numeric values for Overhead and Profit.")
