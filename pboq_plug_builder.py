from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QTextEdit, QPlainTextEdit,
                             QLabel, QMessageBox, QPushButton, QComboBox, QFrame)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPainter, QColor
import re
import os
import json
import sqlite3
from edit_item_dialog import ZebraInput
from database import DatabaseManager

class PlugRateBuilderDialog(QDialog):
    """
    Compact builder for Plug Rates in PBOQ.
    Features automated Plug Rate Code generation based on category.
    """
    dataCommitted = pyqtSignal()
    
    def __init__(self, item_data, project_dir, pboq_file_path, parent=None):
        super().__init__(parent)
        self.item_data = item_data
        self.project_dir = project_dir
        self.pboq_file_path = pboq_file_path
        
        # CATEGORIES: Always pull from the global software database (construction_costs.db)
        # SETTINGS (Like Currency): Pull from the project-level Database if it exists.
        self.global_db = DatabaseManager()
        
        db_path = "construction_costs.db"
        project_db_dir = os.path.join(self.project_dir, "Project Database")
        if os.path.exists(project_db_dir):
            for f in os.listdir(project_db_dir):
                if f.lower().endswith('.db'):
                    db_path = os.path.join(project_db_dir, f)
                    break
        self.db_manager = DatabaseManager(db_path)
        
        self.setWindowTitle("Plug Rate Builder")
        self.setMinimumWidth(550)
        self.setMinimumHeight(350) 
        
        self.is_loading = True
        self._init_ui()
        
        # Override with existing code if available
        if self.item_data.get('code'):
            self.current_plug_code = self.item_data['code']
            self.code_label.setText(f"Code: {self.current_plug_code}")
        else:
            # Generate one if none exists
            self.is_loading = False
            self._on_category_changed(self.cat_combo.currentText())
            self.is_loading = True

        self.is_loading = False

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(2)

        # --- Row 0: Plug Rate Code Display ---
        code_top_row = QHBoxLayout()
        self.code_label = QLabel("Code: PR-MISC1A")
        self.code_label.setStyleSheet("font-weight: bold; color: #7b1fa2; background-color: #f3e5f5; border-radius: 4px; padding: 2px 6px; font-size: 11px;")
        code_top_row.addWidget(self.code_label)
        code_top_row.addStretch()
        layout.addLayout(code_top_row)

        # --- Row 1: Description + Unit ---
        desc_row = QHBoxLayout()
        desc_row.setSpacing(5)
        desc_row.addWidget(QLabel("Description:"))
        
        self.desc_input = QTextEdit(self.item_data.get('name', ''))
        self.desc_input.setReadOnly(True) 
        self.desc_input.setFixedHeight(44) 
        self.desc_input.setStyleSheet("""
            QTextEdit {
                background-color: #f5f5f5; 
                border: 1px solid #ddd; 
                color: blue; 
                font-weight: 600; 
                font-size: 11px;
            }
        """)
        desc_row.addWidget(self.desc_input, 1)
        
        unit = self.item_data.get('unit', '')
        if unit:
            unit_lbl = QLabel(f"Unit: {unit}")
            unit_lbl.setStyleSheet("font-weight: bold; color: #2e7d32; background: #e8f5e9; padding: 2px 5px; border-radius: 4px;")
            desc_row.addWidget(unit_lbl)
        
        layout.addLayout(desc_row)

        # --- Row 2: Category + Currency ---
        meta_row = QHBoxLayout()
        meta_row.setSpacing(10)
        
        meta_row.addWidget(QLabel("Category:"))
        self.cat_combo = QComboBox()
        self.prefixes = self.global_db.get_category_prefixes_dict()
        categories = list(self.prefixes.keys())
        self.cat_combo.addItems(categories)
        initial_cat = self.item_data.get('category') or "Miscellaneous"
        if initial_cat in categories:
            self.cat_combo.setCurrentText(initial_cat)
        self.cat_combo.setFixedHeight(22)
        self.cat_combo.currentTextChanged.connect(self._on_category_changed)
        meta_row.addWidget(self.cat_combo, 1)
        
        meta_row.addWidget(QLabel("Base-Currency:"))
        self.curr_combo = QComboBox()
        default_curr = self.db_manager.get_setting('currency', 'GHS (₵)')
        currencies = [default_curr, "USD ($)", "GBP (£)", "EUR (€)"]
        unique_currencies = []
        for c in currencies:
            if c not in unique_currencies: unique_currencies.append(c)
        self.curr_combo.addItems(unique_currencies)
        
        initial_curr = self.item_data.get('currency') or default_curr
        if initial_curr not in unique_currencies:
            self.curr_combo.addItem(initial_curr)
            self.curr_combo.setCurrentText(initial_curr)
        else:
            self.curr_combo.setCurrentText(initial_curr)
        self.curr_combo.setFixedHeight(22)
        meta_row.addWidget(self.curr_combo, 1)
        
        layout.addLayout(meta_row)

        # --- Row 3: Main Editing Area ---
        split_layout = QHBoxLayout()
        split_layout.setSpacing(5)
        
        input_container = QVBoxLayout()
        input_container.setSpacing(1)
        lbl_formula = QLabel("Formula Input:")
        lbl_formula.setStyleSheet("font-size: 10px; color: #666;")
        input_container.addWidget(lbl_formula)
        
        self.qty_input = ZebraInput()
        self.qty_input.setMinimumHeight(100)
        self.qty_input.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.qty_input.setStyleSheet("font-family: 'Consolas', monospace; border: 1px solid #ddd; background-color: white; font-size: 11px;")
        self.qty_input.setPlaceholderText("e.g. = (10 * 5) \"Notes\";")
        self.qty_input.textChanged.connect(self.update_display)
        input_container.addWidget(self.qty_input)
        split_layout.addLayout(input_container, 4)
        
        output_container = QVBoxLayout()
        output_container.setSpacing(1)
        lbl_calc = QLabel("Calculation:")
        lbl_calc.setStyleSheet("font-size: 10px; color: #666;")
        output_container.addWidget(lbl_calc)
        
        self.qty_display = QTextEdit()
        self.qty_display.setMinimumHeight(100)
        self.qty_display.setReadOnly(True)
        self.qty_display.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.qty_display.setStyleSheet("color: blue; font-family: 'Consolas', monospace; border: 1px solid #ddd; background-color: #f9f9f9; font-size: 11px;")
        
        self.qty_input.verticalScrollBar().valueChanged.connect(self.qty_display.verticalScrollBar().setValue)
        self.qty_display.verticalScrollBar().valueChanged.connect(self.qty_input.verticalScrollBar().setValue)
        
        output_container.addWidget(self.qty_display)
        
        self.total_display = QLabel("TOTAL: 0.00")
        self.total_display.setStyleSheet("color: blue; font-family: 'Consolas', monospace; font-weight:bold; border: 1px solid #ddd; border-top: none; background-color: #f9f9f9; padding-right: 5px;")
        self.total_display.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.total_display.setFixedHeight(22)
        output_container.addWidget(self.total_display)

        split_layout.addLayout(output_container, 1)
        layout.addLayout(split_layout)
        
        # Footer / Help (Compact)
        footer_layout = QHBoxLayout()
        help_text = "Enter value or formula starting with '='. " \
                    "Use \"quotes\" for comments; semicolon ';' for notes."
        help_label = QLabel(help_text)
        help_label.setStyleSheet("color: #888; font-style: italic; font-size: 9px;")
        footer_layout.addWidget(help_label)
        
        # Buttons
        from PyQt6.QtWidgets import QDialogButtonBox
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.on_save_clicked)
        self.button_box.rejected.connect(self.reject)
        footer_layout.addWidget(self.button_box)
        
        layout.addLayout(footer_layout)
        
        # Init Data
        if self.item_data.get('formula'):
            self.qty_input.setPlainText(self.item_data['formula'])
        elif self.item_data.get('rate'):
            # Convert rate to string for simple entry
            self.qty_input.setPlainText(str(self.item_data['rate']))
            
        self.update_display()

    def _on_category_changed(self, category):
        """Regenerates the Plug Rate Code when category selection changes."""
        if getattr(self, 'is_loading', False):
            return
        prefix = self.prefixes.get(category, "MISC")
        plug_prefix = f"PR-{prefix}"
        
        # Fetch current codes from PBOQ DB
        existing_codes = []
        try:
            conn = sqlite3.connect(self.pboq_file_path)
            cursor = conn.cursor()
            cursor.execute("SELECT PlugCode FROM pboq_items WHERE PlugCode LIKE ?", (f"{plug_prefix}%",))
            existing_codes = [r[0] for r in cursor.fetchall() if r[0]]
            conn.close()
        except: pass
        
        new_code = self._generate_logic(plug_prefix, existing_codes)
        self.current_plug_code = new_code
        self.code_label.setText(f"Code: {new_code}")

    def _generate_logic(self, prefix, codes):
        if not codes:
            return f"{prefix}1A"
            
        pattern = re.compile(rf"^{re.escape(prefix)}(\d+)([A-Z])$")
        max_num = 0
        max_letter = 'A'
        valid_found = False
        
        for code in codes:
            match = pattern.match(code)
            if match:
                valid_found = True
                num = int(match.group(1))
                letter = match.group(2)
                if num > max_num:
                    max_num = num
                    max_letter = letter
                elif num == max_num:
                    if letter > max_letter:
                        max_letter = letter
        
        if not valid_found:
            return f"{prefix}1A"
            
        if max_letter == 'Z':
            next_num = max_num + 1
            next_letter = 'A'
        else:
            next_num = max_num
            next_letter = chr(ord(max_letter) + 1)
            
        return f"{prefix}{next_num}{next_letter}"

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
        while len(html_lines) < 20: 
            html_lines.append("<div>&nbsp;</div>")
        self.total_display.setText(f"TOTAL: {total_sum:,.2f}")
        self.qty_display.setHtml(f"<div style='color: blue; font-family: Consolas, monospace; font-size: 11px;'>{''.join(html_lines)}</div>")

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

    def on_save_clicked(self):
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
            self.item_data['code'] = self.current_plug_code 
            self.item_data['category'] = self.cat_combo.currentText()
            self.item_data['currency'] = self.curr_combo.currentText()
            
            self.accept()
            self.dataCommitted.emit()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Invalid Input: {e}")
