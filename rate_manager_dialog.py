from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, 
                             QTableWidgetItem, QHeaderView, QLabel, QLineEdit, QPushButton, QWidget, QMenu, QMessageBox, QFormLayout, QComboBox)
from PyQt6.QtGui import QAction
from PyQt6.QtCore import Qt
from database import DatabaseManager
from rate_buildup_dialog import RateBuildUpDialog

class NewRateDialog(QDialog):
    def __init__(self, categories, units, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Rate Details")
        self.setMinimumWidth(400)
        layout = QVBoxLayout(self)
        
        form = QFormLayout()
        self.desc_input = QLineEdit()
        self.desc_input.setPlaceholderText("e.g. Excavation in topsoil...")
        
        self.unit_combo = QComboBox()
        self.unit_combo.setEditable(True)
        self.unit_combo.addItems(units)
        
        self.category_combo = QComboBox()
        self.category_combo.addItems(categories)
        
        form.addRow("Description:", self.desc_input)
        form.addRow("Unit:", self.unit_combo)
        form.addRow("Category:", self.category_combo)
        layout.addLayout(form)
        
        btns = QHBoxLayout()
        save_btn = QPushButton("Save & Continue")
        save_btn.setStyleSheet("background-color: #2e7d32; color: white; padding: 6px; font-weight: bold;")
        save_btn.clicked.connect(self.accept)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        
        btns.addStretch()
        btns.addWidget(cancel_btn)
        btns.addWidget(save_btn)
        layout.addLayout(btns)

    def get_data(self):
        return {
            "description": self.desc_input.text().strip(),
            "unit": self.unit_combo.currentText().strip(),
            "category": self.category_combo.currentText()
        }

class RateManagerDialog(QDialog):
    """Dialog for viewing and managing saved rates in construction_rates.db."""
    def __init__(self, main_window=None, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.setWindowTitle("Libraries")
        self.setMinimumSize(850, 500)
        self.resize(850, 650)
        self.db_manager = None
        self.project_db_manager = None
        self.is_loading = False
        self.is_combined = False
        
        self._init_ui()
        
        if self.library_combo.count() > 0:
            self.db_manager = DatabaseManager(self.library_combo.currentData())
            self.load_rates()
            
        self.load_project_rates()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)

        self.setSizeGripEnabled(True)

        # Header Section
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        import os
        
        main_label = QLabel("Library(ies) :")
        header_layout.addWidget(main_label)
        
        self.library_combo = QComboBox()
        
        project_dir = ""
        if self.main_window:
            active_est = self.main_window._get_active_estimate_window()
            if active_est and type(active_est).__name__ == "EstimateWindow":
                project_dir = os.path.dirname(active_est.db_path) if active_est.db_path else ""
                if project_dir and os.path.basename(project_dir) == "Project Database":
                    project_dir = os.path.dirname(project_dir)
            if not project_dir:
                project_dir = self.main_window.db_manager.get_setting('last_project_dir', '')
                if project_dir and os.path.basename(project_dir) == "Project Database":
                    project_dir = os.path.dirname(project_dir)
                    
        if project_dir and os.path.exists(project_dir):
            lib_dir = os.path.join(project_dir, "Imported Library")
            if os.path.exists(lib_dir):
                for f in os.listdir(lib_dir):
                    if f.endswith('.db'):
                        self.library_combo.addItem(f, os.path.join(lib_dir, f))
                        
            pdb_dir = os.path.join(project_dir, "Project Database")
            if os.path.exists(pdb_dir):
                for f in os.listdir(pdb_dir):
                    if f.endswith('.db'):
                        self.project_db_manager = DatabaseManager(os.path.join(pdb_dir, f))
                        self.project_db_name = f
                        break

        self.library_combo.currentIndexChanged.connect(self._change_library)
        header_layout.addWidget(self.library_combo)
        
        self.combine_btn = QPushButton("Combine Libraries")
        self.combine_btn.setStyleSheet("padding: 4px 10px; font-weight: bold; background-color: #2e7d32; color: white;")
        self.combine_btn.clicked.connect(self._combine_libraries)
        header_layout.addWidget(self.combine_btn)
        
        header_layout.addStretch()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by Rate Code or Description...")
        self.search_input.setFixedWidth(400)
        self.search_input.textChanged.connect(self.filter_rates)
        header_layout.addWidget(self.search_input)
        
        from PyQt6.QtWidgets import QSplitter
        self.splitter = QSplitter(Qt.Orientation.Vertical)
        self.splitter.setHandleWidth(4)
        self.splitter.setStyleSheet("QSplitter::handle { background-color: #cccccc; border-radius: 2px; }")

        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.addWidget(header_widget)

        # Table
        self.table = QTableWidget()
        headers = ["Library", "Rate Code", "Description", "Unit", "Base Curr", "Net Rate", "Gross Rate", "Adj. Factor", "Date", "Notes"]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        
        # Responsive Header Sizing
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(True)
        
        self.table.setEditTriggers(QTableWidget.EditTrigger.AnyKeyPressed | 
                                   QTableWidget.EditTrigger.EditKeyPressed | 
                                   QTableWidget.EditTrigger.SelectedClicked)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setWordWrap(False)
        self.table.verticalHeader().setDefaultSectionSize(25)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setStyleSheet("QTableWidget { border: 1px solid #e0e0e0; border-radius: 4px; }")
        
        self.table.doubleClicked.connect(lambda idx, t=self.table: self.open_rate_buildup(t, idx))
        self.table.itemChanged.connect(self.on_item_changed)
        
        # Context Menu
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(lambda pos, t=self.table: self.show_context_menu(t, pos))
        
        top_layout.addWidget(self.table)
        
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(0, 0, 0, 15)
        
        proj_label = QLabel("Project Rates")
        proj_label.setStyleSheet("font-weight: bold; color: blue; margin-top: 10px;")
        
        self.project_search_input = QLineEdit()
        self.project_search_input.setPlaceholderText("Search for Project Rates by Rate Code or Description")
        self.project_search_input.setFixedWidth(400)
        self.project_search_input.textChanged.connect(self.filter_project_rates)
        
        proj_header_layout = QHBoxLayout()
        proj_header_layout.addWidget(proj_label)
        proj_header_layout.addStretch()
        proj_header_layout.addWidget(self.project_search_input)
        
        bottom_widget_header = QWidget()
        bottom_widget_header.setLayout(proj_header_layout)
        
        bottom_layout.addWidget(bottom_widget_header)
        
        self.project_table = QTableWidget()
        self.project_table.setColumnCount(len(headers))
        self.project_table.setHorizontalHeaderLabels(headers)
        
        p_header = self.project_table.horizontalHeader()
        p_header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        p_header.setStretchLastSection(True)
        
        self.project_table.setEditTriggers(QTableWidget.EditTrigger.AnyKeyPressed | 
                                           QTableWidget.EditTrigger.EditKeyPressed | 
                                           QTableWidget.EditTrigger.SelectedClicked)
        self.project_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.project_table.setWordWrap(False)
        self.project_table.verticalHeader().setDefaultSectionSize(25)
        self.project_table.setAlternatingRowColors(True)
        self.project_table.setShowGrid(False)
        self.project_table.setStyleSheet("QTableWidget { border: 1px solid #e0e0e0; border-radius: 4px; }")
        
        self.project_table.doubleClicked.connect(lambda idx, t=self.project_table: self.open_rate_buildup(t, idx))
        self.project_table.itemChanged.connect(self.on_item_changed)
        self.project_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.project_table.customContextMenuRequested.connect(lambda pos, t=self.project_table: self.show_context_menu(t, pos))
        
        bottom_layout.addWidget(self.project_table)
        
        self.splitter.addWidget(top_widget)
        self.splitter.addWidget(bottom_widget)
        self.splitter.setSizes([300, 300])
        layout.addWidget(self.splitter)

    def _change_library(self):
        self.is_combined = False
        if hasattr(self, 'combine_btn'):
            self.combine_btn.setText("Combine Libraries")
        db_path = self.library_combo.currentData()
        if db_path:
            self.db_manager = DatabaseManager(db_path)
            self.load_rates()

    def _combine_libraries(self):
        self.is_combined = not self.is_combined
        if self.is_combined:
            self.combine_btn.setText("Un-Combine Libraries")
        else:
            self.combine_btn.setText("Combine Libraries")
            db_path = self.library_combo.currentData()
            if db_path:
                self.db_manager = DatabaseManager(db_path)
        self.load_rates()



    def load_rates(self):
        """Loads data from construction_rates.db into the table."""
        if not self.db_manager and not self.is_combined:
            return
            
        self.is_loading = True
        self.table.setRowCount(0)
        
        all_rates = []
        if self.is_combined:
            for i in range(self.library_combo.count()):
                lib_name = self.library_combo.itemText(i)
                lib_path = self.library_combo.itemData(i)
                if lib_path:
                    db = DatabaseManager(lib_path)
                    rates = db.get_rates_data()
                    for r in rates:
                        r['_library_name'] = lib_name
                        r['_library_path'] = lib_path
                    all_rates.extend(rates)
        else:
            if self.db_manager:
                rates = self.db_manager.get_rates_data()
                lib_name = self.library_combo.currentText()
                lib_path = self.library_combo.currentData()
                for r in rates:
                    r['_library_name'] = lib_name
                    r['_library_path'] = lib_path
                all_rates.extend(rates)
        
        for row_idx, row_data in enumerate(all_rates):
            self.table.insertRow(row_idx)
            
            columns = [
                row_data.get('_library_name'),
                row_data.get('rate_code'),
                row_data.get('project_name'),
                row_data.get('unit'),
                row_data.get('currency'),
                row_data.get('net_total'),
                row_data.get('grand_total'),
                row_data.get('adjustment_factor'),
                row_data.get('date_created'),
                row_data.get('notes')
            ]
            
            for col_idx, data in enumerate(columns):
                if col_idx in [5, 6]: # net_total or grand_total
                    display_text = f"{float(data):,.2f}" if data is not None else "0.00"
                elif col_idx == 7: # adjustment_factor
                    try:
                        val = float(data)
                        display_text = f"{val:.2f}" if val != 1.0 else "N/A"
                    except:
                        display_text = "N/A"
                else:
                    display_text = str(data) if data is not None else ""
                
                item = QTableWidgetItem(display_text)
                # Store the internal DB ID and path in the first visible column's UserRole
                if col_idx == 0:
                    val_str = f"{row_data.get('id')}|{row_data.get('_library_path')}"
                    item.setData(Qt.ItemDataRole.UserRole, val_str)
                    
                if col_idx == 1:
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                
                if col_idx in [5, 6, 7]: # Net Rate, Gross Rate, and Adj Factor
                    font = item.font()
                    font.setBold(True) if col_idx in [5, 6] else None
                    item.setFont(font)
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                
                # Freeze all columns except Rate Code and Description
                if col_idx not in [1, 2]:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                
                self.table.setItem(row_idx, col_idx, item)
        
        # Initial fit for all columns
        for i in range(self.table.columnCount()):
            self.table.resizeColumnToContents(i)
            
        # Ensure description and notes had a bit of extra space to start
        current_desc_w = self.table.columnWidth(2)
        self.table.setColumnWidth(2, max(current_desc_w, 250))
        
        self.is_loading = False

    def load_project_rates(self):
        """Loads data from the Project Database into the table."""
        if not self.project_db_manager:
            return
            
        self.is_loading = True
        self.project_table.setRowCount(0)
        rates = self.project_db_manager.get_rates_data()
        db_name_str = getattr(self, 'project_db_name', "Project Database")
        db_path_str = self.project_db_manager.db_file
        
        for row_idx, row_data in enumerate(rates):
            self.project_table.insertRow(row_idx)
            columns = [
                db_name_str,
                row_data.get('rate_code'),
                row_data.get('project_name'),
                row_data.get('unit'),
                row_data.get('currency'),
                row_data.get('net_total'),
                row_data.get('grand_total'),
                row_data.get('adjustment_factor'),
                row_data.get('date_created'),
                row_data.get('notes')
            ]
            
            for col_idx, data in enumerate(columns):
                if col_idx in [5, 6]:
                    display_text = f"{float(data):,.2f}" if data is not None else "0.00"
                elif col_idx == 7:
                    try:
                        val = float(data)
                        display_text = f"{val:.2f}" if val != 1.0 else "N/A"
                    except:
                        display_text = "N/A"
                else:
                    display_text = str(data) if data is not None else ""
                
                item = QTableWidgetItem(display_text)
                if col_idx == 0:
                    val_str = f"{row_data.get('id')}|{db_path_str}"
                    item.setData(Qt.ItemDataRole.UserRole, val_str)
                    
                if col_idx == 1:
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                
                if col_idx in [5, 6, 7]:
                    font = item.font()
                    font.setBold(True) if col_idx in [5, 6] else None
                    item.setFont(font)
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                
                if col_idx not in [1, 2]:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                
                self.project_table.setItem(row_idx, col_idx, item)
        
        for i in range(self.project_table.columnCount()):
            self.project_table.resizeColumnToContents(i)
        current_desc_w = self.project_table.columnWidth(2)
        self.project_table.setColumnWidth(2, max(current_desc_w, 250))
        
        self.is_loading = False

    def open_rate_buildup(self, table, index):
        """Loads and shows the build-up for the selected rate."""
        row = index.row()
        val_str = table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        
        if val_str:
            db_id = int(val_str.split('|')[0])
            db_path = val_str.split('|')[1]
            from database import DatabaseManager
            rates_db = DatabaseManager(db_path)
            estimate_obj = rates_db.load_estimate_details(db_id)
            if estimate_obj and self.main_window:
                self.main_window.open_rate_buildup_window(estimate_obj, db_path=db_path)
            else:
                dialog = RateBuildUpDialog(estimate_obj, main_window=self.main_window, parent=self, db_path=db_path)
                if table == self.project_table:
                    dialog.dataCommitted.connect(self.load_project_rates)
                else:
                    dialog.dataCommitted.connect(self.load_rates)
                dialog.exec()

    def highlight_rate(self, rate_code):
        """Finds and highlights a rate by its code."""
        # Unhide from search first easily if we have one
        self.search_input.clear()
        self.project_search_input.clear()
        
        # Get the highlight color from settings
        from database import DatabaseManager as _DB
        _settings_db = _DB()
        highlight_color = _settings_db.get_setting("color_highlights") or "#fff9c4"
        from PyQt6.QtGui import QColor as _QC
        bg = _QC(highlight_color)
        
        from PyQt6.QtWidgets import QTableWidget
        # Search both library table and project table
        for tbl in [self.table, self.project_table]:
            for row in range(tbl.rowCount()):
                item = tbl.item(row, 1)
                if item and item.text() == rate_code:
                    tbl.clearSelection()
                    tbl.selectRow(row)
                    tbl.scrollToItem(item, QTableWidget.ScrollHint.PositionAtCenter)
                    # Apply highlight color to the row
                    for col in range(tbl.columnCount()):
                        cell = tbl.item(row, col)
                        if cell:
                            cell.setBackground(bg)
                    return

    def filter_rates(self, text):
        query = text.lower()
        for row in range(self.table.rowCount()):
            item0 = self.table.item(row, 0)
            item1 = self.table.item(row, 1)
            item2 = self.table.item(row, 2)
            if item1 and item2:
                lib_match = query in item0.text().lower() if item0 else False
                id_match = query in item1.text().lower()
                desc_match = query in item2.text().lower()
                self.table.setRowHidden(row, not (lib_match or id_match or desc_match))

    def filter_project_rates(self, text):
        query = text.lower()
        for row in range(self.project_table.rowCount()):
            item0 = self.project_table.item(row, 0)
            item1 = self.project_table.item(row, 1)
            item2 = self.project_table.item(row, 2)
            if item1 and item2:
                lib_match = query in item0.text().lower() if item0 else False
                id_match = query in item1.text().lower()
                desc_match = query in item2.text().lower()
                self.project_table.setRowHidden(row, not (lib_match or id_match or desc_match))

    def on_item_changed(self, item):
        """Handles inline editing of Rate Code and Description."""
        if self.is_loading:
            return
            
        table = item.tableWidget()
        row = item.row()
        col = item.column()
        
        # Only handle Rate Code (1) and Description (2)
        if col not in [1, 2]:
            return
            
        val_str = table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        if not val_str:
            return
            
        db_id = int(val_str.split('|')[0])
        db_path = val_str.split('|')[1]
            
        new_val = item.text().strip()
        field = "rate_code" if col == 1 else "project_name"
        
        db = DatabaseManager(db_path)
        if db.update_estimate_field(db_id, field, new_val):
            pass
        else:
            QMessageBox.warning(self, "Error", f"Failed to update {field} in database.")
            if table == self.project_table:
                self.load_project_rates()
            else:
                self.load_rates()

    def show_context_menu(self, table, pos):
        """Shows the context menu for the given rate table."""
        menu = QMenu(self)
        
        new_action = QAction("New Rate", self)
        new_action.triggered.connect(lambda checked=False, t=table: self.new_rate(t))
        menu.addAction(new_action)
        
        selected_indexes = table.selectionModel().selectedRows()
        if selected_indexes:
            edit_action = QAction("Edit Rate", self)
            edit_action.triggered.connect(lambda checked=False, t=table: self.edit_rate(t))
            menu.addAction(edit_action)
            
            if table == self.project_table:
                price_desc_action = QAction("Price SOR with Description", self)
                price_desc_action.triggered.connect(self.price_sor_from_rate)
                menu.addAction(price_desc_action)
                
                price_kw_action = QAction("Price SOR with Keywords", self)
                price_kw_action.triggered.connect(self.price_sor_from_keywords)
                menu.addAction(price_kw_action)
            
            menu.addSeparator()
            
            duplicate_action = QAction("Duplicate Rate", self)
            duplicate_action.triggered.connect(lambda checked=False, t=table: self.duplicate_rate(t))
            menu.addAction(duplicate_action)
            
            delete_action = QAction("Delete Rate", self)
            delete_action.triggered.connect(lambda checked=False, t=table: self.delete_rate(t))
            menu.addAction(delete_action)
            
        menu.exec(table.viewport().mapToGlobal(pos))

    def edit_rate(self, table=None):
        if table is None: table = self.table
        """Opens the build-up dialog for the selected rate."""
        selected_indexes = table.selectionModel().selectedRows()
        if selected_indexes:
            self.open_rate_buildup(table, selected_indexes[0])

    def new_rate(self, table=None):
        if table is None: table = self.table
        """Creates a new rate and opens the build-up dialog."""
        if table == self.table and (self.is_combined or not self.db_manager):
            QMessageBox.warning(self, "Select Library", "Please select a specific single library from the drop-down to add a new rate.")
            return
        elif table == self.project_table and not self.project_db_manager:
            QMessageBox.warning(self, "No Project Database", "No Project Database found.")
            return
            
        from models import Estimate
        from rate_buildup_dialog import RateBuildUpDialog
        
        db = self.project_db_manager if table == self.project_table else self.db_manager
        
        # Determine category and generate initial code
        cat = "Miscellaneous"
        new_est = Estimate(project_name="New Rate", client_name="", overhead=15.0, profit=10.0, unit="m")
        new_est.category = cat
        new_est.rate_code = db.generate_next_rate_code(cat)
        
        dialog = RateBuildUpDialog(new_est, main_window=self.main_window, parent=self, db_path=db.db_file)
        if table == self.project_table:
            dialog.dataCommitted.connect(self.load_project_rates)
        else:
            dialog.dataCommitted.connect(self.load_rates)
        dialog.exec()

    def duplicate_rate(self, table=None):
        if table is None: table = self.table
        """Duplicates the selected rate."""
        selected_indexes = table.selectionModel().selectedRows()
        if not selected_indexes:
            return
            
        row = selected_indexes[0].row()
        val_str = table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        
        if val_str:
            db_id = int(val_str.split('|')[0])
            db_path = val_str.split('|')[1]
            db = DatabaseManager(db_path)
            
            # Load full details to ensure we duplicate everything (tasks, items, etc.)
            original_estimate = db.load_estimate_details(db_id)
            if original_estimate:
                original_estimate.id = None
                original_estimate.project_name = f"Copy of {original_estimate.project_name}"
                # Generate a new unique rate code
                category = getattr(original_estimate, 'category', "Miscellaneous")
                original_estimate.rate_code = db.generate_next_rate_code(category)
                
                if db.save_estimate(original_estimate):
                    if table == self.project_table:
                        self.load_project_rates()
                    else:
                        self.load_rates()

    def delete_rate(self, table=None):
        if table is None: table = self.table
        """Deletes the selected rate after confirmation."""
        selected_indexes = table.selectionModel().selectedRows()
        if not selected_indexes:
            return
            
        row = selected_indexes[0].row()
        val_str = table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        rate_code = table.item(row, 1).text()
        
        if val_str:
            db_id = int(val_str.split('|')[0])
            db_path = val_str.split('|')[1]
            db = DatabaseManager(db_path)
            
            reply = QMessageBox.question(self, 'Delete Rate',
                                       f"Are you sure you want to delete Rate {rate_code}?",
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                       QMessageBox.StandardButton.No)
            
            if reply == QMessageBox.StandardButton.Yes:
                if db.delete_estimate(db_id):
                    if table == self.project_table:
                        self.load_project_rates()
                    else:
                        self.load_rates()

    def price_sor_from_rate(self):
        """Finds the open SOR window and pushes the selected rate data to it."""
        selected_indexes = self.project_table.selectionModel().selectedRows()
        if not selected_indexes:
            return
            
        row = selected_indexes[0].row()
        rate_code = self.project_table.item(row, 1).text()
        rate_desc = self.project_table.item(row, 2).text()
        
        # Gross Rate is index 6
        try:
            gross_str = self.project_table.item(row, 6).text().replace(',', '')
            gross_rate = float(gross_str)
        except:
            gross_rate = 0.0
            
        # Find SORDialog in MDI area
        sor_dialog = None
        if self.main_window:
            from sor_viewer import SORDialog
            for sub in self.main_window.mdi_area.subWindowList():
                widget = sub.widget()
                if isinstance(widget, SORDialog):
                    sor_dialog = widget
                    break
                    
        if not sor_dialog:
            QMessageBox.warning(self, "SOR Not Open", "Please open the SOR window first to use 'Price SOR'.")
            return
            
        count = sor_dialog._price_sor_with_rate(rate_desc, gross_rate, rate_code)
        if count > 0:
            QMessageBox.information(self, "Success", f"Successfully found and priced {count} SOR item(s) matching '{rate_desc}'.")
        else:
            QMessageBox.information(self, "No Match", f"No items matching '{rate_desc}' were found in the current SOR view.")

    def price_sor_from_keywords(self):
        """Prices SOR items using the keywords active in the SOR window."""
        selected_indexes = self.project_table.selectionModel().selectedRows()
        if not selected_indexes:
            return
            
        row = selected_indexes[0].row()
        rate_code = self.project_table.item(row, 1).text()
        
        try:
            gross_str = self.project_table.item(row, 6).text().replace(',', '')
            gross_rate = float(gross_str)
        except:
            gross_rate = 0.0
            
        # Find SORDialog
        sor_dialog = None
        if self.main_window:
            from sor_viewer import SORDialog
            for sub in self.main_window.mdi_area.subWindowList():
                widget = sub.widget()
                if isinstance(widget, SORDialog):
                    sor_dialog = widget
                    break
        
        if not sor_dialog:
            QMessageBox.warning(self, "SOR Not Open", "Please open the SOR window first to use 'Price SOR with Keywords'.")
            return
            
        count = sor_dialog._price_sor_with_keywords(gross_rate, rate_code)
        
        if count == -1:
            QMessageBox.warning(self, "No Keywords", "Please enter keywords in the SOR window first.")
        elif count > 0:
            QMessageBox.information(self, "Success", f"Successfully found and priced {count} SOR item(s) using current keywords.")
        else:
            QMessageBox.information(self, "No Match", "No items matching the current keywords were found in the SOR view.")
