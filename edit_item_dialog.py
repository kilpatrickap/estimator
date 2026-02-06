from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLineEdit, QTextEdit, QHBoxLayout,
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
        
        # Splitter for Side-by-Side View
        split_layout = QHBoxLayout()
        
        # Left: Input
        input_container = QVBoxLayout()
        input_container.addWidget(QLabel("Formula Input:"))
        self.qty_input = QTextEdit()
        self.qty_input.setMinimumHeight(300)
        self.qty_input.setAcceptRichText(False)
        self.qty_input.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.qty_input.setStyleSheet("padding: 5px; font-family: Consolas, monospace;")
        self.qty_input.setPlaceholderText("e.g. = (10 * 5) \"Wall A\" ;")
        input_container.addWidget(self.qty_input)
        split_layout.addLayout(input_container, 4) # 80% width
        
        # Right: Output Display
        output_container = QVBoxLayout()
        output_container.addWidget(QLabel("Calculation:"))
        self.qty_display = QTextEdit()
        self.qty_display.setMinimumHeight(300)
        self.qty_display.setReadOnly(True)
        self.qty_display.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.qty_display.setStyleSheet("color: blue; padding: 5px; font-family: Consolas, monospace; border: 1px solid #ddd; background-color: #f9f9f9;")
        output_container.addWidget(self.qty_display)
        split_layout.addLayout(output_container, 1) # 20% width
        
        # Sync Scrolling
        self.qty_input.verticalScrollBar().valueChanged.connect(self.qty_display.verticalScrollBar().setValue)
        self.qty_display.verticalScrollBar().valueChanged.connect(self.qty_input.verticalScrollBar().setValue)
        
        # Connect Update
        self.qty_input.textChanged.connect(self.update_display)
        
        form_layout.addRow(split_layout)
        
        initial_qty = item_data.get('qty') if item_type == 'material' else item_data.get('hours')
        
        # Show formula if exists, otherwise show value
        if item_data.get('formula'):
            self.qty_input.setPlainText(item_data['formula'])
        else:
            self.qty_input.setPlainText(f"{initial_qty}")
        help_text = "Enter value or formula starting with '='.\nUse \"double quotes\" for inline comments.\nUse semicolon ';' to end formula and add notes."
        help_label = QLabel(help_text)
        help_label.setStyleSheet("color: gray; font-style: italic; font-size: 10pt;")
        form_layout.addRow("", help_label)
        
        # Increase window size
        self.setMinimumWidth(900)
        self.setMinimumHeight(550)
        
        layout.addLayout(form_layout)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        # Ensure buttons don't steal 'Enter' from the text area
        for button in buttons.buttons():
            button.setAutoDefault(False)
            button.setDefault(False)
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def parse_single_line(self, text):
        """Helper to parse a single line formula"""
        import re
        if not text.strip().startswith('='):
            return None
            
        # 1. Remove leading '='
        text = text.replace('=', '', 1)
            
        # 2. Split by ';' and take the first part (the formula)
        text = text.split(';')[0]
            
        # 3. Extract comments and replace with placeholders to protect content
        comments = []
        def replace_comment(match):
            comments.append(match.group(0))
            return f"__COMMENT_{len(comments)-1}__"
            
        # Replace "comments" with placeholders
        temp_text = re.sub(r'"[^"]*"', replace_comment, text)
        
        # 4. Apply formatting (x -> *, % -> /100) only to non-comment parts
        clean_text = temp_text.replace('x', '*').replace('X', '*').replace('%', '/100')
        
        # 5. Remove the comment placeholders completely
        clean_text = re.sub(r'__COMMENT_\d+__', '', clean_text)
        
        # 6. Remove unit-like patterns from the remaining formula
        clean_text = re.sub(r'\/[a-zA-Z]+', '', clean_text)
        clean_text = re.sub(r'[a-zA-Z]+[0-9]*', '', clean_text)
        
        try:
            return float(eval(clean_text, {"__builtins__": None}, {}))
        except:
            return None

    def update_display(self):
        full_text = self.qty_input.toPlainText()
        lines = full_text.split('\n')
        
        display_lines = []
        total_sum = 0
        
        for line in lines:
            # Parse strictly
            result = self.parse_single_line(line)
            
            if result is not None:
                total_sum += result
                # Show result prefixed with '='
                display_lines.append(f"= {result:,.2f}")
            else:
                # Empty line or comment-only line
                display_lines.append("")
                
        # Fill rest with empty lines to match input length first
        while len(display_lines) < len(lines):
            display_lines.append("")
            
        # Push TOTAL to the bottom of the view (leaving 1 line space at the very bottom)
        while len(display_lines) < 18:
            display_lines.append("")

        # Create HTML for bolding and color
        html_lines = []
        for line in display_lines:
            if line:
                html_lines.append(f"<div>{line}</div>")
            else:
                html_lines.append("<div>&nbsp;</div>")

        if total_sum > 0:
            html_lines.append(f"<div><b>TOTAL: {total_sum:,.2f}</b></div>")
            
        self.qty_display.setHtml(f"<div style='color: blue; font-family: Consolas, monospace;'>{''.join(html_lines)}</div>")

    def parse_formula(self, text):
        # We need to sum up all lines now
        lines = text.split('\n')
        total = 0
        for line in lines:
            res = self.parse_single_line(line)
            if res: total += res
            elif not res and line.strip().replace('.','',1).isdigit():
                 try: total += float(line)
                 except: pass
        
        if total == 0 and text.strip():
             # Fallback for single line simple number
             try: return float(text)
             except: pass
             
        return total

    def save(self):
        input_text = self.qty_input.toPlainText().strip()
        
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
