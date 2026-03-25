import os
import sqlite3
import json
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QMessageBox, QComboBox, QTabWidget, QWidget,
                             QDockWidget, QApplication, QProgressDialog, QTableWidgetItem, QMenu,
                             QLineEdit, QPushButton)
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QColor, QBrush, QAction

import pboq_constants as const
from pboq_logic import PBOQLogic
from pboq_table import PBOQTable
from pboq_tools import PBOQToolsPane
from pboq_price import PBOQPricePane
from edit_item_dialog import EditItemDialog
from database import DatabaseManager
from pboq_plug_builder import PlugRateBuilderDialog
from subcontractor_adjudicator import PackageAdjudicatorDialog
from pboq_package_summary import PackageSummaryDialog

class PBOQDialog(QDialog):
    """Priced Bill of Quantities viewer - Modularized and Maintainable."""
    
    def __init__(self, project_dir, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self.project_dir = project_dir
        self.pboq_folder = os.path.join(self.project_dir, "Priced BOQs")
        
        self.logic = PBOQLogic()
        self.rowid_to_item0 = {}   # rowid -> QTableWidgetItem (the one in column 0)
        self.db_columns = []
        self.is_updating_logic = False
        self.clipboard_data = None  # Store copied rate data for Plug pricing
        
        self.setWindowTitle("Priced Bills of Quantities (PBOQ)")
        self.setMinimumSize(950, 400)
        
        self._init_ui()
        self._load_initial_configuration()

    def _init_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 5, 10, 10)
        
        # 0. Initialize Panes first (Top Bar needs them for signal connections)
        self.tools_pane = PBOQToolsPane(self)
        self.price_pane = PBOQPricePane(self)
        self.tools_pane.hide()
        self.price_pane.hide()

        # 1. Top Bar
        self._setup_top_bar()
        
        # 2. Tabs for Sheets
        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.TabPosition.South)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.main_layout.addWidget(self.tabs)
        
        # 3. Tools Pane (Docked)
        self.tools_dock = QDockWidget("PBOQ Tools", self.main_window)
        self.tools_dock.setWidget(self.tools_pane)
        self.tools_dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        
        if self.main_window:
            self.main_window.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.tools_dock)
            self.tools_dock.show()
            self.main_window.mdi_area.subWindowActivated.connect(self._on_mdi_subwindow_activated)
            self.destroyed.connect(self._cleanup_tools_dock)
            
        # Connect Tools Pane signals
        self.tools_pane.stateChanged.connect(self._save_pboq_state)
        self.tools_pane.columnHeadersRequested.connect(self._update_column_headers)
        self.tools_pane.wrapTextToggled.connect(self._toggle_wrap_text)
        self.tools_pane.alignTextLeftToggled.connect(self._toggle_left_align)
        self.tools_pane.clearGrossRequested.connect(self._clear_gross_and_code)
        self.tools_pane.extendRequested.connect(self._run_extend_logic)
        self.tools_pane.clearBillRequested.connect(self._clear_bill_rates)
        self.tools_pane.collectRequested.connect(self._run_collect_logic)
        self.tools_pane.stateChanged.connect(self._update_stats)
        
        # Connect Price Pane signals
        self.price_pane.rateVisibilityChanged.connect(self._toggle_rate_visibility)
        self.price_pane.stateChanged.connect(self._save_pboq_state)
        self.price_pane.stateChanged.connect(self._update_column_headers)
        self.price_pane.priceSORRequested.connect(self._run_price_sor_logic)
        self.price_pane.linkBillRateRequested.connect(self._run_link_bill_to_rate_logic)
        self.price_pane.clearPlugRequested.connect(self._clear_plug_and_code)
        self.price_pane.openAdjudicatorRequested.connect(self._open_package_adjudicator)
        self.price_pane.clearSubcontractorRequested.connect(self._clear_sub_and_code)
        self.price_pane.assignPackageRequested.connect(self._assign_package_to_selected)
        self.price_pane.managePackagesRequested.connect(self._open_packages_summary)

    def _setup_top_bar(self):
        top_bar = QHBoxLayout()
        top_bar.setSpacing(10)
        top_bar.setContentsMargins(0, 5, 0, 5)
        
        # File selector
        self.pboq_file_selector = QComboBox()
        self.pboq_file_selector.setMinimumWidth(250)
        if os.path.exists(self.pboq_folder):
            for f in sorted(os.listdir(self.pboq_folder)):
                if f.lower().endswith('.db'):
                    self.pboq_file_selector.addItem(f, os.path.join(self.pboq_folder, f))
        self.pboq_file_selector.activated.connect(self._load_pboq_db)
        top_bar.addWidget(QLabel("Select PBOQ:"))
        top_bar.addWidget(self.pboq_file_selector)
        
        # Search Bar
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search for items in sheet(s).")
        self.search_bar.setMinimumWidth(250)
        self.search_bar.textChanged.connect(self._run_global_search)
        top_bar.addWidget(self.search_bar)
        
        self.tool_toggle_btn = QPushButton("Price Tools")
        self.tool_toggle_btn.setFixedWidth(100)
        self.tool_toggle_btn.clicked.connect(self._switch_tool_pane)
        top_bar.addWidget(self.tool_toggle_btn)
        
        # Connect signals for global persistence as well
        self.tools_pane.wrapTextToggled.connect(self._save_viewer_state)
        self.tools_pane.alignTextLeftToggled.connect(self._save_viewer_state)
        
        # Stats
        self.stats_label = QLabel("Items: 0 | Priced: 0 | Outstanding: 0")
        self.stats_label.setStyleSheet("font-weight: bold; margin-left: 20px;")
        top_bar.addWidget(self.stats_label)
        
        top_bar.addStretch()
        self.main_layout.addLayout(top_bar)

    def _load_initial_configuration(self):
        state = self._load_viewer_state()
        last_bill = state.get('last_bill')
        if last_bill:
            index = self.pboq_file_selector.findText(last_bill)
            if index >= 0:
                self.pboq_file_selector.setCurrentIndex(index)
        
        # Apply pane visibility state
            if hasattr(self, 'tools_dock') and self.tools_dock:
                self.tools_dock.show()
        
        if self.pboq_file_selector.count() > 0:
            self._load_pboq_db(self.pboq_file_selector.currentIndex())

        # Restore tool pane selection
        if state.get('active_pane') == 'price':
            self._switch_tool_pane()
            
        # Restore global UI preferences
        if 'global_wrap' in state:
            self.tools_pane.wrap_text_btn.setChecked(state['global_wrap'])
            self._toggle_wrap_text(state['global_wrap'])
        if 'global_align_left' in state:
            self.tools_pane.align_left_btn.setChecked(state['global_align_left'])
            self._toggle_left_align(state['global_align_left'])

    def _load_pboq_db(self, index):
        if index < 0: return
        file_path = self.pboq_file_selector.itemData(index)
        self._save_viewer_state() # Save selection change
        
        self.tabs.blockSignals(True)
        # Clear existing tabs
        while self.tabs.count() > 0:
            self.tabs.removeTab(0)
            
        conn = self.logic.connect_db(file_path)
        if not conn: return
        
        success, result = self.logic.ensure_schema(conn)
        if not success:
            QMessageBox.warning(self, "Error", result)
            conn.close()
            return
            
        self.db_columns = result
        display_col_names = self.db_columns[1:]
        num_display_cols = len(display_col_names)
        
        formatting_data = self.logic.load_formatting(conn)
        cursor = conn.cursor()
        quoted_cols = [f'"{c}"' for c in self.db_columns]
        cursor.execute(f"SELECT rowid, {', '.join(quoted_cols)} FROM pboq_items")
        rows = cursor.fetchall()
        conn.close()
        
        self.rowid_to_item0 = {}
        sheet_groups = {}
        for g_idx, row in enumerate(rows):
            row_id = row[0]
            sheet_data = row[1:]
            sheet_name = str(sheet_data[0]) if sheet_data[0] else "Sheet 1"
            if sheet_name not in sheet_groups: sheet_groups[sheet_name] = []
            sheet_groups[sheet_name].append((g_idx, row_id, sheet_data[1:]))
            
        self.tools_pane.populate_column_combos(num_display_cols)
        
        progress = QProgressDialog("Loading Sheets...", None, 0, len(rows), self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)
        
        rows_loaded = 0
        try:
            for sheet_name, sheet_entries in sheet_groups.items():
                table = PBOQTable(self)
                table._is_loading = True
                table.setRowCount(len(sheet_entries))
                table.setColumnCount(num_display_cols)
                table.setHorizontalHeaderLabels([f"Column {i}" for i in range(num_display_cols)])
                table.cellUpdated.connect(self._handle_cell_updated)
                
                for r_idx, (global_row_idx, row_id, row_data) in enumerate(sheet_entries):
                    for c_idx in range(num_display_cols):
                        val = row_data[c_idx] if c_idx < len(row_data) else ""
                        m = self.tools_pane.get_mappings()
                        display_val = str(val) if val is not None else ""
                        
                        # Format Subbee Markup if mapped
                        if c_idx == m.get('sub_markup', -1) and display_val:
                            try:
                                f_val = float(display_val.replace('%','').replace(',',''))
                                display_val = "{:,.2f}%".format(f_val)
                            except: pass
                             
                        item = QTableWidgetItem(display_val)
                        
                        # Apply Default Column Color
                        def_color = table.get_column_default_color(c_idx)
                        if def_color: item.setBackground(def_color)

                        if c_idx == 0:
                            item.setData(Qt.ItemDataRole.UserRole, row_id)
                            self.rowid_to_item0[row_id] = item
                        item.setData(Qt.ItemDataRole.UserRole + 1, global_row_idx)
                        
                        # Apply Specific Saved Formatting (overwrites default)
                        fmt = formatting_data.get((global_row_idx, c_idx))
                        if fmt:
                            self._apply_item_format(item, fmt)
                        
                        if item.text() == "0.00":
                            item.setForeground(const.COLOR_GRAY_TEXT)
                            # Removed hardcoded AlignRight, will be handled by _update_column_headers
                            # item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                            
                        table.setItem(r_idx, c_idx, item)
                    
                    rows_loaded += 1
                    if rows_loaded % 100 == 0:
                        progress.setValue(rows_loaded)
                        QApplication.processEvents()
                    if progress.wasCanceled():
                        break
                
                    if progress.wasCanceled():
                        break
                
                table.resizeColumnsToContents()
                table._is_loading = False
                self.tabs.addTab(table, sheet_name)
                self._update_column_headers()
                if progress.wasCanceled():
                    break
            
            progress.setValue(len(rows))
        finally:
            progress.close()
            self.tabs.blockSignals(False)
            
        self._load_pboq_state(index)
        self._update_column_headers()
        self._update_stats()
        self._run_global_search(self.search_bar.text())

    def _handle_cell_updated(self, rowid, col_idx, new_val):
        """Called when a user manually edits a cell in the table."""
        self._persist_updates(col_idx, [(rowid, new_val)])

    def _run_global_search(self, text):
        """Filters rows in all sheets based on the search text."""
        text = text.lower()
        for i in range(self.tabs.count()):
            table = self.tabs.widget(i)
            if not isinstance(table, PBOQTable): continue
            
            for r in range(table.rowCount()):
                match = False
                if not text:
                    match = True
                else:
                    # Search in all visible columns
                    for c in range(table.columnCount()):
                        item = table.item(r, c)
                        if item and text in item.text().lower():
                            match = True
                            break
                table.setRowHidden(r, not match)

    def _apply_item_format(self, item, fmt):
        font = item.font()
        if fmt.get('bold'): font.setBold(True)
        if fmt.get('italic'): font.setItalic(True)
        item.setFont(font)
        if 'font_color' in fmt: item.setForeground(QColor(fmt['font_color']))
        if 'bg_color' in fmt: item.setBackground(QColor(fmt['bg_color']))

    def _handle_context_menu(self, table, pos, row, col, rowid):
        m = self.tools_pane.get_mappings()
        
        if col == m['bill_amount']:
            menu = QMenu(self)
            clear_act = menu.addAction("Clear")
            
            action = menu.exec(table.viewport().mapToGlobal(pos))
            if not action: return
            
            if action == clear_act:
                item = table.item(row, col)
                if item:
                    item.setText("")
                    self._persist_updates(col, [(rowid, "")])
                    self._update_stats()
        
        elif col == m.get('rate', -1):
            # Gross Rate context menu (not on Rate Code column)
            self._handle_rate_context_menu(table, pos, row, col, rowid, is_plug=False)
            
        elif col == m.get('plug_rate', -1):
            # Plug Rate context menu (not on Plug Code column)
            self._handle_rate_context_menu(table, pos, row, col, rowid, is_plug=True)

        elif col == m.get('sub_package', -1) and col >= 0:
            # Subcontractor Package context menu
            menu = QMenu(self)
            clear_action = menu.addAction("Clear Package Assignment")
            action = menu.exec(table.viewport().mapToGlobal(pos))
            
            if action == clear_action:
                selected_indexes = table.selectedIndexes()
                selected_rows = set(idx.row() for idx in selected_indexes) if selected_indexes else [row]
                
                updates = []
                for r in selected_rows:
                    it = table.item(r, col)
                    if it:
                        it.setText("")
                        rid = table.item(r, 0).data(Qt.ItemDataRole.UserRole)
                        updates.append((rid, ""))
                        
                if updates:
                    self._persist_updates(col, updates)
                    self._update_stats()

        elif col == m.get('sub_name', -1) and col >= 0:
            self._handle_subbee_assign_menu(table, pos, row, col, rowid)

    def _handle_subbee_assign_menu(self, table, pos, row, col, rowid):
        m = self.tools_pane.get_mappings()
        pkg_col = m.get('sub_package', -1)
        if pkg_col < 0: return
        
        # Get package name for this row
        pkg_item = table.item(row, pkg_col)
        pkg = pkg_item.text() if pkg_item else ""
        if not pkg: 
            return # Can't assign if no package exists
        
        # Query available quotes for this specific row and package
        db_path = self.pboq_file_selector.currentData()
        if not db_path:
            return
            
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT subcontractor_name, rate FROM subcontractor_quotes WHERE package_name=? AND row_idx=? AND rate > 0", (pkg, rowid))
            quotes = cursor.fetchall()
        except sqlite3.Error:
            quotes = []
        conn.close()
        
        menu = QMenu(self)
        assign_menu = menu.addMenu("Assign Item To...")
        
        if quotes:
            for sub_name, rate in quotes:
                act = assign_menu.addAction(f"{sub_name} (Rate: {rate:,.2f})")
                act.setData((sub_name, rate))
        else:
            assign_menu.addAction("No quotes available").setEnabled(False)
            
        menu.addSeparator()
        clear_act = menu.addAction("Clear Assignment")
        
        action = menu.exec(table.viewport().mapToGlobal(pos))
        if not action: return
        
        if action == clear_act:
            self._apply_item_subcontractor(table, row, col, rowid, "")
        elif action.data():
            sub_name, rate = action.data()
            self._apply_item_subcontractor(table, row, col, rowid, sub_name, rate)

    def _apply_item_subcontractor(self, table, row, name_col, rowid, sub_name, rate=None):
        """Surgically updates the Subcontractor Name and Subcontractor Rate directly (NOT Gross/Plug rate)."""
        m = self.tools_pane.get_mappings()
        rate_col = m.get('sub_rate', -1)
        
        # Update Name Column
        name_item = table.item(row, name_col)
        if name_item:
            name_item.setText(sub_name)
        self._persist_updates(name_col, [(rowid, sub_name)])
        
        # Update Rate Column
        if rate_col >= 0:
            rate_str = f"{rate:,.2f}" if rate is not None else ""
            rate_item = table.item(row, rate_col)
            if rate_item:
                rate_item.setText(rate_str)
            self._persist_updates(rate_col, [(rowid, rate_str)])
            
        self._update_stats()

    def _handle_rate_context_menu(self, table, pos, row, col, rowid, is_plug=True):
        """Standardized rate context menu based on the SOR Table design."""
        m = self.tools_pane.get_mappings()
        rate_role = 'plug_rate' if is_plug else 'rate'
        code_role = 'plug_code' if is_plug else 'rate_code'
        
        rate_col = m.get(rate_role, -1)
        code_col = m.get(code_role, -1)
        
        item_rate = table.item(row, rate_col) if rate_col >= 0 else None
        item_code = table.item(row, code_col) if code_col >= 0 else None
        
        rate_code = item_code.text().strip() if item_code else ""
        
        menu = QMenu(self)
        
        # 1. Build/Edit Rate
        action_text = "Edit Rate" if rate_code else "Build Rate"
        build_act = menu.addAction(action_text)
        
        # 2. Clear Rate
        clear_act = menu.addAction("Clear Rate")
        
        menu.addSeparator()
        
        # 3. Copy Rate
        copy_act = menu.addAction("Copy Rate")
        
        # 4. Paste Rate
        paste_act = menu.addAction("Paste Rate")
        if not self.clipboard_data:
            paste_act.setEnabled(False)
            
        menu.addSeparator()
        
        # 5. Go-To Rate
        goto_act = menu.addAction("Go-To Rate")
        if not rate_code:
            goto_act.setEnabled(False)
            
        action = menu.exec(table.viewport().mapToGlobal(pos))
        if not action: return
        
        if action == build_act:
            self._build_rate(table, row, rowid, is_plug)
        elif action == clear_act:
            self._clear_rate_at_row(table, row, rowid, is_plug)
        elif action == copy_act:
            self._copy_rate_info(table, row, is_plug)
        elif action == paste_act:
            self._paste_rate_info(table, row, rowid, is_plug)
        elif action == goto_act:
            if self.main_window and hasattr(self.main_window, 'show_rate_in_database'):
                self.main_window.show_rate_in_database(rate_code)

    def _copy_rate_info(self, table, row, is_plug):
        m = self.tools_pane.get_mappings()
        rate_col = m.get('plug_rate' if is_plug else 'rate', -1)
        code_col = m.get('plug_code' if is_plug else 'rate_code', -1)
        unit_col = m.get('unit', -1)
        
        if rate_col < 0 or code_col < 0: return
        
        self.clipboard_data = {
            'rate': table.item(row, rate_col).text() if table.item(row, rate_col) else "",
            'code': table.item(row, code_col).text() if table.item(row, code_col) else "",
            'unit': table.item(row, unit_col).text() if unit_col >= 0 and table.item(row, unit_col) else ""
        }
        if self.main_window:
            self.main_window.statusBar().showMessage(f"Rate {self.clipboard_data['code']} copied.", 2000)

    def _paste_rate_info(self, table, row, rowid, is_plug):
        if not self.clipboard_data: return
        m = self.tools_pane.get_mappings()
        unit_col = m.get('unit', -1)
        target_unit = table.item(row, unit_col).text().strip() if unit_col >= 0 and table.item(row, unit_col) else ""
        
        if self.clipboard_data['unit'].strip().lower() != target_unit.lower():
            QMessageBox.warning(self, "Unit Mismatch", 
                              f"Cannot paste. Units do not match!\nSource: {self.clipboard_data['unit']} vs Target: {target_unit}")
            return
            
        rate_role = 'plug_rate' if is_plug else 'rate'
        code_role = 'plug_code' if is_plug else 'rate_code'
        
        rate_col = m.get(rate_role, -1)
        code_col = m.get(code_role, -1)
        
        if rate_col >= 0:
            it = table.item(row, rate_col)
            if not it: it = QTableWidgetItem(); table.setItem(row, rate_col, it)
            it.setText(self.clipboard_data['rate'])
            self._persist_updates(rate_col, [(rowid, self.clipboard_data['rate'])])
            
        if code_col >= 0:
            it = table.item(row, code_col)
            if not it: it = QTableWidgetItem(); table.setItem(row, code_col, it)
            it.setText(self.clipboard_data['code'])
            self._persist_updates(code_col, [(rowid, self.clipboard_data['code'])])
        
        self._update_stats()

    def _clear_rate_at_row(self, table, row, rowid, is_plug):
        m = self.tools_pane.get_mappings()
        rate_col = m.get('plug_rate' if is_plug else 'rate', -1)
        code_col = m.get('plug_code' if is_plug else 'rate_code', -1)
        
        for c in [rate_col, code_col]:
            if c >= 0:
                item = table.item(row, c)
                if item:
                    item.setText("")
                    self._persist_updates(c, [(rowid, "")])
        self._update_stats()

    def _build_rate(self, table, row, rowid, is_plug):
        m = self.tools_pane.get_mappings()
        desc_col = m.get('desc', -1)
        unit_col = m.get('unit', -1)
        code_col = m.get('plug_code' if is_plug else 'rate_code', -1)
        rate_col = m.get('plug_rate' if is_plug else 'rate', -1)
        
        desc = table.item(row, desc_col).text().strip() if desc_col >= 0 and table.item(row, desc_col) else "New Rate"
        unit = table.item(row, unit_col).text().strip() if unit_col >= 0 and table.item(row, unit_col) else "m"
        rate_code = table.item(row, code_col).text().strip() if code_col >= 0 and table.item(row, code_col) else ""
        file_path = self.pboq_file_selector.currentData()
        
        if is_plug:
            # Fetch existing data from DB
            formula_val = ""
            category_val = ""
            currency_val = ""
            plug_code_val = ""
            plug_rate_val = 0.0
            ex_rates_json = "{}"
            
            try:
                conn = sqlite3.connect(file_path)
                cursor = conn.cursor()
                cursor.execute("SELECT PlugFormula, PlugCategory, PlugCurrency, PlugExchangeRates, PlugCode, PlugRate FROM pboq_items WHERE rowid = ?", (rowid,))
                res = cursor.fetchone()
                if res:
                    formula_val = res[0] or ""
                    category_val = res[1] or ""
                    currency_val = res[2] or ""
                    ex_rates_json = res[3] or "{}"
                    plug_code_val = res[4] or ""
                    try: plug_rate_val = float(str(res[5]).replace(',', '')) if res[5] else 0.0
                    except: plug_rate_val = 0.0
                conn.close()
            except: pass
            
            if plug_rate_val == 0.0 and rate_col >= 0:
                try: 
                    txt = table.item(row, rate_col).text().replace(',', '')
                    plug_rate_val = float(txt) if txt else 0.0
                except: pass

            ex_rates = {}
            try: ex_rates = json.loads(ex_rates_json)
            except: pass
            
            item_data = {
                'name': desc,
                'unit': unit,
                'rate': plug_rate_val,
                'formula': formula_val,
                'category': category_val,
                'currency': currency_val,
                'code': plug_code_val,
                'exchange_rates': ex_rates
            }
            
            # Open specialized Plug Rate Builder Dialog
            dialog = PlugRateBuilderDialog(item_data, self.project_dir, file_path, parent=self)
            if dialog.exec():
                new_rate_val = item_data.get('rate', 0.0)
                new_rate_str = f"{new_rate_val:,.2f}"
                new_formula = item_data.get('formula') or ""
                new_code = item_data.get('code') or ""
                new_cat = item_data.get('category') or ""
                new_curr = item_data.get('currency') or ""
                new_ex_rates = json.dumps(item_data.get('exchange_rates', {}))
                
                # Update UI and Physical Persistence
                if rate_col >= 0:
                    it = table.item(row, rate_col)
                    if not it: it = QTableWidgetItem(); table.setItem(row, rate_col, it)
                    it.setText(new_rate_str)
                    self._persist_updates(rate_col, [(rowid, new_rate_str)])
                
                if code_col >= 0:
                    it = table.item(row, code_col)
                    if not it: it = QTableWidgetItem(); table.setItem(row, code_col, it)
                    it.setText(new_code)
                    self._persist_updates(code_col, [(rowid, new_code)])
                
                # Update Logical Database Columns (Formula, Category, etc.)
                try:
                    conn = sqlite3.connect(file_path)
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE pboq_items 
                        SET PlugRate = ?, PlugFormula = ?, PlugCode = ?, PlugCategory = ?, PlugCurrency = ?, PlugExchangeRates = ?
                        WHERE rowid = ?
                    """, (new_rate_str, new_formula, new_code, new_cat, new_curr, new_ex_rates, rowid))
                    conn.commit()
                    conn.close()
                except: pass
                
                self._update_stats()
            return

        # Full Build-Up Logic (Gross Rate)
        from models import Estimate
        from rate_buildup_dialog import RateBuildUpDialog
        from database import DatabaseManager
        
        project_db_dir = os.path.join(self.project_dir, "Project Database")
        db_path = None
        if os.path.exists(project_db_dir):
            for f in os.listdir(project_db_dir):
                if f.endswith('.db'):
                    db_path = os.path.join(project_db_dir, f)
                    break
        
        if not db_path:
            QMessageBox.warning(self, "No Database", "No Project Database found to build rate into.")
            return

        db = DatabaseManager(db_path)
        
        if rate_code:
            from orm_models import DBEstimate
            est_id = None
            with db.Session() as session:
                db_est = session.query(DBEstimate).filter(DBEstimate.rate_code == rate_code).first()
                if db_est: est_id = db_est.id
            if est_id:
                estimate_obj = db.load_estimate_details(est_id)
                if estimate_obj and self.main_window:
                    self.main_window.open_rate_buildup_window(estimate_obj, db_path=db_path)
                return

        cat = "Miscellaneous"
        new_est = Estimate(project_name=desc, client_name="", overhead=15.0, profit=10.0, unit=unit)
        new_est.category = cat
        new_est.rate_code = db.generate_next_rate_code(cat)
        
        dialog = RateBuildUpDialog(new_est, main_window=self.main_window, parent=self, db_path=db_path)
        if dialog.exec():
            totals = dialog.estimate.calculate_totals()
            gross_rate = f"{totals.get('grand_total', 0.0):,.2f}"
            new_code = str(dialog.estimate.rate_code)
            
            if rate_col >= 0:
                it = table.item(row, rate_col)
                if not it: it = QTableWidgetItem(); table.setItem(row, rate_col, it)
                it.setText(gross_rate)
                self._persist_updates(rate_col, [(rowid, gross_rate)])
            
            if code_col >= 0:
                it = table.item(row, code_col)
                if not it: it = QTableWidgetItem(); table.setItem(row, code_col, it)
                it.setText(new_code)
                self._persist_updates(code_col, [(rowid, new_code)])
                
            self._update_stats()




    def _persist_updates(self, display_col, updates):
        if display_col < 0: return
        file_path = self.pboq_file_selector.currentData()
        self.logic.persist_batch_updates(file_path, self.db_columns, display_col, updates)
        
        # Mirroring Logic: Sync physical edits to logical "SubbeeName" / "SubbeePackage"
        m = self.tools_pane.get_mappings()
        if display_col == m.get('sub_name'):
             self.logic.persist_batch_named_updates(file_path, "SubbeeName", updates)
        elif display_col == m.get('sub_package'):
             self.logic.persist_batch_named_updates(file_path, "SubbeePackage", updates)

        # Trigger Collection update IF we are currently in "Revert" mode (meaning it was clicked once)
        # AND we are not already in a logic update.
        if display_col == m['bill_amount'] and not self.is_updating_logic:
            if self.tools_pane.collect_btn.text() == "Revert":
                self._run_collect_logic(force_collect=True)
        
        # Stats update is fast enough to keep live
        self._update_stats()



    def _update_stats(self):
        m = self.tools_pane.get_mappings()
        total, priced = 0, 0
        
        # Guard against unmapped columns
        if m['qty'] < 0:
            self.stats_label.setText("Map 'Quantity' column to see stats")
            return

        for i in range(self.tabs.count()):
            t = self.tabs.widget(i)
            if not isinstance(t, PBOQTable): continue
            
            for r in range(t.rowCount()):
                qty_item = t.item(r, m['qty'])
                if qty_item and qty_item.text().strip():
                    total += 1
                    # Determine which rate column to check for "priced" count
                    rate_col = m['rate']
                    if hasattr(self, 'price_pane') and self.price_pane.price_type_combo.currentText() == "Plug Rate":
                        rate_col = m.get('plug_rate', -1)
                        
                    if rate_col >= 0:
                        rate_item = t.item(r, rate_col)
                        if rate_item and rate_item.text().strip():
                            priced += 1
        
        outstanding = total - priced
        
        # Format with HTML for colors
        blue = const.COLOR_STATS_BLUE.name()
        green = const.COLOR_STATS_GREEN.name()
        red = const.COLOR_STATS_RED.name()
        
        # User requested: Items: blue, Priced: green, Outstanding: red
        stats_text = (
            f"Items: <span style='color:{blue}'>{total}</span> | "
            f"Priced: <span style='color:{green}'>{priced}</span> | "
            f"Outstanding: <span style='color:{red}'>{outstanding}</span>"
        )
        self.stats_label.setText(stats_text)

    def _on_tab_changed(self, index):
        self._save_pboq_state()

    def _on_mdi_subwindow_activated(self, sub):
        try:
            if hasattr(self, 'tools_dock') and self.tools_dock:
                if sub and sub.widget() is self: 
                    self.tools_dock.show()
                else: 
                    self.tools_dock.hide()
        except RuntimeError:
            # Object already deleted, ignore
            pass

    def _switch_tool_pane(self):
        """Switches between PBOQ Tools and Price Tools panes."""
        if self.tools_dock.widget() == self.tools_pane:
            self.tools_dock.setWidget(self.price_pane)
            self.tools_dock.setWindowTitle("Price Tools")
            self.tool_toggle_btn.setText("PBOQ Tools")
            
            # Apply current state of the price pane
            self._toggle_rate_visibility(self.price_pane.get_rate_visibility())
        else:
            self.tools_dock.setWidget(self.tools_pane)
            self.tools_dock.setWindowTitle("PBOQ Tools")
            self.tool_toggle_btn.setText("Price Tools")
        
        # Ensure dock is visible
        if not self.tools_dock.isVisible():
            self.tools_dock.show()
        
        self._save_viewer_state()

    def _toggle_rate_visibility(self, visible):
        """Hides or shows the relevant Rate and Code columns based on current Price Type."""
        m = self.tools_pane.get_mappings()
        price_type = self.price_pane.price_type_combo.currentText()
        
        # Identify active vs inactive pricing roles
        if price_type == "Plug Rate":
            active_cols = [m.get('plug_rate', -1), m.get('plug_code', -1)]
            inactive_cols = [m.get('rate', -1), m.get('rate_code', -1), m.get('sub_package', -1), m.get('sub_name', -1), m.get('sub_rate', -1), m.get('sub_markup', -1)]
        elif price_type == "Subcontractor Rate":
            active_cols = [m.get('sub_package', -1), m.get('sub_name', -1), m.get('sub_rate', -1), 
                           m.get('sub_markup', -1), m.get('sub_category', -1), m.get('sub_code', -1)]
            inactive_cols = [m.get('rate', -1), m.get('rate_code', -1), m.get('plug_rate', -1), m.get('plug_code', -1)]
        else: # Gross Rate or others
            active_cols = [m.get('rate', -1), m.get('rate_code', -1)]
            inactive_cols = [m.get('plug_rate', -1), m.get('plug_code', -1), 
                             m.get('sub_package', -1), m.get('sub_name', -1), m.get('sub_rate', -1), 
                             m.get('sub_markup', -1), m.get('sub_category', -1), m.get('sub_code', -1)]

        for i in range(self.tabs.count()):
            table = self.tabs.widget(i)
            if isinstance(table, PBOQTable):
                # 1. Handle Active Columns (Toggle based on checkbox)
                for col in active_cols:
                    if col >= 0:
                        table.setColumnHidden(col, not visible)
                
                # 2. Handle Inactive Columns (Always Hide in this mode)
                for col in inactive_cols:
                    # Only hide if it's not sharing a physical column with an active role
                    if col >= 0 and col not in active_cols:
                        table.setColumnHidden(col, True)


    def _toggle_wrap_text(self, enabled):
        m = self.tools_pane.get_mappings()
        desc_col = m.get('desc', -1)
        for i in range(self.tabs.count()):
            table = self.tabs.widget(i)
            if enabled and desc_col >= 0:
                # Ensure description column is not too wide for wrapping to be effective
                if table.columnWidth(desc_col) > 400:
                    table.setColumnWidth(desc_col, 400)
            table.set_word_wrap_enabled(enabled)

    def _toggle_left_align(self, enabled):
        """Forces Left alignment across the table based on the toggle."""
        self._update_column_headers()

    def _update_column_headers(self):
        m = self.tools_pane.get_mappings()
        
        friends = {
            'ref': "Ref/Item", 'desc': "Description", 'qty': "Quantity", 'unit': "Unit",
            'bill_rate': "Bill Rate", 'bill_amount': "Bill Amount",
            'rate': "Gross Rate", 'rate_code': "Rate Code",
            'plug_rate': "Plug Rate", 'plug_code': "Plug Code",
            'sub_package': "Subbee Package", 'sub_name': "Subbee Name", 
            'sub_rate': "Subbee Rate", 'sub_markup': "Subbee Markup (%)",
            'sub_category': "Subbee Category", 'sub_code': "Subbee Code"
        }
        
        map_inv = {v: k for k, v in m.items() if v >= 0}
        
        for idx in range(self.tabs.count()):
            table = self.tabs.widget(idx)
            if not isinstance(table, PBOQTable): continue
            
            headers = []
            for i in range(table.columnCount()):
                role = map_inv.get(i)
                name = friends.get(role, f"Column {i}")
                headers.append(name)
                
                # Automatically hide blank/extra columns beyond the standard pricing range (16 columns)
                # but only if they aren't mapped to anything.
                if i >= 16:
                    table.setColumnHidden(i, role is None)
                else:
                    # Ensure standard columns (0-7) are visible so user can map them
                    table.setColumnHidden(i, False)
            
            table.setHorizontalHeaderLabels(headers)
            
            # Apply heading color and blue text to the header items directly
            # This is more robust than Palette when a global stylesheet is present
            for i in range(table.columnCount()):
                item = table.horizontalHeaderItem(i)
                if item:
                    item.setBackground(const.COLOR_HEADING)
                    # Only use blue (COLOR_HEADER_TEXT) for mapped columns
                    if map_inv.get(i) is not None:
                        item.setForeground(const.COLOR_HEADER_TEXT)
                        font = item.font()
                        font.setBold(True)
                        item.setFont(font)
                    else:
                        item.setForeground(Qt.GlobalColor.black)
            
            # Update columns identifying colors across sheets
            table.apply_column_colors(m, table.columnCount())
            
            # Apply dynamic alignment
            table.apply_column_alignment(self.tools_pane.align_left_btn.isChecked(), m)
        
        # Ensure Rate visibility is synced with current mapping
        self._toggle_rate_visibility(self.price_pane.get_rate_visibility())
        
        # Sync the Logical Backplane (ensure SubbeeName column has latest award data)
        self._sync_logical_assignment_columns()

        self._update_stats()

    def _sync_logical_assignment_columns(self):
        """Backfills the hidden 'SubbeeName' and 'SubbeePackage' columns from whatever physical columns are currently mapped."""
        m = self.tools_pane.get_mappings()
        name_idx = m.get('sub_name', -1)
        pkg_idx = m.get('sub_package', -1)
        if name_idx < 0 and pkg_idx < 0: return

        file_path = self.pboq_file_selector.currentData()
        name_updates, pkg_updates = [], []
        
        for i in range(self.tabs.count()):
            table = self.tabs.widget(i)
            if not isinstance(table, PBOQTable): continue
            for r in range(table.rowCount()):
                rowid = table.item(r, 0).data(Qt.ItemDataRole.UserRole)
                if name_idx >= 0:
                    item = table.item(r, name_idx)
                    val = item.text().strip() if item else ""
                    name_updates.append((rowid, val))
                if pkg_idx >= 0:
                    item = table.item(r, pkg_idx)
                    val = item.text().strip() if item else ""
                    pkg_updates.append((rowid, val))
        
        if name_updates: self.logic.persist_batch_named_updates(file_path, "SubbeeName", name_updates)
        if pkg_updates: self.logic.persist_batch_named_updates(file_path, "SubbeePackage", pkg_updates)

    # --- Worker Logic Methods ---

    def _run_extend_logic(self):
        m = self.tools_pane.get_mappings()
        if m['qty'] < 0 or m['bill_rate'] < 0:
            QMessageBox.warning(self, "Mapping Required", "Map Qty and Bill Rate columns.")
            return

        is_revert = self.tools_pane.extend_btn.text() == "Revert"
        d_rate = self.tools_pane.dummy_rate_spin.value()
        d_rate_str = "{:,.2f}".format(d_rate)
        
        rate_updates, amt_updates = [], []
        
        checked_cols = []
        if self.tools_pane.extend_cb0.isChecked(): checked_cols.append(0)
        if self.tools_pane.extend_cb1.isChecked(): checked_cols.append(1)
        if self.tools_pane.extend_cb2.isChecked(): checked_cols.append(2)
        if self.tools_pane.extend_cb3.isChecked(): checked_cols.append(3)

        for i in range(self.tabs.count()):
            table = self.tabs.widget(i)
            for r in range(table.rowCount()):
                rowid = table.item(r, 0).data(Qt.ItemDataRole.UserRole)
                rate_item = table.item(r, m['bill_rate'])
                g_idx = table.item(r, 0).data(Qt.ItemDataRole.UserRole + 1)
                
                if is_revert:
                    if rate_item and rate_item.text() == d_rate_str and rate_item.foreground().color().name().lower() == const.COLOR_GRAY_TEXT.name().lower():
                        rate_item.setText("")
                        rate_item.setForeground(Qt.GlobalColor.black)
                        rate_updates.append((rowid, ""))
                        if g_idx is not None: self.logic.clear_cell_formatting(self.pboq_file_selector.currentData(), g_idx, m['bill_rate'])
                        if m['bill_amount'] >= 0:
                            amt_item = table.item(r, m['bill_amount'])
                            if amt_item: 
                                amt_item.setText("")
                                amt_item.setForeground(Qt.GlobalColor.black)
                            amt_updates.append((rowid, ""))
                            if g_idx is not None: self.logic.clear_cell_formatting(self.pboq_file_selector.currentData(), g_idx, m['bill_amount'])
                else:
                    # Extend Logic
                    if not checked_cols: continue
                    is_aligned = all(table.item(r, c) and table.item(r, c).text().strip() for c in checked_cols)
                    if not is_aligned: continue
                    
                    qty_item = table.item(r, m['qty'])
                    if not qty_item or not qty_item.text().strip(): continue
                    
                    # Already has a rate?
                    if rate_item and rate_item.text().strip(): continue
                    
                    try:
                        qty_val = float(qty_item.text().replace(',', ''))
                        if qty_val <= 0: continue
                        
                        if not rate_item:
                            rate_item = QTableWidgetItem()
                            table.setItem(r, m['bill_rate'], rate_item)
                        
                        rate_item.setText(d_rate_str)
                        rate_item.setForeground(const.COLOR_GRAY_TEXT)
                        rate_updates.append((rowid, d_rate_str))
                        
                        if m['bill_amount'] >= 0:
                            amt_val = qty_val * d_rate
                            amt_str = "{:,.2f}".format(amt_val)
                            amt_item = table.item(r, m['bill_amount'])
                            if not amt_item:
                                amt_item = QTableWidgetItem()
                                table.setItem(r, m['bill_amount'], amt_item)
                            amt_item.setText(amt_str)
                            amt_item.setForeground(const.COLOR_GRAY_TEXT)
                            amt_updates.append((rowid, amt_str))
                    except ValueError: continue

        if rate_updates:
            self._persist_updates(m['bill_rate'], rate_updates)
            # Persist gray color for rates
            fmt_updates = [(self.rowid_to_item0[rid].data(Qt.ItemDataRole.UserRole + 1), {'font_color': const.COLOR_GRAY_TEXT.name()}) for rid, _ in rate_updates]
            self.logic.persist_batch_cell_formatting(self.pboq_file_selector.currentData(), m['bill_rate'], fmt_updates)

            if amt_updates: 
                self._persist_updates(m['bill_amount'], amt_updates)
                # Persist gray color for amounts
                fmt_amt_updates = [(self.rowid_to_item0[rid].data(Qt.ItemDataRole.UserRole + 1), {'font_color': const.COLOR_GRAY_TEXT.name()}) for rid, _ in amt_updates]
                self.logic.persist_batch_cell_formatting(self.pboq_file_selector.currentData(), m['bill_amount'], fmt_amt_updates)
            
            self.tools_pane.extend_btn.setText("Extend" if is_revert else "Revert")
            self._update_column_headers()
            QMessageBox.information(self, "Success", f"Processed {len(rate_updates)} rows.")

    def _clear_bill_rates(self):
        m = self.tools_pane.get_mappings()
        d_rate_str = "{:,.2f}".format(self.tools_pane.dummy_rate_spin.value())
        updates = []
        for i in range(self.tabs.count()):
            t = self.tabs.widget(i)
            for r in range(t.rowCount()):
                item = t.item(r, m['bill_rate'])
                if item and item.text() == d_rate_str:
                    item.setText("")
                    rowid = t.item(r, 0).data(Qt.ItemDataRole.UserRole)
                    updates.append((rowid, ""))
        if updates: self._persist_updates(m['bill_rate'], updates)

    def _run_collect_logic(self, force_collect=False):
        m = self.tools_pane.get_mappings()
        if m['desc'] < 0 or m['bill_amount'] < 0: return
        
        # Start logical update session
        self.is_updating_logic = True
        try:
            # We are "reverting" strictly if the button says Revert AND we aren't forcing a collect update
            is_revert_action = self.tools_pane.collect_btn.text() == "Revert" and not force_collect
            kw = self.tools_pane.collect_search_bar.text().lower().strip()
            
            # Options from UI
            search_desc = self.tools_pane.collect_desc_cb.isChecked()
            search_amt = self.tools_pane.collect_amount_cb.isChecked()
            
            updates = []
            
            for i in range(self.tabs.count()):
                t = self.tabs.widget(i)
                if not isinstance(t, PBOQTable): continue
                
                cur_sum = 0.0
                for r in range(t.rowCount()):
                    item_desc = t.item(r, m['desc'])
                    item_amt = t.item(r, m['bill_amount'])
                    rowid = t.item(r, 0).data(Qt.ItemDataRole.UserRole)
                    g_idx = item_amt.data(Qt.ItemDataRole.UserRole + 1) if item_amt else None
                    
                    if is_revert_action:
                        # Clear only collected items
                        if item_amt and item_amt.background().color().name().lower() == const.COLOR_COLLECT.name().lower():
                            item_amt.setText("")
                            def_color = t.get_column_default_color(m['bill_amount'])
                            item_amt.setBackground(def_color if def_color else QBrush())
                            item_amt.setForeground(Qt.GlobalColor.black)
                            updates.append((rowid, ""))
                            if g_idx is not None: 
                                self.logic.clear_cell_formatting(self.pboq_file_selector.currentData(), g_idx, m['bill_amount'])
                    else:
                        if not kw: 
                            # If no keyword and not reverting, we can't search
                            continue
                        
                        # Check for matches based on user selection
                        match = False
                        if search_desc and item_desc and kw in item_desc.text().lower():
                            match = True
                        if not match and search_amt and item_amt and kw in item_amt.text().lower():
                            match = True
                            
                        if match:
                            if not item_amt:
                                item_amt = QTableWidgetItem()
                                t.setItem(r, m['bill_amount'], item_amt)
                            
                            f_sum = "{:,.2f}".format(cur_sum)
                            item_amt.setText(f_sum)
                            item_amt.setBackground(const.COLOR_COLLECT)
                            item_amt.setForeground(const.COLOR_GRAY_TEXT)
                            updates.append((rowid, f_sum))
                            cur_sum = 0.0
                        else:
                            # Add to sum if not a logic cell
                            if item_amt and item_amt.text().strip():
                                bg_hex = item_amt.background().color().name().lower()
                                is_logic = bg_hex == const.COLOR_COLLECT.name().lower()
                                
                                if not is_logic:
                                    try: 
                                        val = float(item_amt.text().replace(',', ''))
                                        cur_sum += val
                                    except ValueError: pass
            
            if updates:
                self._persist_updates(m['bill_amount'], updates)
                if not is_revert_action:
                    fmt_updates = []
                    for rid, val in updates:
                        if val == "": continue 
                        item0 = self.rowid_to_item0.get(rid)
                        if item0:
                            g_idx = item0.data(Qt.ItemDataRole.UserRole + 1)
                            if g_idx is not None:
                                fmt_updates.append((g_idx, {'bg_color': const.COLOR_COLLECT.name(), 'font_color': const.COLOR_GRAY_TEXT.name()}))
                    
                    if fmt_updates:
                        self.logic.persist_batch_cell_formatting(self.pboq_file_selector.currentData(), m['bill_amount'], fmt_updates)
            
            # Update button text manually based on action just taken
            if is_revert_action:
                self.tools_pane.collect_btn.setText("Collect")
            elif kw:
                self.tools_pane.collect_btn.setText("Revert")
            
            self._update_column_headers()
            self._save_pboq_state()
        finally:
            self.is_updating_logic = False

    def _clear_gross_and_code(self):
        m = self.tools_pane.get_mappings()
        rate_col = m['rate']
        code_col = m['rate_code']
        self._clear_columns([rate_col, code_col], "Gross Rate & Code")

    def _clear_plug_and_code(self):
        m = self.tools_pane.get_mappings()
        rate_col = m.get('plug_rate', -1)
        code_col = m.get('plug_code', -1)
        self._clear_columns([rate_col, code_col], "Plug Rate & Code")

    def _clear_sub_and_code(self):
        m = self.tools_pane.get_mappings()
        pkg_col = m.get('sub_package', -1)
        name_col = m.get('sub_name', -1)
        rate_col = m.get('sub_rate', -1)
        markup_col = m.get('sub_markup', -1)
        
        custom_warning = (
            "WARNING: All existing Subcontractors data will be deleted.\n\n"
            "This will permanently clear all Subcontractor assignments, markups, "
            "and all stored quotes within this PBOQ file.\n\n"
            "Are you absolutely sure you wish to proceed?"
        )
        self._clear_columns([pkg_col, name_col, rate_col, markup_col], "Subcontractor Package, Name, Rate & Markup", custom_prompt=custom_warning, is_subbee=True)

    def _clear_columns(self, col_indices, label, custom_prompt=None, is_subbee=False):
        """Generic helper to clear one or more columns across all sheets."""
        if all(c < 0 for c in col_indices):
            QMessageBox.warning(self, "Clear", f"Please map the {label} columns first.")
            return

        prompt = custom_prompt if custom_prompt else f"Are you sure you want to clear {label} content in ALL sheets?"
        
        if custom_prompt:
            confirm = QMessageBox.warning(self, "Clear Data Warning", prompt, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        else:
            confirm = QMessageBox.question(self, "Clear Data", prompt, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            
        if confirm != QMessageBox.StandardButton.Yes: return
        
        # If this is specifically the subcontractor clear, wipe the quotes DB table for this PBOQ too
        if is_subbee:
            try:
                pboq_db_path = self.pboq_file_selector.itemData(self.pboq_file_selector.currentIndex())
                import sqlite3
                conn = sqlite3.connect(pboq_db_path)
                cursor = conn.cursor()
                cursor.execute("DELETE FROM subcontractor_quotes") # Wipe quotes
                conn.commit()
                conn.close()
            except Exception as e:
                print(f"Failed to clear subcontractor_quotes table: {e}")

        for i in range(self.tabs.count()):
            t = self.tabs.widget(i)
            if not isinstance(t, PBOQTable): continue
            
            updates_by_col = {c: [] for c in col_indices if c >= 0}
            
            for r in range(t.rowCount()):
                rowid = t.item(r, 0).data(Qt.ItemDataRole.UserRole)
                for c in col_indices:
                    if c >= 0:
                        item = t.item(r, c)
                        if item:
                            item.setText("")
                            updates_by_col[c].append((rowid, ""))
            
            for c, updates in updates_by_col.items():
                if updates:
                    self._persist_updates(c, updates)
        
        QMessageBox.information(self, "Clear", f"{label} cleared successfully.")
        self._update_stats()

    # --- State Management ---
    def _save_pboq_state(self):
        idx = self.pboq_file_selector.currentIndex()
        if idx < 0: return
        file_path = self.pboq_file_selector.itemData(idx)
        state_dir = os.path.join(self.project_dir, "PBOQ States")
        os.makedirs(state_dir, exist_ok=True)
        
        state = self.tools_pane.get_tools_state()
        state['active_tab'] = self.tabs.currentIndex()
        if hasattr(self, 'price_pane'):
            state['price_tools'] = self.price_pane.get_state()
        
        state_file = os.path.join(state_dir, os.path.basename(file_path) + ".json")
        with open(state_file, 'w') as f:
            json.dump(state, f)

    def _load_pboq_state(self, index):
        file_path = self.pboq_file_selector.itemData(index)
        state_file = os.path.join(self.project_dir, "PBOQ States", os.path.basename(file_path) + ".json")
        if os.path.exists(state_file):
            with open(state_file, 'r') as f:
                state = json.load(f)
                self.tools_pane.set_tools_state(state)
                if 'price_tools' in state and hasattr(self, 'price_pane'):
                    self.price_pane.set_state(state['price_tools'])
                    # Apply initial visibility
                    self._toggle_rate_visibility(self.price_pane.get_rate_visibility())
                
                self.tabs.setCurrentIndex(state.get('active_tab', 0))
                # Apply word wrap state after loading
                self._toggle_wrap_text(self.tools_pane.wrap_text_btn.isChecked())
                self._toggle_left_align(self.tools_pane.align_left_btn.isChecked())
                
                # If sticky mode was active, refresh it
                if self.tools_pane.collect_btn.text() == "Revert":
                    self._run_collect_logic(force_collect=True)

    def _save_viewer_state(self):
        settings_file = os.path.join(self.project_dir, "PBOQ States", "viewer_state.json")
        os.makedirs(os.path.dirname(settings_file), exist_ok=True)
        
        state = {
            'last_bill': self.pboq_file_selector.currentText(),
            'active_pane': 'price' if hasattr(self, 'price_pane') and self.tools_dock.widget() == self.price_pane else 'tools',
            'global_wrap': self.tools_pane.wrap_text_btn.isChecked(),
            'global_align_left': self.tools_pane.align_left_btn.isChecked()
        }
        
        with open(settings_file, 'w') as f:
            json.dump(state, f)

    def _load_viewer_state(self):
        settings_file = os.path.join(self.project_dir, "PBOQ States", "viewer_state.json")
        if os.path.exists(settings_file):
            with open(settings_file, 'r') as f:
                state_data = json.load(f)
                if isinstance(state_data, dict):
                    return state_data
                return {'last_bill': state_data}
        return {}

    def _run_price_sor_logic(self, apply_price):
        """Performs multi-column strict matching against SOR database to price PBOQ items."""
        if not apply_price:
            self._revert_sor_pricing()
            return

        # 1. Identify SOR file
        pboq_filename = self.pboq_file_selector.currentText()
        if pboq_filename.startswith("PBOQ_"):
            sor_filename = "SOR_" + pboq_filename[5:]
        else:
            sor_filename = "SOR_" + pboq_filename
            
        sor_path = os.path.join(self.project_dir, "SOR", sor_filename)
        if not sor_path.endswith(".db"): sor_path += ".db"
            
        if not os.path.exists(sor_path):
            QMessageBox.warning(self, "SOR Not Found", f"Could not find matching SOR file for Bill: {sor_filename}")
            # Reset button state
            self.price_pane.gross_rate_tool.price_sor_btn.blockSignals(True)
            self.price_pane.gross_rate_tool.price_sor_btn.setText("Price with SOR")
            self.price_pane.gross_rate_tool.price_sor_btn.blockSignals(False)
            return

        # 2. Helper functions for robust matching
        def normalize_desc(d):
            if not d: return ""
            return str(d).rsplit(':', 1)[-1].strip().lower()

        def normalize_qty(q):
            try:
                # Remove commas and convert to float for comparison
                clean = str(q).replace(',', '').strip()
                if not clean: return "0.00"
                return "{:.2f}".format(float(clean))
            except (ValueError, TypeError):
                return str(q).strip().lower()

        # 3. Get Mappings
        mapping = self.tools_pane.get_mappings()
        if mapping['desc'] < 0 or mapping['qty'] < 0 or mapping['rate'] < 0 or mapping['rate_code'] < 0:
            QMessageBox.warning(self, "Mapping Error", "Please ensure Description, Quantity, Gross Rate, and Rate Code columns are mapped in the Tools Pane first.")
            self.price_pane.gross_rate_tool.price_sor_btn.blockSignals(True)
            self.price_pane.gross_rate_tool.price_sor_btn.setText("Price with SOR")
            self.price_pane.gross_rate_tool.price_sor_btn.blockSignals(False)
            return

        # 4. Load SOR data into a lookup map
        sor_lookup = {}
        try:
            conn = sqlite3.connect(sor_path)
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(sor_items)")
            cols = [info[1] for info in cursor.fetchall()]
            
            query = "SELECT Sheet, Ref, Description, Quantity, Unit"
            query += ", GrossRate" if "GrossRate" in cols else ", NULL"
            query += ", RateCode" if "RateCode" in cols else ", NULL"
            query += " FROM sor_items"
            
            cursor.execute(query)
            for row in cursor.fetchall():
                sheet, ref, desc, qty, unit, gross, code = row
                if not (gross or code): continue
                
                # Normalize key
                key = (str(sheet).strip().lower(), 
                       str(ref).strip().lower(), 
                       normalize_desc(desc), 
                       normalize_qty(qty), 
                       str(unit).strip().lower())
                sor_lookup[key] = (gross, code)
            conn.close()
        except Exception as e:
            QMessageBox.critical(self, "SOR Error", f"Failed to load SOR database for cross-referencing:\n{e}")
            return

        # 5. Iterate PBOQ tabs and price
        priced_count = 0
        pboq_db_path = self.pboq_file_selector.itemData(self.pboq_file_selector.currentIndex())
        price_updates = []

        for i in range(self.tabs.count()):
            sheet_name = self.tabs.tabText(i).strip().lower()
            table = self.tabs.widget(i)
            if not isinstance(table, PBOQTable): continue
            
            for r in range(table.rowCount()):
                row_id_item = table.item(r, 0)
                if not row_id_item: continue
                row_id = row_id_item.data(Qt.ItemDataRole.UserRole)
                
                # Extract PBOQ values
                p_ref = table.item(r, mapping['ref']).text().strip().lower() if mapping['ref'] >= 0 else ""
                p_desc_full = table.item(r, mapping['desc']).text().strip()
                p_qty_raw = table.item(r, mapping['qty']).text().strip()
                p_unit = table.item(r, mapping['unit']).text().strip().lower() if mapping['unit'] >= 0 else ""
                
                p_desc_tail = normalize_desc(p_desc_full)
                p_qty = normalize_qty(p_qty_raw)
                
                key = (sheet_name, p_ref, p_desc_tail, p_qty, p_unit)
                
                if key in sor_lookup:
                    gross, code = sor_lookup[key]
                    gross_item = table.item(r, mapping['rate'])
                    code_item = table.item(r, mapping['rate_code'])
                    
                    # Store original values for revert if not already stored
                    if not gross_item.data(Qt.ItemDataRole.UserRole + 10):
                        gross_item.setData(Qt.ItemDataRole.UserRole + 11, gross_item.text())
                        code_item.setData(Qt.ItemDataRole.UserRole + 11, code_item.text())
                        
                    gross_item.setText(str(gross) if gross else "")
                    code_item.setText(str(code) if code else "")
                    
                    # Mark as SOR priced
                    gross_item.setData(Qt.ItemDataRole.UserRole + 10, True)
                    code_item.setData(Qt.ItemDataRole.UserRole + 10, True)
                    
                    # Highlight row (Light Green)
                    for c in range(table.columnCount()):
                        table.item(r, c).setBackground(QColor("#e8f5e9"))
                        
                    price_updates.append((row_id, gross, code))
                    priced_count += 1

        # 6. Persist to PBOQ DB
        if price_updates:
            try:
                conn = sqlite3.connect(pboq_db_path)
                cursor = conn.cursor()
                if mapping['rate'] < 0 or mapping['rate_code'] < 0:
                    conn.close()
                    return
                gross_col_name = self.db_columns[mapping['rate'] + 1]
                code_col_name = self.db_columns[mapping['rate_code'] + 1]
                
                for row_id, gross, code in price_updates:
                    cursor.execute(f'UPDATE pboq_items SET "{gross_col_name}" = ?, "{code_col_name}" = ? WHERE rowid = ?',
                                 (gross, code, row_id))
                conn.commit()
                conn.close()
            except Exception as e:
                 QMessageBox.critical(self, "DB Error", f"Prices were applied to UI but failed to persist to project database:\n{e}")

        if priced_count > 0:
            QMessageBox.information(self, "Pricing Successful", f"Found and applied matching rates for {priced_count} items using the project SOR.")
        else:
            QMessageBox.information(self, "No Matches", "No matching items were found in the SOR for the current PBOQ view using strict validation.\n\nTips:\n- Ensure the 'Sheet' names in SOR match the PBOQ tab names.\n- Ensure Quantity values are identical (including decimal precision).")
            # Reset button state
            self.price_pane.gross_rate_tool.price_sor_btn.blockSignals(True)
            self.price_pane.gross_rate_tool.price_sor_btn.setText("Price with SOR")
            self.price_pane.gross_rate_tool.price_sor_btn.blockSignals(False)

        self._update_stats()

    def _revert_sor_pricing(self):
        """Reverts Gross Rate and Rate Code to their original state before SOR pricing."""
        pboq_db_path = self.pboq_file_selector.itemData(self.pboq_file_selector.currentIndex())
        mapping = self.tools_pane.get_mappings()
        
        if mapping['rate'] < 0 or mapping['rate_code'] < 0:
            QMessageBox.warning(self, "Mapping Error", "Gross Rate or Rate Code columns are not mapped. Cannot revert correctly.")
            return

        revert_count = 0
        db_updates = []

        for i in range(self.tabs.count()):
            table = self.tabs.widget(i)
            if not isinstance(table, PBOQTable): continue
            
            for r in range(table.rowCount()):
                gross_item = table.item(r, mapping['rate'])
                if gross_item and gross_item.data(Qt.ItemDataRole.UserRole + 10):
                    row_id_item = table.item(r, 0)
                    if not row_id_item: continue
                    row_id = row_id_item.data(Qt.ItemDataRole.UserRole)
                    code_item = table.item(r, mapping['rate_code'])
                    
                    # Restore original values
                    orig_gross = gross_item.data(Qt.ItemDataRole.UserRole + 11)
                    orig_code = code_item.data(Qt.ItemDataRole.UserRole + 11)
                    
                    # Ensure we handle None/empty correctly for "clearing"
                    new_gross = str(orig_gross) if orig_gross is not None else ""
                    new_code = str(orig_code) if orig_code is not None else ""
                    
                    gross_item.setText(new_gross)
                    code_item.setText(new_code)
                    
                    # Clear SOR flags
                    gross_item.setData(Qt.ItemDataRole.UserRole + 10, None)
                    code_item.setData(Qt.ItemDataRole.UserRole + 10, None)
                    
                    # Reset colors
                    for c in range(table.columnCount()):
                        table.item(r, c).setBackground(QBrush(Qt.BrushStyle.NoBrush))
                        def_color = table.get_column_default_color(c)
                        if def_color: table.item(r, c).setBackground(def_color)
                        
                    db_updates.append((row_id, new_gross, new_code))
                    revert_count += 1

        if db_updates:
            try:
                conn = sqlite3.connect(pboq_db_path)
                cursor = conn.cursor()
                gross_col_name = self.db_columns[mapping['gross_rate'] + 1]
                code_col_name = self.db_columns[mapping['rate_code'] + 1]
                
                for row_id, gross, code in db_updates:
                    cursor.execute(f'UPDATE pboq_items SET "{gross_col_name}" = ?, "{code_col_name}" = ? WHERE rowid = ?',
                                 (gross, code, row_id))
                conn.commit()
                conn.close()
                QMessageBox.information(self, "Reverted", f"Successfully reverted {revert_count} items to their original pricing.")
            except Exception as e:
                QMessageBox.critical(self, "DB Revert Error", f"UI was reverted but database update failed:\n{e}")
        else:
             QMessageBox.information(self, "Revert", "No SOR-priced items found to revert in the current view.")

        self._update_stats()

    def _run_link_bill_to_rate_logic(self):
        """Batch copies current Rate (Gross or Plug) to Bill Rates and recalculates Bill Amounts."""
        m = self.tools_pane.get_mappings()
        
        # Determine source rate column based on current Price Type
        price_type = self.price_pane.price_type_combo.currentText()
        markup_pct = 0.0
        
        if price_type == "Plug Rate":
            source_col_key = 'plug_rate'
            source_label = "Plug Rate"
        elif price_type == "Subcontractor Rate":
            source_col_key = 'sub_rate'
            source_label = "Subcontractor Rate"
        else:
            source_col_key = 'rate' # Default to Gross Rate
            source_label = "Gross Rate"

        if m['bill_rate'] < 0 or m[source_col_key] < 0:
            QMessageBox.warning(self, "Mapping Error", f"Please ensure 'Bill Rate' and '{source_label}' columns are mapped first.")
            return

        # Determine source color for visual consistency (same color as source columns)
        # We can fetch this from PBOQTable defaults
        dummy_table = PBOQTable()
        source_color = dummy_table.get_role_color(source_col_key) or const.COLOR_LINK_CYAN

        # Determine source markup for Subcontractor
        db_markup_map = {}
        if price_type == "Subcontractor Rate":
             db_path = self.pboq_file_selector.itemData(self.pboq_file_selector.currentIndex())
             try:
                import sqlite3
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT rowid, SubbeeMarkup FROM pboq_items WHERE SubbeeMarkup IS NOT NULL AND SubbeeMarkup != ''")
                for rid, m_str in cursor.fetchall():
                    try:
                        db_markup_map[rid] = float(m_str)
                    except: pass
                conn.close()
             except: pass

        db_path = self.pboq_file_selector.itemData(self.pboq_file_selector.currentIndex())
        link_updates = []
        amt_updates = []
        
        for i in range(self.tabs.count()):
            table = self.tabs.widget(i)
            if not isinstance(table, PBOQTable): continue
            
            for r in range(table.rowCount()):
                row_id_item = table.item(r, 0)
                if not row_id_item: continue
                row_id = row_id_item.data(Qt.ItemDataRole.UserRole)
                
                source_item = table.item(r, m[source_col_key])
                if not source_item or not source_item.text().strip(): continue
                
                val_str = source_item.text().strip()
                
                # Update Bill Rate UI
                bill_rate_item = table.item(r, m['bill_rate'])
                if not bill_rate_item:
                    bill_rate_item = QTableWidgetItem()
                    table.setItem(r, m['bill_rate'], bill_rate_item)
                
                bill_rate_item.setText(val_str)
                # Apply source color for visual consistency
                bill_rate_item.setBackground(source_color)
                bill_rate_item.setForeground(const.COLOR_GRAY_TEXT)
                
                link_updates.append((row_id, val_str))
                
                # Also update Bill Amount if Quantity exists
                if m['qty'] >= 0 and m['bill_amount'] >= 0:
                    qty_item = table.item(r, m['qty'])
                    if qty_item and qty_item.text().strip():
                        try:
                            # Parse Qty and Rate (handle commas)
                            q_val = float(qty_item.text().replace(',', ''))
                            r_val = float(val_str.replace(',', ''))
                            
                            # Apply markup if subcontractor
                            if price_type == "Subcontractor Rate":
                                # Use DB-stored markup (from Packages window), default to 0.0
                                effective_markup = db_markup_map.get(row_id, 0.0)
                                
                                if effective_markup != 0:
                                    r_val = r_val * (1 + (effective_markup / 100.0))
                                
                                # Update Bill Rate UI with marked up rate
                                marked_up_str = "{:,.2f}".format(r_val)
                                bill_rate_item.setText(marked_up_str)
                                
                                # Overwrite the link_updates tuple with marked up rate
                                link_updates.pop() # Remove original raw rate
                                link_updates.append((row_id, marked_up_str))
                                
                            a_val = q_val * r_val
                            a_str = "{:,.2f}".format(a_val)
                            
                            amt_item = table.item(r, m['bill_amount'])
                            if not amt_item:
                                amt_item = QTableWidgetItem()
                                table.setItem(r, m['bill_amount'], amt_item)
                            
                            amt_item.setText(a_str)
                            amt_item.setForeground(const.COLOR_GRAY_TEXT)
                            amt_updates.append((row_id, a_str))
                        except ValueError: pass

        if link_updates:
            self._persist_updates(m['bill_rate'], link_updates)
            
            # Persist formatting (Source Color BG + Gray Text)
            fmt_updates = []
            for rid, _ in link_updates:
                item0 = self.rowid_to_item0.get(rid)
                if not item0: continue
                g_idx = item0.data(Qt.ItemDataRole.UserRole + 1)
                fmt_updates.append((g_idx, {'bg_color': source_color.name(), 'font_color': const.COLOR_GRAY_TEXT.name()}))
            self.logic.persist_batch_cell_formatting(db_path, m['bill_rate'], fmt_updates)
            
            if amt_updates:
                self._persist_updates(m['bill_amount'], amt_updates)
                # Persist gray color for amounts
                fmt_amt_updates = []
                for rid, _ in amt_updates:
                    item0 = self.rowid_to_item0.get(rid)
                    if not item0: continue
                    g_idx = item0.data(Qt.ItemDataRole.UserRole + 1)
                    fmt_amt_updates.append((g_idx, {'font_color': const.COLOR_GRAY_TEXT.name()}))
                self.logic.persist_batch_cell_formatting(db_path, m['bill_amount'], fmt_amt_updates)

            QMessageBox.information(self, "Linked", f"Successfully linked {len(link_updates)} Bill Rate cells to {source_label}s.\nBill Amounts have been updated where quantities were available.")
            self._update_column_headers()
            self._update_stats()
        else:
            QMessageBox.information(self, "No Links", f"No items with {source_label}s were found to link in the current view.")

    def closeEvent(self, event):
        # Ensure the tools dock is hidden when the window is closed
        try:
            if hasattr(self, 'tools_dock') and self.tools_dock:
                self.tools_dock.hide()
        except RuntimeError:
            pass
            
        super().closeEvent(event)

    def _cleanup_tools_dock(self):
        """Cleanup dock widget when the dialog is actually destroyed."""
        if self.main_window:
            try:
                if hasattr(self, 'tools_dock') and self.tools_dock:
                    self.main_window.removeDockWidget(self.tools_dock)
                    self.tools_dock.deleteLater()
            except RuntimeError:
                pass

    # --- Subcontractor Adjudicator Handlers ---
    def _assign_package_to_selected(self, package_name):
        if not package_name:
            QMessageBox.warning(self, "Invalid Input", "Please enter a valid package name.")
            return
            
        m = self.tools_pane.get_mappings()
        pkg_col = m.get('sub_package', -1)
        desc_col = m.get('desc', -1)
        qty_col = m.get('qty', -1)
        unit_col = m.get('unit', -1)
        
        if pkg_col < 0:
            QMessageBox.warning(self, "Mapping Error", "Please map the 'Subbee Package' column in the tools pane first.")
            return

        # Check for other required mappings
        if desc_col < 0 or qty_col < 0 or unit_col < 0:
             QMessageBox.warning(self, "Mapping Error", "Description, Quantity, and Unit columns must be mapped to assign packages.")
             return

        table = self.tabs.currentWidget()
        if not isinstance(table, PBOQTable): return
        
        selected_indexes = table.selectedIndexes()
        if not selected_indexes:
            QMessageBox.warning(self, "No Selection", "Please highlight the rows in the table where you want to assign this package.")
            return

        # Get unique rows from selection
        selected_rows = set(idx.row() for idx in selected_indexes)
        updates = []
        
        for r in selected_rows:
            # Validate presence of standard info
            desc = table.item(r, desc_col).text().strip() if table.item(r, desc_col) else ""
            qty = table.item(r, qty_col).text().strip() if table.item(r, qty_col) else ""
            unit = table.item(r, unit_col).text().strip() if table.item(r, unit_col) else ""
            
            if not desc or not qty or not unit:
                continue

            row_id_item = table.item(r, 0)
            if not row_id_item: continue
            row_id = row_id_item.data(Qt.ItemDataRole.UserRole)
            
            pkg_item = table.item(r, pkg_col)
            if not pkg_item:
                pkg_item = QTableWidgetItem()
                table.setItem(r, pkg_col, pkg_item)
            
            pkg_item.setText(package_name)
            updates.append((row_id, package_name))
            
        if updates:
            self._persist_updates(pkg_col, updates)
            self._update_column_headers()
            self._update_stats()



    def _open_package_adjudicator(self):
        file_path = self.pboq_file_selector.currentData()
        if not file_path: return
        
        m = self.tools_pane.get_mappings()
        pkg_display_col = m.get('sub_package', -1)
        if pkg_display_col < 0:
            QMessageBox.warning(self, "Mapping Error", "Please map the 'Subbee Package' column first.")
            return
        pkg_db_col = self.db_columns[pkg_display_col + 1]
        
        dialog = PackageAdjudicatorDialog(file_path, pkg_db_col, self.project_dir, self)
        dialog.exec()

    def get_package_items(self, pkg):
        """Called by PackageAdjudicatorDialog to get BOQ items for a specific package."""
        m = self.tools_pane.get_mappings()
        pkg_col = m.get('sub_package', -1)
        ref_col = m.get('ref', -1)
        desc_col = m.get('desc', -1)
        qty_col = m.get('qty', -1)
        unit_col = m.get('unit', -1)
        
        items = []
        if pkg_col < 0: return items
        
        for i in range(self.tabs.count()):
            table = self.tabs.widget(i)
            if not isinstance(table, PBOQTable): continue
            
            for r in range(table.rowCount()):
                pkg_item = table.item(r, pkg_col)
                if pkg_item and pkg_item.text().strip() == pkg:
                    row_id = table.item(r, 0).data(Qt.ItemDataRole.UserRole)
                    ref = table.item(r, ref_col).text().strip() if ref_col >= 0 and table.item(r, ref_col) else ""
                    desc = table.item(r, desc_col).text().strip() if desc_col >= 0 and table.item(r, desc_col) else ""
                    qty = table.item(r, qty_col).text().strip() if qty_col >= 0 and table.item(r, qty_col) else ""
                    unit = table.item(r, unit_col).text().strip() if unit_col >= 0 and table.item(r, unit_col) else ""
                    rate = table.item(r, m['bill_rate']).text().strip() if m['bill_rate'] >= 0 and table.item(r, m['bill_rate']) else ""
                    
                    items.append({
                        'rowid': row_id,
                        'ref': ref,
                        'desc': desc,
                        'qty': qty,
                        'unit': unit,
                        'bill_rate': rate
                    })
        return items

    def get_full_pboq_for_export(self, target_pkg):
        """
        Extracts the entire PBOQ structure for 'Filtered Full BOQ' Excel export.
        Returns a list of dicts for ALL rows. Each dict includes 'is_target_pkg'.
        """
        m = self.tools_pane.get_mappings()
        pkg_col = m.get('sub_package', -1)
        ref_col = m.get('ref', -1)
        desc_col = m.get('desc', -1)
        qty_col = m.get('qty', -1)
        unit_col = m.get('unit', -1)
        
        items = []
        if pkg_col < 0: return items
        
        for i in range(self.tabs.count()):
            table = self.tabs.widget(i)
            if not isinstance(table, PBOQTable): continue
            
            for r in range(table.rowCount()):
                pkg_item = table.item(r, pkg_col)
                current_pkg = pkg_item.text().strip() if pkg_item else ""
                
                row_id = table.item(r, 0).data(Qt.ItemDataRole.UserRole)
                ref = table.item(r, ref_col).text().strip() if ref_col >= 0 and table.item(r, ref_col) else ""
                desc = table.item(r, desc_col).text().strip() if desc_col >= 0 and table.item(r, desc_col) else ""
                qty = table.item(r, qty_col).text().strip() if qty_col >= 0 and table.item(r, qty_col) else ""
                unit = table.item(r, unit_col).text().strip() if unit_col >= 0 and table.item(r, unit_col) else ""
                rate = table.item(r, m['bill_rate']).text().strip() if m['bill_rate'] >= 0 and table.item(r, m['bill_rate']) else ""
                
                is_target = (current_pkg == target_pkg)
                
                items.append({
                    'rowid': row_id,
                    'ref': ref,
                    'desc': desc,
                    'qty': qty,
                    'unit': unit,
                    'bill_rate': rate,
                    'is_target_pkg': is_target
                })
        return items

    def apply_winning_subcontractor(self, pkg, winner_name, winning_rates):
        """Called by PackageAdjudicatorDialog to apply chosen rates and generate SR- codes."""
        m = self.tools_pane.get_mappings()
        file_path = self.pboq_file_selector.currentData()
        
        roles = ['sub_package', 'sub_name', 'sub_rate', 'sub_markup', 'sub_category', 'sub_code']
        cols = {role: m.get(role, -1) for role in roles}
        
        if cols['sub_package'] < 0 or cols['sub_name'] < 0 or cols['sub_rate'] < 0:
            QMessageBox.warning(self, "Mapping Required", "Please map Subbee Package, Name, and Rate columns first.")
            return

        # 1. Fetch Package Meta-Data
        pkg_settings = PBOQLogic.get_package_settings(file_path).get(pkg, {})
        category = pkg_settings.get('category', 'Miscellaneous')
        markup = pkg_settings.get('markup', 0.0)

        # 2. Resolve Prefix for the category (Strict: All Caps, Alphanumeric only)
        import re
        db_path = "construction_costs.db"
        project_db_dir = os.path.join(self.project_dir, "Project Database")
        if os.path.exists(project_db_dir):
            for f in os.listdir(project_db_dir):
                if f.lower().endswith('.db'):
                    db_path = os.path.join(project_db_dir, f)
                    break
        db_mgr = DatabaseManager(db_path)
        prefixes = db_mgr.get_category_prefixes_dict()
        raw_prefix = prefixes.get(category, "MISC")
        # Ensure prefix is clean (Alpha-only) and Upper Case
        clean_prefix = re.sub(r'[^A-Z]', '', raw_prefix.upper())
        sr_prefix = f"SR-{clean_prefix}"

        # 3. Code Generation Logic
        existing_codes = []
        try:
            conn = sqlite3.connect(file_path)
            cursor = conn.cursor()
            cursor.execute("SELECT SubbeeCode FROM pboq_items WHERE SubbeeCode LIKE ?", (f"{sr_prefix}%",))
            existing_codes = [r[0] for r in cursor.fetchall() if r[0]]
            conn.close()
        except: pass
        
        def _get_next_code(p, codes, current_idx):
            """Returns the Nth code in a sequence starting from the last known code in the DB."""
            import re
            pattern = re.compile(rf"^{re.escape(p)}(\d+)([A-Z])$")
            max_num = 1
            max_letter = '@' # Before 'A'
            
            if codes:
                for c in codes:
                    match = pattern.match(str(c))
                    if match:
                        num = int(match.group(1))
                        let = match.group(2)
                        if num > max_num:
                            max_num = num
                            max_letter = let
                        elif num == max_num:
                            if let > max_letter:
                                max_letter = let

            # If no valid codes exist, start at 1A
            if max_letter == '@':
                num, let = 1, 'A'
            else:
                # Increment from found max
                if max_letter == 'Z':
                    num, let = max_num + 1, 'A'
                else:
                    num, let = max_num, chr(ord(max_letter) + 1)
            
            # Now calculate the Nth jump based on current_idx (relative to start of package apply)
            # We jump 'idx' steps from (num, let)
            for _ in range(current_idx):
                if let == 'Z':
                    num += 1
                    let = 'A'
                else:
                    let = chr(ord(let) + 1)
            
            return f"{p}{num}{let}"

        # 4. Apply Updates
        rate_dict = dict(winning_rates) # rowid -> rate
        db_updates = []
        
        # Format markup string
        markup_str = "{:,.2f}%".format(markup) if markup else ""

        current_item_index = 0
        for i in range(self.tabs.count()):
            table = self.tabs.widget(i)
            if not isinstance(table, PBOQTable): continue
            
            for r in range(table.rowCount()):
                pkg_item = table.item(r, cols['sub_package'])
                if pkg_item and pkg_item.text().strip() == pkg:
                    row_id = table.item(r, 0).data(Qt.ItemDataRole.UserRole)
                    if row_id in rate_dict:
                        raw_rate = rate_dict[row_id]
                        try:
                            f_rate = float(str(raw_rate).replace(',', ''))
                            rate_str = "{:,.2f}".format(f_rate)
                        except:
                            rate_str = str(raw_rate)
                        
                        # Generate unique SR code using jumping logic
                        sub_code = _get_next_code(sr_prefix, existing_codes, current_item_index)
                        
                        # Update UI
                        update_roles = [
                            (winner_name, cols['sub_name']),
                            (rate_str, cols['sub_rate']),
                            (markup_str, cols['sub_markup']),
                            (category, cols['sub_category']),
                            (sub_code, cols['sub_code'])
                        ]
                        for text, col_idx in update_roles:
                            if col_idx >= 0:
                                itm = table.item(r, col_idx)
                                if not itm:
                                    itm = QTableWidgetItem()
                                    table.setItem(r, col_idx, itm)
                                itm.setText(text)

                        db_updates.append((winner_name, rate_str, markup_str, category, sub_code, row_id))
                        current_item_index += 1

        # 5. Persist to Database
        if db_updates:
            try:
                conn = sqlite3.connect(file_path)
                cursor = conn.cursor()
                cursor.executemany("""
                    UPDATE pboq_items 
                    SET SubbeeName = ?, SubbeeRate = ?, SubbeeMarkup = ?, 
                        SubbeeCategory = ?, SubbeeCode = ?
                    WHERE rowid = ?
                """, db_updates)
                conn.commit()
                conn.close()
                self._update_stats()
                QMessageBox.information(self, "Applied", f"Applied winning quotes from {winner_name} for package '{pkg}'.\nGenerated {len(db_updates)} SR- codes.")
            except Exception as e:
                QMessageBox.critical(self, "DB Error", f"Failed to persist awards: {e}")

    def _open_packages_summary(self):
        """Open a project-wide summary of subcontractor packages and markups."""
        m = self.tools_pane.get_mappings()
        pkg_display_col = m.get('sub_package', -1)
        markup_display_col = m.get('sub_markup', -1)
        
        if pkg_display_col < 0:
            QMessageBox.warning(self, "Mapping Required", "Please map 'Subbee Package' column first.")
            return

        file_path = self.pboq_file_selector.currentData()
        if not file_path: return
             
        # Resolve actual DB column names
        pkg_db_col = self.db_columns[pkg_display_col + 1]
        
        if markup_display_col >= 0:
            markup_db_col = self.db_columns[markup_display_col + 1]
        else:
            markup_db_col = "SubbeeMarkup"

        # Resolve Project Categories for the summary dialog
        db_path = "construction_costs.db"
        project_db_dir = os.path.join(self.project_dir, "Project Database")
        if os.path.exists(project_db_dir):
            for f in os.listdir(project_db_dir):
                if f.lower().endswith('.db'):
                    db_path = os.path.join(project_db_dir, f)
                    break
        db_mgr = DatabaseManager(db_path)
        categories_dict = db_mgr.get_category_prefixes_dict()

        dialog = PackageSummaryDialog(file_path, self.project_dir, pkg_db_col, markup_db_col, categories_dict, self)
        dialog.dataChanged.connect(lambda: self._load_pboq_db(self.pboq_file_selector.currentIndex()))
        dialog.exec()
