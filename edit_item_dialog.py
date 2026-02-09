from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLineEdit, QTextEdit, QHBoxLayout, QPlainTextEdit,
                             QDialogButtonBox, QLabel, QMessageBox)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QDoubleValidator, QPainter, QColor
import re

class ZebraInput(QPlainTextEdit):
    """A text editor that draws alternating row background colors."""
    def paintEvent(self, event):
        painter = QPainter(self.viewport())
        color_1 = QColor("#ffffff")
        color_2 = QColor("#f2f7ff") 
        
        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())
        
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible():
                color = color_2 if block_number % 2 == 1 else color_1
                painter.fillRect(0, top, self.viewport().width(), int(self.blockBoundingRect(block).height()), color)
            
            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            block_number += 1
            
        super().paintEvent(event)

class EditItemDialog(QDialog):
    """
    Dialog for editing the quantity/hours of a cost item using a formula or direct value.
    Supports basic arithmetic formulas starting with '='.
    """
    def __init__(self, item_data, item_type, estimate_currency, parent=None):
        super().__init__(parent)
        self.item_data = item_data
        self.item_type = item_type
        self.original_rate = item_data.get('unit_cost') if item_type == 'material' else item_data.get('rate')
        
        name = item_data.get('name') or item_data.get('trade') or "Unknown Item"
        self.setWindowTitle(f"Edit {item_type.capitalize()}")
        self.setMinimumWidth(900)
        self.setMinimumHeight(550)
        
        self._init_ui(name)

    def _init_ui(self, name):
        layout = QVBoxLayout(self)
        
        # Header Info
        form_layout = QFormLayout()
        self.name_display = QLineEdit(name)
        self.name_display.setReadOnly(True)
        self.name_display.setStyleSheet("background-color: #f5f5f5; color: #333;")
        form_layout.addRow("Item Name:", self.name_display)
        
        # Splitter Layout
        split_layout = QHBoxLayout()
        
        # Input Section
        input_container = QVBoxLayout()
        input_container.addWidget(QLabel("Formula Input:"))
        self.qty_input = ZebraInput()
        self.qty_input.setMinimumHeight(300)
        self.qty_input.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.qty_input.setStyleSheet("padding: 5px; font-family: Consolas, monospace;")
        self.qty_input.setPlaceholderText("e.g. = (10 * 5) \"Wall A\";")
        self.qty_input.textChanged.connect(self.update_display)
        
        # Sync Scroll
        self.qty_display = QTextEdit()
        self.qty_input.verticalScrollBar().valueChanged.connect(self.qty_display.verticalScrollBar().setValue)
        
        input_container.addWidget(self.qty_input)
        split_layout.addLayout(input_container, 4)
        
        # Output Section
        output_container = QVBoxLayout()
        output_container.addWidget(QLabel("Calculation:"))
        self.qty_display.setMinimumHeight(300)
        self.qty_display.setReadOnly(True)
        self.qty_display.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.qty_display.setStyleSheet("color: blue; padding: 5px; font-family: Consolas, monospace; border: 1px solid #ddd; background-color: #f9f9f9;")
        self.qty_display.verticalScrollBar().valueChanged.connect(self.qty_input.verticalScrollBar().setValue)
        
        output_container.addWidget(self.qty_display)
        split_layout.addLayout(output_container, 1)
        
        form_layout.addRow(split_layout)
        
        # Help Text
        help_text = "Enter value or formula starting with '='.\nUse \"double quotes\" for inline comments.\nUse semicolon ';' to end formula and add notes."
        help_label = QLabel(help_text)
        help_label.setStyleSheet("color: gray; font-style: italic; font-size: 10pt;")
        form_layout.addRow("", help_label)
        
        layout.addLayout(form_layout)
        
        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        for button in buttons.buttons():
            button.setAutoDefault(False)
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # Initialize Data
        initial_qty = self.item_data.get('qty') if self.item_type == 'material' else self.item_data.get('hours')
        if self.item_data.get('formula'):
            self.qty_input.setPlainText(self.item_data['formula'])
        else:
            self.qty_input.setPlainText(str(initial_qty))

    def parse_single_line(self, text):
        """Parses a single line of formula text."""
        if not text.strip().startswith('='):
            return None
            
        # Remove '=' and comments
        term = text.replace('=', '', 1).split(';')[0]
        term = re.sub(r'"[^"]*"', '', term) # Remove quoted comments
        
        # Normalize and sanitize
        term = term.replace('x', '*').replace('X', '*').replace('%', '/100')
        term = re.sub(r'[a-zA-Z]+', '', term) # Remove letters (units)
        
        try:
            # Safe(ish) eval
            return float(eval(term, {"__builtins__": None}, {}))
        except:
            return None

    def update_display(self):
        """Updates the calculated display based on input."""
        full_text = self.qty_input.toPlainText()
        lines = full_text.split('\n')
        
        html_lines = []
        total_sum = 0
        
        for line in lines:
            val = self.parse_single_line(line)
            if val is not None:
                total_sum += val
                html_lines.append(f"<div>= {val:,.2f}</div>")
            else:
                html_lines.append("<div>&nbsp;</div>")
        
        # Pad lines to match input
        while len(html_lines) < 18:
            html_lines.append("<div>&nbsp;</div>")

        if total_sum > 0:
            html_lines.append(f"<div><b>TOTAL: {total_sum:,.2f}</b></div>")
            
        self.qty_display.setHtml(f"<div style='color: blue; font-family: Consolas, monospace;'>{''.join(html_lines)}</div>")

    def save(self):
        input_text = self.qty_input.toPlainText().strip()
        try:
            # Re-calculate total
            lines = input_text.split('\n')
            total = 0
            has_formula = False
            
            for line in lines:
                val = self.parse_single_line(line)
                if val is not None:
                    total += val
                    has_formula = True
                elif not has_formula and line.replace('.','',1).isdigit():
                    # Fallback for simple number
                    total = float(line)

            # Update Item Data
            qty_key = 'qty' if self.item_type == 'material' else 'hours'
            self.item_data[qty_key] = total
            self.item_data['formula'] = input_text if has_formula else None
            
            rate = self.original_rate or 0.0
            self.item_data['total'] = total * rate
            
            self.accept()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Invalid Input: {e}")
