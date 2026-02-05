from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLineEdit, 
                             QDialogButtonBox, QLabel, QMessageBox, QComboBox, QSpacerItem, QSizePolicy)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QDoubleValidator
import re

class EditItemDialog(QDialog):
    def __init__(self, item_data, item_type, estimate_currency, parent=None):
        super().__init__(parent)
        self.item_data = item_data
        self.item_type = item_type
        # Store initial rate and currency since we won't edit them
        self.original_rate = item_data.get('unit_cost') if item_type == 'material' else item_data.get('rate')
        self.original_currency = item_data.get('currency', estimate_currency)
        
        name = item_data.get('name') or item_data.get('trade') or "Unknown Item"
        self.setWindowTitle(f"Edit {item_type.capitalize()}:")
        self.setMinimumWidth(350)
        
        layout = QVBoxLayout(self)
        
        form_layout = QFormLayout()
        form_layout.setSpacing(15)
        
        # Name (ReadOnly)
        self.name_display = QLineEdit(name)
        self.name_display.setReadOnly(True)
        self.name_display.setStyleSheet("background-color: #f5f5f5; color: #333;")
        form_layout.addRow("Item Name:", self.name_display)
        
        # Setup Validator
        double_validator = QDoubleValidator(0.0, 100000000.0, 4)
        double_validator.setNotation(QDoubleValidator.Notation.StandardNotation)
        
        # 1. Quantity / Hours
        qty_label = "Output : "
        self.qty_input = QLineEdit()
        # Removed validator to allow formula input
        
        initial_qty = item_data.get('qty') if item_type == 'material' else item_data.get('hours')
        
        # Show formula if exists, otherwise show value
        if item_data.get('formula'):
            self.qty_input.setText(item_data['formula'])
        else:
            self.qty_input.setText(f"{initial_qty}")
        form_layout.addRow(qty_label, self.qty_input)
        
        layout.addLayout(form_layout)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def parse_formula(self, text):
        # 1. Remove leading '='
        if text.startswith('='):
            text = text[1:]
            
        # 2. formatting: replace x/X with *
        clean_text = text.replace('x', '*').replace('X', '*').replace('%', '/100')
        
        # 3. Remove unit-like patterns
        # Remove /text (e.g. /hr, /day)
        clean_text = re.sub(r'\/[a-zA-Z]+', '', clean_text)
        # Remove text+numbers (e.g. m3, hrs, kg)
        clean_text = re.sub(r'[a-zA-Z]+[0-9]*', '', clean_text)
        
        try:
            # Eval the cleaned math string
            # explicit conversion to float to ensure result is numeric
            return float(eval(clean_text, {"__builtins__": None}, {}))
        except Exception:
            raise ValueError(f"Could not parse formula: {text}")

    def save(self):
        input_text = self.qty_input.text().strip()
        
        try:
            if input_text.startswith('='):
                qty = self.parse_formula(input_text)
                # Store the formula so it can be shown again
                self.item_data['formula'] = input_text
            else:
                qty = float(input_text)
                # Clear formula if user overwrote with specific number
                if 'formula' in self.item_data:
                    del self.item_data['formula']

            rate = self.original_rate or 0.0
            
            # Commit changes to the dictionary
            if self.item_type == 'material':
                self.item_data['qty'] = qty
                # We don't update unit_cost or unit as they are not visible/editable
            else:
                self.item_data['hours'] = qty
                # We don't update rate as it is not visible/editable
                
            # Recalculate total based on new quantity and original rate
            self.item_data['total'] = qty * rate
            
            self.accept()
        except ValueError as e:
             QMessageBox.warning(self, "Invalid Input", f"Error: {str(e)}\nPlease enter a valid number or formula starting with '='.")
        except Exception as e:
             QMessageBox.warning(self, "Error", f"An unexpected error occurred: {str(e)}")
