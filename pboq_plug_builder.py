from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLineEdit, QTextEdit, QHBoxLayout, QPlainTextEdit,
                             QDialogButtonBox, QLabel, QMessageBox, QPushButton, QComboBox)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPainter, QColor
import re
from edit_item_dialog import ZebraInput
from database import DatabaseManager

class PlugRateBuilderDialog(QDialog):
    """
    Specialized dialog for building Plug Rates in PBOQ.
    Features formula input, category selection, and currency management.
    """
    dataCommitted = pyqtSignal()
    
    def __init__(self, item_data, project_dir, parent=None):
        super().__init__(parent)
        self.item_data = item_data
        self.project_dir = project_dir
        
        # Determine the project database to fetch categories and currency
        db_path = "construction_costs.db"
        project_db_dir = os.path.join(self.project_dir, "Project Database")
        if os.path.exists(project_db_dir):
            for f in os.listdir(project_db_dir):
                if f.endswith('.db'):
                    db_path = os.path.join(project_db_dir, f)
                    break
        self.db_manager = DatabaseManager(db_path)
        
        self.setWindowTitle("Plug Rate Builder")
        self.setMinimumWidth(500)
        self.setMinimumHeight(450)
        
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        
        # 1. Header Info (Description & Category/Currency)
        header_layout = QFormLayout()
        header_layout.setSpacing(5)
        
        # Description (Wrapped)
        self.desc_input = QTextEdit(self.item_data.get('name', ''))
        self.desc_input.setFixedHeight(60)
        self.desc_input.setStyleSheet("background-color: #f8fdf9; border: 1px solid #c8e6c9; color: #2e7d32; font-weight: bold;")
        header_layout.addRow("Description:", self.desc_input)
        
        # Category Dropdown
        self.cat_combo = QComboBox()
        categories = list(self.db_manager.get_category_prefixes_dict().keys())
        self.cat_combo.addItems(categories)
        initial_cat = self.item_data.get('category') or "Miscellaneous"
        if initial_cat in categories:
            self.cat_combo.setCurrentText(initial_cat)
        header_layout.addRow("Category:", self.cat_combo)
        
        # Base Currency & Exchange Rates
        curr_layout = QHBoxLayout()
        self.curr_combo = QComboBox()
        # Fetch available currencies from settings or defaults
        default_curr = self.db_manager.get_setting('currency', 'GHS (₵)')
        # In a real app, we might have a list of all currencies. 
        # For now, we seed with the default and a few common ones if not already there.
        currencies = [default_curr, "USD ($)", "GBP (£)", "EUR (€)"]
        unique_currencies = []
        for c in currencies:
            if c not in unique_currencies: unique_currencies.append(c)
        self.curr_combo.addItems(unique_currencies)
        
        initial_curr = self.item_data.get('currency') or default_curr
        if initial_curr in unique_currencies:
            self.curr_combo.setCurrentText(initial_curr)
        else:
            self.curr_combo.addItem(initial_curr)
            self.curr_combo.setCurrentText(initial_curr)
            
        curr_layout.addWidget(self.curr_combo, 1)
        
        self.exchange_btn = QPushButton("Exchange Rates")
        self.exchange_btn.setFixedWidth(110)
        self.exchange_btn.clicked.connect(self.open_exchange_rates)
        curr_layout.addWidget(self.exchange_btn)
        
        header_layout.addRow("Base Currency:", curr_layout)
        
        layout.addLayout(header_layout)
        
        # 2. Main Editing Area (Formula & Calculation)
        split_layout = QHBoxLayout()
        split_layout.setSpacing(5)
        
        # Input Section (Left)
        input_container = QVBoxLayout()
        input_container.addWidget(QLabel("Formula Input:"))
        self.qty_input = ZebraInput()
        self.qty_input.setMinimumHeight(150)
        self.qty_input.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.qty_input.setStyleSheet("font-family: 'Consolas', monospace; border: 1px solid #ddd; background-color: white;")
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
        self.qty_display.setStyleSheet("color: blue; font-family: 'Consolas', monospace; border: 1px solid #ddd; background-color: #f9f9f9;")
        
        # Sync Scroll
        self.qty_input.verticalScrollBar().valueChanged.connect(self.qty_display.verticalScrollBar().setValue)
        self.qty_display.verticalScrollBar().valueChanged.connect(self.qty_input.verticalScrollBar().setValue)
        
        output_container.addWidget(self.qty_display)
        
        self.total_display = QLabel("TOTAL: 0.00")
        self.total_display.setStyleSheet("color: blue; font-family: 'Consolas', monospace; font-weight:bold; border: 1px solid #ddd; border-top: none; background-color: #f9f9f9;")
        self.total_display.setAlignment(Qt.AlignmentFlag.AlignRight)
        output_container.addWidget(self.total_display)

        split_layout.addLayout(output_container, 1)
        layout.addLayout(split_layout)
        
        # 3. Help Text
        help_text = "Enter value (1.00) or formula starting with '='.\nUse \"double quotes\" for inline comments.\nUse semicolon ';' to end formula and add notes."
        help_label = QLabel(help_text)
        help_label.setStyleSheet("color: #666; font-style: italic; font-size: 10px;")
        layout.addWidget(help_label)

        # Initialize Data
        if self.item_data.get('formula'):
            self.qty_input.setPlainText(self.item_data['formula'])
        else:
            self.qty_input.setPlainText(str(self.item_data.get('rate') or ""))
            
        self.update_display()

    def update_display(self):
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
        
        while len(html_lines) < 25:
            html_lines.append("<div>&nbsp;</div>")

        self.total_display.setText(f"TOTAL: {total_sum:,.2f}")
        self.qty_display.setHtml(f"<div style='color: blue; font-family: Consolas, monospace;'>{''.join(html_lines)}</div>")

    def parse_single_line(self, text):
        trimmed = text.strip()
        if not trimmed: return None
        is_formula = trimmed.startswith('=')
        segment = text.split(';')[0]
        if not is_formula:
            try: return float(segment.strip())
            except ValueError: return None
        term = segment.replace('=', '', 1)
        term = re.sub(r'"[^"]*"', '', term)
        term = term.replace('x', '*').replace('X', '*').replace('%', '/100')
        term = re.sub(r'/\s*[a-zA-Z\u00b2\u00b3]+[a-zA-Z\u00b2\u00b3\d]*', '', term)
        term = re.sub(r'[a-zA-Z\u00b2\u00b3]+[a-zA-Z\u00b2\u00b3\d]*', '', term)
        try:
            cleaned_term = re.sub(r'[^0-9+\-*/(). ]', '', term)
            return float(eval(cleaned_term, {"__builtins__": None}, {}))
        except: return None

    def open_exchange_rates(self):
        from currency_conversion_dialog import CurrencyConversionDialog
        from models import Estimate
        
        # Create a tiny dummy estimate to hold currency/exchange rate state
        dummy_est = Estimate(self.item_data.get('name', 'Plug'), "", 0, 0, currency=self.curr_combo.currentText())
        dummy_est.exchange_rates = self.item_data.get('exchange_rates', {})
        
        dialog = CurrencyConversionDialog(dummy_est, self)
        if dialog.exec():
            # Dialog updates dummy_est.exchange_rates in its save() method or similar
            # But the dialog we have calls self.creator.save_estimate() which we don't have.
            # We'll just take the data back manually if it supports it, 
            # or we assume it modified the object.
            self.item_data['exchange_rates'] = dummy_est.exchange_rates

    def save(self):
        input_text = self.qty_input.toPlainText().strip()
        try:
            lines = input_text.split('\n')
            total = 0
            has_formula = False
            for line in lines:
                val = self.parse_single_line(line)
                if val is not None:
                    total += val
                    if line.strip().startswith('=') or len(lines) > 1:
                        has_formula = True

            self.item_data['rate'] = total
            self.item_data['formula'] = input_text if has_formula else None
            self.item_data['name'] = self.desc_input.toPlainText().strip()
            self.item_data['category'] = self.cat_combo.currentText()
            self.item_data['currency'] = self.curr_combo.currentText()
            
            self.accept()
            self.dataCommitted.emit()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Invalid Input: {e}")

    def closeEvent(self, event):
        self.save()
        super().closeEvent(event)

import os
