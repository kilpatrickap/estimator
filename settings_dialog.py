from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLineEdit, QComboBox, 
                             QDialogButtonBox, QLabel, QMessageBox, QPushButton, QFileDialog, QHBoxLayout,
                             QColorDialog, QGroupBox, QGridLayout, QTableWidget, QTableWidgetItem, QHeaderView, QMenu)
from PyQt6.QtGui import QDoubleValidator, QColor, QAction
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
        
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        
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

    def show_context_menu(self, pos):
        menu = QMenu(self)
        
        add_action = QAction("Add Category", self)
        add_action.triggered.connect(self.add_category)
        menu.addAction(add_action)
        
        if self.table.selectedItems():
            delete_action = QAction("Delete Selected", self)
            delete_action.triggered.connect(self.delete_category)
            menu.addAction(delete_action)
            
        menu.exec(self.table.viewport().mapToGlobal(pos))

class ResourceColorsDialog(QDialog):
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Resource Colors")
        self.db_manager = db_manager
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)
        
        self.colors = {}
        categories = ["Materials", "Labour", "Equipment", "Plant", "Indirect Costs", "Rates", "Highlights"]
        default_colors = {
            "Materials": "#e6f2ff",
            "Labour": "#fff0e6",
            "Equipment": "#e6ffe6",
            "Plant": "#ffe6e6",
            "Indirect Costs": "#f2e6ff",
            "Rates": "#ffffe6",
            "Highlights": "#fff9c4"
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
    def __init__(self, estimate=None, project_dir="", library_path="", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.db_manager = DatabaseManager()
        self.estimate = estimate
        self.project_dir = project_dir

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        columns_layout = QHBoxLayout()
        main_layout.addLayout(columns_layout)

        # ====== LEFT: Application Settings ======
        app_group = QGroupBox("Application Settings")
        app_layout = QVBoxLayout(app_group)
        app_form = QFormLayout()
        
        self.company_name = QLineEdit(self.db_manager.get_setting('company_name', ''))
        self.company_name.setPlaceholderText("Your Company Name")
        
        self.logo_path = QLineEdit(self.db_manager.get_setting('company_logo', ''))
        self.logo_path.setReadOnly(True)
        self.logo_path.setPlaceholderText("No logo selected")
        
        logo_layout = QHBoxLayout()
        logo_layout.addWidget(self.logo_path)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.browse_logo)
        logo_layout.addWidget(browse_btn)

        app_form.addRow("Company Name:", self.company_name)
        app_form.addRow("Company Logo:", logo_layout)

        self.resource_colors_btn = QPushButton("Resource Colors...")
        self.resource_colors_btn.clicked.connect(self.open_resource_colors)
        app_form.addRow("Visuals:", self.resource_colors_btn)

        self.categories_btn = QPushButton("Categories and Codes...")
        self.categories_btn.clicked.connect(self.open_categories_dialog)
        app_form.addRow("Categories and Codes:", self.categories_btn)
        
        app_layout.addLayout(app_form)
        app_layout.addStretch()
        columns_layout.addWidget(app_group)

        # ====== RIGHT: Project Settings ======
        import os
        if self.estimate or (self.project_dir and os.path.exists(self.project_dir)):
            proj_group = QGroupBox("Project Settings")
            proj_layout = QVBoxLayout(proj_group)
            proj_form = QFormLayout()
            
            from PyQt6.QtWidgets import QDateEdit, QListWidget, QAbstractItemView
            from PyQt6.QtCore import QDate
            
            # Auto-detect DB Path
            db_path = ""
            if self.project_dir and os.path.exists(self.project_dir):
                db_dir = os.path.join(self.project_dir, "Project Database")
                if os.path.exists(db_dir):
                    dbs = [f for f in os.listdir(db_dir) if f.endswith('.db')]
                    if dbs:
                        db_path = os.path.join(db_dir, dbs[0])

            proj_db_manager = None
            if db_path:
                proj_db_manager = DatabaseManager(db_path)
            
            # Auto-detect Library Path
            actual_lib_path = library_path
            if self.project_dir and os.path.exists(self.project_dir):
                lib_dir = os.path.join(self.project_dir, "Imported Library")
                if os.path.exists(lib_dir):
                    libs = [f for f in os.listdir(lib_dir) if f.endswith('.db')]
                    if libs:
                        actual_lib_path = os.path.join(lib_dir, libs[0])
            
            # Resolve properties
            self._def_name = self.estimate.project_name if self.estimate else os.path.basename(self.project_dir)
            self._def_client = self.estimate.client_name if self.estimate else ""
            self._def_date = self.estimate.date if self.estimate else ""
            def_overhead = str(self.estimate.overhead_percent) if self.estimate else "15.0"
            def_profit = str(self.estimate.profit_margin_percent) if self.estimate else "10.0"
            def_currency = self.estimate.currency if self.estimate else "GHS (₵)"

            if not self.estimate and proj_db_manager:
                def_overhead = proj_db_manager.get_setting('overhead', def_overhead)
                def_profit = proj_db_manager.get_setting('profit', def_profit)
                def_currency = proj_db_manager.get_setting('currency', def_currency)
                
            try:
                def_overhead = f"{float(def_overhead):.2f}"
            except (ValueError, TypeError):
                def_overhead = "15.00"
                
            try:
                def_profit = f"{float(def_profit):.2f}"
            except (ValueError, TypeError):
                def_profit = "10.00"
                
            pct_validator = QDoubleValidator(0.0, 100.0, 2)
            self.proj_overhead = QLineEdit(def_overhead)
            self.proj_overhead.setValidator(pct_validator)
            self.proj_profit = QLineEdit(def_profit)
            self.proj_profit.setValidator(pct_validator)
            
            self.proj_currency = QComboBox()
            self.proj_currency.addItems(["USD ($)", "EUR (€)", "GBP (£)", "JPY (¥)", "CAD ($)", "GHS (₵)", "CNY (¥)", "INR (₹)"])
            self.proj_currency.setCurrentText(def_currency)
            # Library (List)
            self.library_list = QListWidget()
            self.library_list.setMaximumHeight(100)
            self.library_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
            self._load_libraries()
            
            lib_btn_layout = QHBoxLayout()
            self.add_lib_btn = QPushButton("Add/Import Libraries...")
            self.add_lib_btn.clicked.connect(self._add_library)
            self.del_lib_btn = QPushButton("Delete Selected")
            self.del_lib_btn.clicked.connect(self._delete_library)
            lib_btn_layout.addWidget(self.add_lib_btn)
            lib_btn_layout.addWidget(self.del_lib_btn)
            
            lib_main_layout = QVBoxLayout()
            lib_main_layout.addWidget(self.library_list)
            lib_main_layout.addLayout(lib_btn_layout)
            
            # BOQ
            self.boq_list = QListWidget()
            self.boq_list.setMaximumHeight(100)
            self.boq_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
            self._load_boqs()
            
            boq_btn_layout = QHBoxLayout()
            self.add_boq_btn = QPushButton("Add/Import BOQs...")
            self.add_boq_btn.clicked.connect(self._add_boq)
            self.del_boq_btn = QPushButton("Delete Selected")
            self.del_boq_btn.clicked.connect(self._delete_boq)
            boq_btn_layout.addWidget(self.add_boq_btn)
            boq_btn_layout.addWidget(self.del_boq_btn)
            
            boq_main_layout = QVBoxLayout()
            boq_main_layout.addWidget(self.boq_list)
            boq_main_layout.addLayout(boq_btn_layout)

            proj_form.addRow("Overhead (%):", self.proj_overhead)
            proj_form.addRow("Profit (%):", self.proj_profit)
            proj_form.addRow("Currency:", self.proj_currency)
            proj_form.addRow("Library(ies):", lib_main_layout)
            proj_form.addRow("Imported BOQs:", boq_main_layout)
            
            proj_layout.addLayout(proj_form)
            columns_layout.addWidget(proj_group)

        # Buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.save_settings)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

    def browse_logo(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Logo", "", "Images (*.png *.jpg *.jpeg)")
        if file_path:
            self.logo_path.setText(file_path)

    def open_resource_colors(self):
        ResourceColorsDialog(self.db_manager, self).exec()

    def open_categories_dialog(self):
        CategoriesCodesDialog(self.db_manager, self).exec()

    def _load_libraries(self):
        self.library_list.clear()
        import os
        if not self.project_dir or not os.path.exists(self.project_dir):
            return
        lib_dir = os.path.join(self.project_dir, "Imported Library")
        if not os.path.exists(lib_dir):
            return
        for f in os.listdir(lib_dir):
            if f.endswith('.db'):
                self.library_list.addItem(f)

    def _add_library(self):
        import os, shutil
        if not self.project_dir or not os.path.exists(self.project_dir):
            QMessageBox.warning(self, "Error", "Project directory is not valid.")
            return
        file_paths, _ = QFileDialog.getOpenFileNames(self, "Select Library(ies)", "", "Database Files (*.db);;All Files (*)")
        if file_paths:
            lib_dir = os.path.join(self.project_dir, "Imported Library")
            os.makedirs(lib_dir, exist_ok=True)
            for file_path in file_paths:
                filename = os.path.basename(file_path)
                target = os.path.join(lib_dir, filename)
                try:
                    shutil.copy2(file_path, target)
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Failed to copy Library:\n{e}")
            self._load_libraries()

    def _delete_library(self):
        import os
        curr = self.library_list.currentItem()
        if not curr: return
        filename = curr.text()
        reply = QMessageBox.question(self, "Confirm Delete", f"Are you sure you want to delete '{filename}'?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            fpath = os.path.join(self.project_dir, "Imported Library", filename)
            if os.path.exists(fpath):
                try:
                    os.remove(fpath)
                    self._load_libraries()
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Failed to delete file:\n{e}")

    def _load_boqs(self):
        self.boq_list.clear()
        import os
        if not self.project_dir or not os.path.exists(self.project_dir):
            return
        boq_dir = os.path.join(self.project_dir, "Imported BOQs")
        if not os.path.exists(boq_dir):
            return
        for f in os.listdir(boq_dir):
            if f.lower().endswith(('.xlsx', '.xls')):
                self.boq_list.addItem(f)

    def _add_boq(self):
        import os, shutil
        if not self.project_dir or not os.path.exists(self.project_dir):
            QMessageBox.warning(self, "Error", "Project directory is not valid.")
            return
        file_paths, _ = QFileDialog.getOpenFileNames(self, "Select Excel BOQ(s)", "", "Excel Files (*.xlsx *.xls);;All Files (*)")
        if file_paths:
            boq_dir = os.path.join(self.project_dir, "Imported BOQs")
            os.makedirs(boq_dir, exist_ok=True)
            for file_path in file_paths:
                filename = os.path.basename(file_path)
                target = os.path.join(boq_dir, filename)
                try:
                    shutil.copy2(file_path, target)
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Failed to copy BOQ: {e}")
            self._load_boqs()

    def _delete_boq(self):
        import os
        curr = self.boq_list.currentItem()
        if not curr: return
        filename = curr.text()
        reply = QMessageBox.question(self, "Confirm Delete", f"Are you sure you want to delete '{filename}'?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            fpath = os.path.join(self.project_dir, "Imported BOQs", filename)
            if os.path.exists(fpath):
                try:
                    os.remove(fpath)
                    self._load_boqs()
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Failed to delete file:\n{e}")

    def get_project_data(self):
        if not hasattr(self, 'proj_overhead'):
            return None
        return {
            "name": getattr(self, '_def_name', ""),
            "client": getattr(self, '_def_client', ""),
            "date": getattr(self, '_def_date', ""),
            "overhead": float(self.proj_overhead.text() or 0),
            "profit": float(self.proj_profit.text() or 0),
            "currency": self.proj_currency.currentText(),
            "library_path": ""
        }

    def save_settings(self):
        try:
            self.db_manager.set_setting('company_name', self.company_name.text())
            self.db_manager.set_setting('company_logo', self.logo_path.text())
            

            QMessageBox.information(self, "Success", "Settings saved successfully.")
            self.accept()
        except ValueError:
            QMessageBox.warning(self, "Error", "Invalid numeric values for settings.")

