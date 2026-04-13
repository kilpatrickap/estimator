import os
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
        
        main_label = QLabel("Imported Library(ies) :")
        main_label.setStyleSheet("font-weight: bold;")
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
            
            # Also locate all PBOQ databases to capture Plug/Sub rates
            self.pboq_db_managers = []
            
            # Look for "Priced BOQs" folder in project root (case-insensitive)
            pboq_dir = None
            if os.path.exists(project_dir):
                for d in os.listdir(project_dir):
                    if d.lower() == "priced boqs":
                        pboq_dir = os.path.join(project_dir, d)
                        break
            
            # If still not found, try common naming patterns
            if not pboq_dir:
                pboq_dir = os.path.join(project_dir, "Priced BOQs")
            
            if os.path.exists(pboq_dir):
                for f in sorted(os.listdir(pboq_dir)):
                    if f.lower().endswith('.db'):
                        self.pboq_db_managers.append(DatabaseManager(os.path.join(pboq_dir, f)))

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
        
        historical_label = QLabel("Historical Data")
        historical_label.setStyleSheet("font-weight: bold; font-size: 14px; color: blue;")
        top_layout.addWidget(historical_label)
        
        top_layout.addWidget(header_widget)

        # Table
        self.table = QTableWidget()
        headers = ["Library", "Rate Code", "Description", "Unit", "Base Curr", "Rate", "Rate Type", "Date"]
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
        self.table.setWordWrap(True)
        self.table.verticalHeader().setDefaultSectionSize(30)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setStyleSheet("QTableWidget { border: 1px solid #e0e0e0; border-radius: 4px; }")
        
        self.table.doubleClicked.connect(lambda idx, t=self.table: self.open_rate_buildup(t, idx))
        self.table.itemChanged.connect(self.on_item_changed)
        self.table.itemSelectionChanged.connect(lambda: self.clear_highlights(self.table))
        self.table.cellClicked.connect(lambda r, c: self.clear_highlights(self.table))
        
        # Context Menu
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(lambda pos, t=self.table: self.show_context_menu(t, pos))
        
        top_layout.addWidget(self.table)
        
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(0, 0, 0, 15)
        
        self.project_label = QLabel("Project Library")
        self.project_label.setStyleSheet("font-weight: bold; font-size: 14px; color: blue;")
        bottom_layout.addWidget(self.project_label)
        
        self.project_search_input = QLineEdit()
        self.project_search_input.setPlaceholderText("Search for Project Rates by Rate Code or Description")
        self.project_search_input.setFixedWidth(400)
        self.project_search_input.textChanged.connect(self.filter_project_rates)
        
        proj_header_layout = QHBoxLayout()
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
        self.project_table.setWordWrap(True)
        self.project_table.verticalHeader().setDefaultSectionSize(30)
        self.project_table.setAlternatingRowColors(True)
        self.project_table.setShowGrid(False)
        self.project_table.setStyleSheet("QTableWidget { border: 1px solid #e0e0e0; border-radius: 4px; }")
        
        self.project_table.doubleClicked.connect(lambda idx, t=self.project_table: self.open_rate_buildup(t, idx))
        self.project_table.itemChanged.connect(self.on_item_changed)
        self.project_table.itemSelectionChanged.connect(lambda: self.clear_highlights(self.project_table))
        self.project_table.cellClicked.connect(lambda r, c: self.clear_highlights(self.project_table))
        self.project_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.project_table.customContextMenuRequested.connect(lambda pos, t=self.project_table: self.show_context_menu(t, pos))
        
        bottom_layout.addWidget(self.project_table)
        
        self.splitter.addWidget(top_widget)
        self.splitter.addWidget(bottom_widget)
        self.splitter.setSizes([300, 300])
        layout.addWidget(self.splitter)

    def clear_highlights(self, table):
        """Removes the custom background highlight once the user starts interacting with the table."""
        if self.is_loading:
            return
        self.is_loading = True
        for row in range(table.rowCount()):
            # Check if column 1 has a custom background to avoid checking all cells
            item = table.item(row, 1)
            from PyQt6.QtCore import Qt
            if item and item.background().style() != Qt.BrushStyle.NoBrush:
                for col in range(table.columnCount()):
                    cell = table.item(row, col)
                    if cell:
                        cell.setData(Qt.ItemDataRole.BackgroundRole, None)
        self.is_loading = False

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



    def _extract_rates_from_db(self, db_manager, lib_name):
        """Standardized method to pull ALL rate types (Gross, Plug, Sub) from a database."""
        if not db_manager:
            return []
            
        import copy
        processed_data = []
        
        # 1. Formal Rates (from 'estimates' table)
        formal_rates = db_manager.get_rates_data()
        
        # 2. PBOQ Discovery (from 'pboq_items' table)
        pboq_summary = db_manager.get_pboq_rates_summary()
        
        seen_codes = set()
        
        # Pre-build a unit/currency lookup from formal rates that have values.
        # This lets us fill missing unit/currency for PR-/SR- prefixed entries
        # by inheriting from the corresponding base rate code.
        unit_map = {}
        curr_map = {}
        for r in formal_rates:
            rc = (r.get('rate_code') or "").strip()
            base = rc
            for pfx in ('PR-', 'SR-'):
                if base.startswith(pfx):
                    base = base[len(pfx):]
                    break
            if base and r.get('unit') and base not in unit_map:
                unit_map[base] = r['unit']
            if base and r.get('currency') and base not in curr_map:
                curr_map[base] = r['currency']
        
        # Process Formal Rates first
        for r in formal_rates:
            code = (r.get('rate_code') or "").strip()
            seen_codes.add(code)
            p_data = pboq_summary.get(code, {})
            
            # Gross Rate
            rate_g = r.get('grand_total')
            if rate_g is not None and float(rate_g) != 0.0:
                gr = copy.deepcopy(r)
                gr['_rate_val'] = rate_g
                gr['_type_val'] = "Gross Rate"
                gr['_library_name'] = lib_name
                gr['_library_path'] = db_manager.db_file
                if p_data.get('_source_db'):
                    gr['_lib_override'] = p_data['_source_db']
                processed_data.append(gr)
            elif r.get('rate_type') == "Plug Rate" and code:
                # Fallback: Synced Plug/Sub entries stored with zero grand_total.
                # These are rate references from PBOQs — show them even without
                # build-up data so they remain visible in imported libraries.
                if code.startswith('SR-'):
                    type_val = "Sub. Rate"
                    rate_val = p_data.get('sub_rate') or 0.0
                else:
                    type_val = "Plug Rate"
                    rate_val = p_data.get('plug_rate') or 0.0
                entry = copy.deepcopy(r)
                entry['_rate_val'] = rate_val
                entry['_type_val'] = type_val
                entry['_library_name'] = lib_name
                entry['_library_path'] = db_manager.db_file
                if p_data.get('_source_db'):
                    entry['_lib_override'] = p_data['_source_db']
                # Inherit missing unit/currency from the base code's formal rate
                base_code = code
                for pfx in ('PR-', 'SR-'):
                    if base_code.startswith(pfx):
                        base_code = base_code[len(pfx):]
                        break
                if not entry.get('unit'):
                    entry['unit'] = p_data.get('unit') or unit_map.get(base_code, '')
                if not entry.get('currency'):
                    fallback_curr = p_data.get('curr') or curr_map.get(base_code, '')
                    if not fallback_curr and hasattr(self, 'project_db_manager') and self.project_db_manager:
                        fallback_curr = self.project_db_manager.get_setting('currency', '')
                    entry['currency'] = fallback_curr
                processed_data.append(entry)
                continue
            
            # Plug Rate (if overridden in this DB)
            if p_data.get('_is_plug'):
                p_val = p_data.get('plug_rate')
                if p_val is not None and float(p_val) != 0.0:
                    pr = copy.deepcopy(r)
                    pr['_rate_val'] = p_val
                    pr['_type_val'] = "Plug Rate"
                    pr['_library_name'] = lib_name
                    pr['_library_path'] = db_manager.db_file
                    if p_data.get('_source_db'):
                        pr['_lib_override'] = p_data['_source_db']
                    processed_data.append(pr)

            # Sub Rate (if exists in summary for this code)
            s_val = p_data.get('sub_rate')
            if s_val is not None and float(s_val) != 0.0:
                sr = copy.deepcopy(r)
                sr['_rate_val'] = s_val
                sr['_type_val'] = "Sub. Rate"
                sr['_library_name'] = lib_name
                sr['_library_path'] = db_manager.db_file
                if p_data.get('_source_db'):
                    sr['_lib_override'] = p_data['_source_db']
                processed_data.append(sr)

        # 3. Discovery-only rates (Codes that don't exist in 'estimates' table yet)
        for code, data in pboq_summary.items():
            if code not in seen_codes:
                p_val = data.get('plug_rate')
                if p_val is not None and float(p_val) != 0.0:
                    row = {
                        'rate_code': code,
                        'project_name': data.get('desc', ''),
                        'unit': data.get('unit', ''),
                        'currency': data.get('curr', ''),
                        '_rate_val': p_val,
                        '_type_val': "Plug Rate",
                        'date_created': data.get('_source_date', 'From PBOQ'),
                        'id': None,
                        '_library_name': lib_name,
                        '_library_path': db_manager.db_file
                    }
                    if data.get('_source_db'): row['_lib_override'] = data['_source_db']
                    processed_data.append(row)
                    
                s_val = data.get('sub_rate')
                if s_val is not None and float(s_val) != 0.0:
                    row = {
                        'rate_code': code,
                        'project_name': data.get('desc', ''),
                        'unit': data.get('unit', ''),
                        'currency': data.get('curr', ''),
                        '_rate_val': s_val,
                        '_type_val': "Sub. Rate",
                        'date_created': data.get('_source_date', 'From PBOQ'),
                        'id': None,
                        '_library_name': lib_name,
                        '_library_path': db_manager.db_file
                    }
                    if data.get('_source_db'): row['_lib_override'] = data['_source_db']
                    processed_data.append(row)
                    
        return processed_data

    def _populate_table_with_rates(self, table, rates_data):
        """Fills a QTableWidget with the standardized rates_data list."""
        table.setRowCount(0)
        from PyQt6.QtGui import QColor
        
        for row_data in rates_data:
            row_idx = table.rowCount()
            table.insertRow(row_idx)
            
            # Determine display name for Library column
            lib_display = row_data.get('_lib_override', row_data.get('_library_name', ""))
            
            columns = [
                lib_display,
                row_data.get('rate_code'),
                row_data.get('project_name'),
                row_data.get('unit'),
                row_data.get('currency'),
                row_data.get('_rate_val'),
                row_data.get('_type_val'),
                row_data.get('date_created')
            ]
            
            db_path_str = row_data.get('_library_path', "")
            
            for col_idx, data in enumerate(columns):
                if col_idx == 5: # Rate
                    try:
                        display_text = f"{float(data):,.2f}" if data is not None else "0.00"
                    except:
                        display_text = str(data)
                else:
                    display_text = str(data) if data is not None else ""
                
                item = QTableWidgetItem(display_text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
                
                # Store metadata in Library column
                if col_idx == 0:
                    val_str = f"{row_data.get('id')}|{db_path_str}"
                    item.setData(Qt.ItemDataRole.UserRole, val_str)
                
                if col_idx == 1 or col_idx == 5: # Rate Code or Rate
                    font = item.font(); font.setBold(True); item.setFont(font)
                
                if col_idx == 6: # Rate Type colors
                    tp = str(data)
                    if tp == "Gross Rate": item.setForeground(Qt.GlobalColor.darkGreen)
                    elif tp == "Plug Rate": item.setForeground(QColor("#7b1fa2"))
                    elif tp == "Sub. Rate": item.setForeground(QColor("#e65100"))
                
                # Freeze all columns except Description
                if col_idx != 2:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                
                table.setItem(row_idx, col_idx, item)
        
        # Fit columns
        for i in range(table.columnCount()):
            if i == 2: table.setColumnWidth(i, 350)
            else: table.resizeColumnToContents(i)
        table.resizeRowsToContents()

    def load_rates(self):
        """Loads data from library databases into the table."""
        if not self.db_manager and not self.is_combined:
            return
            
        self.is_loading = True
        all_rates = []
        
        if self.is_combined:
            for i in range(self.library_combo.count()):
                lib_name = self.library_combo.itemText(i)
                lib_path = self.library_combo.itemData(i)
                if lib_path:
                    db = DatabaseManager(lib_path)
                    all_rates.extend(self._extract_rates_from_db(db, lib_name))
        else:
            if self.db_manager:
                lib_name = self.library_combo.currentText()
                all_rates.extend(self._extract_rates_from_db(self.db_manager, lib_name))
        
        # De-duplicate: If a Gross Rate exists for a code, suppress Plug/Sub for same code
        gross_codes = { r.get('rate_code') for r in all_rates if r.get('_type_val') == "Gross Rate" }
        seen_keys = set()
        deduped = []
        for r in all_rates:
            code = r.get('rate_code')
            rtype = r.get('_type_val')
            if code in gross_codes and rtype != "Gross Rate":
                continue
            key = (code, rtype)
            if key not in seen_keys:
                deduped.append(r)
                seen_keys.add(key)
        
        # Sort by code for readability
        deduped.sort(key=lambda x: x.get('rate_code', ''))
        
        self._populate_table_with_rates(self.table, deduped)
        self.is_loading = False

    def load_project_rates(self):
        """Loads data from the Project Database and all PBOQs into the table."""
        if not self.project_db_manager:
            return
            
        self.is_loading = True
        
        # 1. Gather all raw rates from Main Project DB
        raw_rates = []
        proj_lib_name = getattr(self, 'project_db_name', "Project Database")
        raw_rates.extend(self._extract_rates_from_db(self.project_db_manager, proj_lib_name))
        
        # 2. Gather all raw rates from Priced PBOQs
        target_managers = self.pboq_db_managers if hasattr(self, 'pboq_db_managers') and self.pboq_db_managers else []
        for manager in target_managers:
            lib_name = os.path.basename(manager.db_file)
            raw_rates.extend(self._extract_rates_from_db(manager, lib_name))
            
        # 3. Apply Unified De-duplication
        # We prioritize existing project Gross Rates. If a Gross Rate exists, 
        # we do NOT show discovered Plug/Sub Rates for the same code.
        gross_codes = { r.get('rate_code') for r in raw_rates if r.get('_type_val') == "Gross Rate" }
        seen_project_codes = set()
        
        all_project_rates = []
        for r in raw_rates:
            code = r.get('rate_code')
            rtype = r.get('_type_val')
            
            # Rule: Do not show Plug/Sub discovery if a Gross Rate already exists for this code
            if code in gross_codes and rtype != "Gross Rate":
                continue
                
            code_key = (code, rtype)
            if code_key not in seen_project_codes:
                all_project_rates.append(r)
                seen_project_codes.add(code_key)

        all_project_rates.sort(key=lambda x: x.get('rate_code', ''))
        
        self._populate_table_with_rates(self.project_table, all_project_rates)
        self.is_loading = False


    def open_rate_buildup(self, table, index):
        """Loads and shows the build-up for the selected rate."""
        row = index.row()
        val_str = table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        
        if val_str:
            db_id_str = val_str.split('|')[0]
            if db_id_str == "None":
                QMessageBox.information(self, "No Build-up", "This discovered rate has no build-up. Price it manually or using tools.")
                return
            db_id = int(db_id_str)
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
        highlight_color = _settings_db.get_setting("color_highlights") or "#ffffd9"
        from PyQt6.QtGui import QColor as _QC
        bg = _QC(highlight_color)
        
        from PyQt6.QtWidgets import QTableWidget
        # Search project table first, then library table
        for tbl in [self.project_table, self.table]:
            for row in range(tbl.rowCount()):
                item = tbl.item(row, 1) # Rate Code
                if item and item.text() == rate_code:
                    tbl.clearSelection()
                    tbl.scrollToItem(item, QTableWidget.ScrollHint.PositionAtCenter)
                    
                    self.is_loading = True
                    # Apply highlight color to the row
                    for col in range(tbl.columnCount()):
                        cell = tbl.item(row, col)
                        if cell:
                            cell.setBackground(bg)
                    self.is_loading = False        
                    return

    def filter_rates(self, text):
        query = text.lower()
        for row in range(self.table.rowCount()):
            item0 = self.table.item(row, 0) # Library
            item1 = self.table.item(row, 1) # Rate Code
            item2 = self.table.item(row, 2) # Description
            if item1 and item2:
                lib_match = query in item0.text().lower() if item0 else False
                id_match = query in item1.text().lower()
                desc_match = query in item2.text().lower()
                self.table.setRowHidden(row, not (lib_match or id_match or desc_match))

    def filter_project_rates(self, text):
        query = text.lower()
        for row in range(self.project_table.rowCount()):
            item0 = self.project_table.item(row, 0) # Library
            item1 = self.project_table.item(row, 1) # Rate Code
            item2 = self.project_table.item(row, 2) # Description
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
        if not val_str or val_str.split('|')[0] == "None":
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
            row = selected_indexes[0].row()
            rate_type = table.item(row, 6).text() if table.columnCount() > 6 and table.item(row, 6) else ""
            
            if table == self.project_table and rate_type in ["Plug Rate", "Sub. Rate"]:
                edit_action = QAction("Go-To", self)
                edit_action.triggered.connect(lambda checked=False, t=table: self.goto_pboq_row(t))
                menu.addAction(edit_action)
            else:
                edit_action = QAction("Edit Rate", self)
                edit_action.triggered.connect(lambda checked=False, t=table: self.edit_rate(t))
                menu.addAction(edit_action)
                
                # Add optional Go-To for Gross Rates in the Project Table
                if table == self.project_table and rate_type == "Gross Rate":
                    goto_action = QAction("Go-To", self)
                    goto_action.triggered.connect(lambda checked=False, t=table: self.goto_pboq_row(t))
                    menu.addAction(goto_action)
            
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

    def goto_pboq_row(self, table):
        """Finds the source PBOQ and row for the selected rate and navigates to it."""
        selected_indexes = table.selectionModel().selectedRows()
        if not selected_indexes or not self.main_window:
            return
            
        row = selected_indexes[0].row()
        lib_name = table.item(row, 0).text()  # The PBOQ file name
        rate_code = table.item(row, 1).text()
        
        # 1. Find the project root to find the bill file
        project_dir = ""
        if hasattr(self, 'project_db_manager') and self.project_db_manager:
            pdb_path = self.project_db_manager.db_file
            project_dir = os.path.dirname(os.path.dirname(pdb_path))
            
        if not project_dir:
            active_est = self.main_window._get_active_estimate_window()
            if active_est and hasattr(active_est, 'db_path') and active_est.db_path:
                project_dir = os.path.dirname(os.path.dirname(active_est.db_path))
                
        if not project_dir:
            project_dir = self.main_window.db_manager.get_setting('last_project_dir', '')
            
        if not project_dir:
            return
            
        # --- SMART REDIRECT ---
        # If the source is the Project Database (e.g., Two.db), it won't have a bill view alone.
        # We scan all PBOQs in the project to find where this rate is actually being used.
        proj_db_name = getattr(self, 'project_db_name', "Two.db")
        if lib_name.lower() == proj_db_name.lower():
            pboq_dir = os.path.join(project_dir, "Priced BOQs")
            if os.path.exists(pboq_dir):
                from database import DatabaseManager as _DB
                for f in os.listdir(pboq_dir):
                    if f.lower().endswith('.db'):
                        test_path = os.path.join(pboq_dir, f)
                        temp_db = _DB(test_path)
                        if rate_code in temp_db.get_pboq_rates_summary():
                            lib_name = f # Redirect lib_name to the bill filename
                            break
        # ----------------------

        bill_path = os.path.join(project_dir, "Priced BOQs", lib_name)
        if not os.path.exists(bill_path):
            # Try case-insensitive scan in Priced BOQs
            pboq_dir = os.path.join(project_dir, "Priced BOQs")
            if os.path.exists(pboq_dir):
                for f in os.listdir(pboq_dir):
                    if f.lower() == lib_name.lower():
                        bill_path = os.path.join(pboq_dir, f)
                        break
        
        if not os.path.exists(bill_path):
            # Fallback 1: Try Imported Library folder
            lib_dir = os.path.join(project_dir, "Imported Library")
            if os.path.exists(lib_dir):
                for f in os.listdir(lib_dir):
                    if f.lower() == lib_name.lower():
                        bill_path = os.path.join(lib_dir, f)
                        break
        
        if not os.path.exists(bill_path):
            # Fallback 2: Try Project Database folder (for main files like Two.db)
            db_dir = os.path.join(project_dir, "Project Database")
            if os.path.exists(db_dir):
                for f in os.listdir(db_dir):
                    if f.lower() == lib_name.lower():
                        bill_path = os.path.join(db_dir, f)
                        break

        if not os.path.exists(bill_path):
             QMessageBox.warning(self, "Error", f"Could not find source bill file: {lib_name}")
             return

        # 2. Find or open the PBOQDialog
        from pboq_viewer import PBOQDialog
        target_viewer = None
        for sub in self.main_window.mdi_area.subWindowList():
            win = sub.widget()
            if isinstance(win, PBOQDialog):
                # Check if it has the right project_dir
                if os.path.normpath(win.project_dir) == os.path.normpath(project_dir):
                    target_viewer = win
                    sub.setFocus()
                    break
        
        if not target_viewer:
            # Open new PBOQ viewer
            self.main_window.open_pboq_dialog() # This typically opens the project's PBOQ
            # Find the newly opened window
            for sub in self.main_window.mdi_area.subWindowList():
                win = sub.widget()
                if isinstance(win, PBOQDialog):
                    target_viewer = win
                    break
        
        if target_viewer:
            # 3. Ensure the correct bill is selected in the viewer
            selector = target_viewer.pboq_file_selector
            idx = selector.findText(lib_name)
            if idx >= 0:
                if selector.currentIndex() != idx:
                    selector.setCurrentIndex(idx)
                    target_viewer._load_pboq_db(idx)
                
                # 4. Highlight the row
                if not target_viewer.highlight_code(rate_code):
                    # Try finding it in description if rate_code not found
                    desc = table.item(row, 2).text()
                    target_viewer.highlight_code(desc)

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
        
        if val_str and val_str.split('|')[0] != "None":
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
        
        # Selected Rate is index 5
        try:
            rate_str = self.project_table.item(row, 5).text().replace(',', '')
            selected_rate = float(rate_str)
        except:
            selected_rate = 0.0
            
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
            
        count = sor_dialog._price_sor_with_rate(rate_desc, selected_rate, rate_code)
        if count > 0:
            QMessageBox.information(self, "Success", f"Successfully found and priced {count} SOR item(s) matching '{rate_desc}'.")
        else:
            QMessageBox.information(self, "No Match", f"No items matching '{rate_desc}' were found in the current SOR view.")

    def price_sor_from_keywords(self):
        """Finds SOR and prices items using currently defined keywords & selected rate."""
        selected_indexes = self.project_table.selectionModel().selectedRows()
        if not selected_indexes or self.project_table.rowCount() == 0:
            return
            
        row = selected_indexes[0].row()
        rate_code = self.project_table.item(row, 1).text()
        
        # Selected Rate is index 5
        try:
            rate_str = self.project_table.item(row, 5).text().replace(',', '')
            selected_rate = float(rate_str)
        except:
            selected_rate = 0.0
            
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
            
        count = sor_dialog._price_sor_with_keywords(selected_rate, rate_code)
        
        if count == -1:
            QMessageBox.warning(self, "No Keywords", "Please enter keywords in the SOR window first.")
        elif count > 0:
            QMessageBox.information(self, "Success", f"Successfully found and priced {count} SOR item(s) using current keywords.")
        else:
            QMessageBox.information(self, "No Match", "No items matching the current keywords were found in the SOR view.")
