from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLineEdit, QComboBox, 
                             QDialogButtonBox, QLabel, QMessageBox, QPushButton, QFileDialog, QHBoxLayout,
                             QColorDialog, QGroupBox, QGridLayout, QTableWidget, QTableWidgetItem, QHeaderView)
from PyQt6.QtGui import QDoubleValidator, QColor
from PyQt6.QtCore import Qt
from database import DatabaseManager

class CategoriesCodesDialog(QDialog):
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Categories and Codes")
        self.db_manager = db_manager
        self.resize(300, 350)
        
        self.original_prefixes = self.db_manager.get_category_prefixes_dict()
        
        layout = QVBoxLayout(self)
        
        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Category", "Code Prefix"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.table)
        
        self.load_data()
        
        btn_layout = QHBoxLayout()
        add_btn = QPushButton("Add Category")
        add_btn.clicked.connect(self.add_category)
        remove_btn = QPushButton("Delete Selected")
        remove_btn.clicked.connect(self.delete_category)
        
        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(remove_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.save_data)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
    def load_data(self):
        self.table.setRowCount(0)
        for cat, code in self.original_prefixes.items():
            self.add_row(cat, code)
            
    def add_row(self, cat, code):
        row = self.table.rowCount()
        self.table.insertRow(row)
        cat_item = QTableWidgetItem(cat)
        cat_item.setData(Qt.ItemDataRole.UserRole, cat)
        code_item = QTableWidgetItem(code)
        
        self.table.setItem(row, 0, cat_item)
        self.table.setItem(row, 1, code_item)
        
    def add_category(self):
        self.add_row("New Category", "NEW")
        self.table.selectRow(self.table.rowCount() - 1)
        self.table.editItem(self.table.item(self.table.rowCount() - 1, 0))
        
    def delete_category(self):
        selected_items = self.table.selectedItems()
        if not selected_items:
            return
            
        # Get unique rows from the selected items
        rows_to_delete = sorted(list(set(item.row() for item in selected_items)), reverse=True)
        count = len(rows_to_delete)
        
        reply = QMessageBox.question(self, 'Confirm Deletion',
                                     f"Are you sure you want to delete {count} selected categor{'y' if count == 1 else 'ies'}?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            for row in rows_to_delete:
                self.table.removeRow(row)
            
    def save_data(self):
        new_prefixes = {}
        renames = []
        for row in range(self.table.rowCount()):
            cat_item = self.table.item(row, 0)
            code_item = self.table.item(row, 1)
            
            if not cat_item or not code_item:
                continue
                
            new_cat = cat_item.text().strip()
            new_code = code_item.text().strip()
            
            if not new_cat:
                continue
                
            new_prefixes[new_cat] = new_code
            
            old_cat = cat_item.data(Qt.ItemDataRole.UserRole)
            if old_cat and old_cat != "New Category" and old_cat != new_cat:
                renames.append((old_cat, new_cat))
                
        self.db_manager.set_category_prefixes_dict(new_prefixes)
        
        for old_cat, new_cat in renames:
            self.db_manager.rename_category(old_cat, new_cat)
            
        QMessageBox.information(self, "Success", "Categories and codes saved successfully. Please close and re-open any affected windows.")
        self.accept()
class ResourceColorsDialog(QDialog):
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Resource Colors")
        self.db_manager = db_manager
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)
        
        self.colors = {}
        categories = ["Materials", "Labour", "Equipment", "Plant", "Indirect Costs", "Rates"]
        default_colors = {
            "Materials": "#e6f2ff",
            "Labour": "#fff0e6",
            "Equipment": "#e6ffe6",
            "Plant": "#ffe6e6",
            "Indirect Costs": "#f2e6ff",
            "Rates": "#ffffe6"
        }
        
        color_layout = QGridLayout()
        color_layout.setContentsMargins(0, 0, 0, 0)
        color_layout.setHorizontalSpacing(15)
        color_layout.setVerticalSpacing(5)
        
        row, col = 0, 0
        for cat in categories:
            setting_key = f"color_{cat.lower().replace(' ', '_')}"
            val = self.db_manager.get_setting(setting_key)
            if not val:
                val = default_colors[cat]
            self.colors[setting_key] = val
            
            btn = QPushButton()
            btn.setFixedSize(50, 20)
            btn.setStyleSheet(f"background-color: {val}; border: 1px solid #777; border-radius: 3px;")
            
            btn.clicked.connect(lambda checked, c=cat, sk=setting_key, b=btn: self.choose_color(c, sk, b))
            
            lbl = QLabel(f"{cat}:")
            color_layout.addWidget(lbl, row, col)
            color_layout.addWidget(btn, row, col + 1)
            
            col += 2
            if col > 2:
                col = 0
                row += 1
            
        layout.addLayout(color_layout)
        
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.save_colors)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def choose_color(self, category, setting_key, btn):
        initial_color = QColor(self.colors[setting_key])
        color = QColorDialog.getColor(initial_color, self, f"Select Color for {category}")
        if color.isValid():
            hex_color = color.name()
            self.colors[setting_key] = hex_color
            btn.setStyleSheet(f"background-color: {hex_color}; border: 1px solid #777; border-radius: 3px;")

    def save_colors(self):
        for sk, hex_color in self.colors.items():
            self.db_manager.set_setting(sk, hex_color)
        from PyQt6.QtWidgets import QApplication
        for widget in QApplication.topLevelWidgets():
            if hasattr(widget, 'mdi_area'):
                # Trigger refresh across open editor windows
                for sub in widget.mdi_area.subWindowList():
                    from rate_buildup_dialog import RateBuildUpDialog
                    sub_widget = sub.widget()
                    if isinstance(sub_widget, RateBuildUpDialog) and hasattr(sub_widget, 'tree_widget'):
                        sub_widget.tree_widget.refresh_ui()
        QMessageBox.information(self, "Success", "Resource colors saved successfully.")
        self.accept()

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Application Settings")
        self.setMinimumWidth(400)
        self.db_manager = DatabaseManager()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        form_layout = QFormLayout()
        form_layout.setSpacing(5)

        # Default Currency
        self.currency_combo = QComboBox()
        self.currency_combo.addItems(["USD ($)", "EUR (€)", "GBP (£)", "JPY (¥)", "CAD ($)", "GHS (₵)", "CNY (¥)", "INR (₹)"])
        current_currency = self.db_manager.get_setting('currency', 'GHS (₵)')
        self.currency_combo.setCurrentText(current_currency)
        
        # Default Overhead
        self.overhead_input = QLineEdit()
        pct_validator = QDoubleValidator(0.0, 100.0, 2)
        self.overhead_input.setValidator(pct_validator)
        self.overhead_input.setText(self.db_manager.get_setting('overhead', '15.00'))

        # Default Profit
        self.profit_input = QLineEdit()
        self.profit_input.setValidator(pct_validator)
        self.profit_input.setText(self.db_manager.get_setting('profit', '10.00'))

        # Company Name (for reports)
        self.company_name = QLineEdit()
        self.company_name.setText(self.db_manager.get_setting('company_name', ''))
        self.company_name.setPlaceholderText("Your Company Name")

        # Company Logo
        self.logo_path = QLineEdit()
        self.logo_path.setReadOnly(True)
        self.logo_path.setText(self.db_manager.get_setting('company_logo', ''))
        self.logo_path.setPlaceholderText("No logo selected")
        
        logo_layout = QHBoxLayout()
        logo_layout.addWidget(self.logo_path)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.browse_logo)
        logo_layout.addWidget(browse_btn)

        form_layout.addRow("Default Currency:", self.currency_combo)
        form_layout.addRow("Default Overhead (%):", self.overhead_input)
        form_layout.addRow("Default Profit (%):", self.profit_input)
        form_layout.addRow("Company Name:", self.company_name)
        form_layout.addRow("Company Logo:", logo_layout)

        self.resource_colors_btn = QPushButton("Resource Colors...")
        self.resource_colors_btn.clicked.connect(self.open_resource_colors)
        form_layout.addRow("Visuals:", self.resource_colors_btn)

        self.categories_btn = QPushButton("Categories and Codes...")
        self.categories_btn.clicked.connect(self.open_categories_dialog)
        form_layout.addRow("Categories and Codes:", self.categories_btn)

        layout.addLayout(form_layout)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.save_settings)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def browse_logo(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Logo", "", "Images (*.png *.jpg *.jpeg)")
        if file_path:
            self.logo_path.setText(file_path)

    def open_resource_colors(self):
        dialog = ResourceColorsDialog(self.db_manager, self)
        dialog.exec()

    def open_categories_dialog(self):
        dialog = CategoriesCodesDialog(self.db_manager, self)
        dialog.exec()

    def save_settings(self):
        try:
            self.db_manager.set_setting('currency', self.currency_combo.currentText())
            self.db_manager.set_setting('overhead', float(self.overhead_input.text()))
            self.db_manager.set_setting('profit', float(self.profit_input.text()))
            self.db_manager.set_setting('company_name', self.company_name.text())
            self.db_manager.set_setting('company_logo', self.logo_path.text())
            
            QMessageBox.information(self, "Success", "Settings saved successfully.")
            self.accept()
        except ValueError:
            QMessageBox.warning(self, "Error", "Invalid numeric values for Overhead or Profit.")
