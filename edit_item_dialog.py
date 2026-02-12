from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLineEdit, QTextEdit, QHBoxLayout, QPlainTextEdit,
                             QDialogButtonBox, QLabel, QMessageBox, QPushButton)
from PyQt6.QtCore import Qt, pyqtSignal
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
    Dialog for editing the quantity/hours OR price/rate of a cost item using a formula.
    Supports basic arithmetic formulas starting with '='.
    """
    stateChanged = pyqtSignal()
    dataCommitted = pyqtSignal()
    
    def __init__(self, item_data, item_type, estimate_currency, parent=None, is_library=False, is_modal=True):
        super().__init__(parent)
        self.item_data = item_data
        self.item_type = item_type
        self.is_library = is_library
        self.is_modal = is_modal
        
        # Determine target key and original rate
        if is_library:
            self.target_key = 'price' if item_type == 'materials' else ('amount' if item_type == 'indirect_costs' else 'rate')
            self.original_rate = None # Not needed for library Price/Rate editing
        else:
            self.target_key = 'qty' if item_type == 'material' else 'hours'
            self.original_rate = item_data.get('unit_cost') if item_type == 'material' else item_data.get('rate')
        
        name = item_data.get('name') or item_data.get('trade') or item_data.get('description') or "Unknown Item"
        title_prefix = "Edit" if not is_library else "Set Price/Rate for"
        self.setWindowTitle(f"{title_prefix} {item_type.capitalize()}")
        self.setMinimumWidth(400)
        self.setMinimumHeight(350)
        
        self._init_ui(name)

    def _init_ui(self, name):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(2)
        
        # Header Info
        header_layout = QFormLayout()
        self.name_display = QLineEdit(name)
        self.name_display.setReadOnly(True)
        self.name_display.setStyleSheet("background-color: #f8fdf9; border: 1px solid #c8e6c9; color: #2e7d32; font-weight: bold; padding: 2px;")
        header_layout.addRow("Item Name:", self.name_display)
        layout.addLayout(header_layout)
        
        # Main Editing Area
        split_layout = QHBoxLayout()
        split_layout.setSpacing(2)
        
        # Input Section (Left)
        input_container = QVBoxLayout()
        input_container.addWidget(QLabel("Formula Input:"))
        self.qty_input = ZebraInput()
        self.qty_input.setMinimumHeight(150)
        self.qty_input.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.qty_input.setStyleSheet("padding: 4px; font-family: 'Consolas', monospace; font-size: 9pt; border: 1px solid #ddd; background-color: white;")
        self.qty_input.setPlaceholderText("e.g. = (10 * 5) \"Notes\";")
        self.qty_input.textChanged.connect(self.update_display)
        input_container.addWidget(self.qty_input)
        split_layout.addLayout(input_container, 4)
        
        # Output Section (Right)
        output_container = QVBoxLayout()
        output_container.addWidget(QLabel("Calculation:"))
        self.qty_display = QTextEdit()
        self.qty_display.setMinimumHeight(150)
        self.qty_display.setReadOnly(True)
        self.qty_display.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.qty_display.setStyleSheet("color: blue; padding: 4px; font-family: 'Consolas', monospace; font-size: 9pt; border: 1px solid #ddd; background-color: #f9f9f9;")
        
        # Sync Scroll
        self.qty_input.verticalScrollBar().valueChanged.connect(self.qty_display.verticalScrollBar().setValue)
        self.qty_display.verticalScrollBar().valueChanged.connect(self.qty_input.verticalScrollBar().setValue)
        
        output_container.addWidget(self.qty_display)
        
        self.total_display = QLabel("TOTAL: 0.00")
        self.total_display.setStyleSheet("color: blue; font-family: 'Consolas', monospace; font-size: 10pt; font-weight:bold; padding: 2px; border: 1px solid #ddd; border-top: none; background-color: #f9f9f9;")
        self.total_display.setAlignment(Qt.AlignmentFlag.AlignRight)
        output_container.addWidget(self.total_display)

        split_layout.addLayout(output_container, 1)
        
        layout.addLayout(split_layout)
        
        # Help Text
        help_text = "Enter value (1.00) or formula starting with '='.\nUse \"double quotes\" for inline comments.\nUse semicolon ';' to end formula and add notes."
        help_label = QLabel(help_text)
        help_label.setStyleSheet("color: #666; font-style: italic; font-size: 9pt;")
        layout.addWidget(help_label)
        
        # Buttons removed as per user request. Changes are auto-saved on close.
        pass

        # Initialize Data
        initial_val = self.item_data.get(self.target_key)
        if self.item_data.get('formula'):
            self.qty_input.setPlainText(self.item_data['formula'])
        else:
            self.qty_input.setPlainText(str(initial_val or ""))
            
        # Connect internal undo/redo state changes to update global toolbar
        self.qty_input.undoAvailable.connect(lambda: self.stateChanged.emit())
        self.qty_input.redoAvailable.connect(lambda: self.stateChanged.emit())

    def undo(self):
        self.qty_input.undo()
        
    def redo(self):
        self.qty_input.redo()

    def parse_single_line(self, text):
        """Parses a single line of formula text."""
        if not text.strip().startswith('='):
            return None
            
        # Remove '=' and comments
        term = text.split(';')[0].replace('=', '', 1)
        term = re.sub(r'"[^"]*"', '', term) # Remove quoted comments
        
        # Normalize and sanitize
        term = term.replace('x', '*').replace('X', '*').replace('%', '/100')
        
        # 1. Remove "per" units with slashes (e.g., /hr, /day, /m3)
        term = re.sub(r'/[a-zA-Z]+\d*', '', term)
        
        # 2. Remove remaining alphanumeric units (e.g., hrs, m3, pcs)
        term = re.sub(r'[a-zA-Z]+\d*', '', term)
        
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
        
        # Pad lines to ensure sync scroll looks okay
        while len(html_lines) < 25:
            html_lines.append("<div>&nbsp;</div>")

        self.total_display.setText(f"TOTAL: {total_sum:,.2f}")
            
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
                elif not has_formula and line.strip().replace('.','',1).isdigit():
                    # Fallback for simple number if no formulas present at all
                    total = float(line.strip())

            # Update Item Data
            self.item_data[self.target_key] = total
            self.item_data['formula'] = input_text if has_formula else None
            
            if not self.is_library:
                rate = self.original_rate or 0.0
                self.item_data['total'] = total * rate
            
            if self.is_modal:
                self.accept()
            self.dataCommitted.emit()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Invalid Input: {e}")
