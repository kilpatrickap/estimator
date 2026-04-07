import os
import sqlite3
import json
import re
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QMessageBox, QComboBox, QTabWidget, QWidget,
                             QDockWidget, QApplication, QProgressDialog, QTableWidgetItem, QMenu,
                             QLineEdit, QPushButton, QInputDialog)
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
        
        # PC Selection Mode State
        self._pc_selection_mode = False
        self._pc_selection_data = {} # target_rowid, target_row, field_type, etc.
        
        # Synchronization Flags
        self._is_syncing_codes = False
        
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
        self.price_pane.clearProvRequested.connect(self._clear_prov_and_code)
        self.price_pane.linkBillProvRequested.connect(self._run_link_bill_to_rate_logic) # Reusing generic logic
        self.price_pane.clearPCRequested.connect(self._clear_pc_and_code)
        self.price_pane.linkBillPCRequested.connect(self._run_link_bill_to_rate_logic) # Reusing generic logic
        self.price_pane.clearDayworkRequested.connect(self._clear_daywork_and_code)
        self.price_pane.linkBillDayworkRequested.connect(self._run_link_bill_to_rate_logic) # Reusing generic logic
        self.price_pane.openAdjudicatorRequested.connect(self._open_package_adjudicator)
        self.price_pane.clearSubcontractorRequested.connect(self._clear_sub_and_code)
        self.price_pane.assignPackageRequested.connect(self._assign_package_to_selected)
        self.price_pane.managePackagesRequested.connect(self._open_packages_summary)
        self.price_pane.openDirectoryRequested.connect(self._open_subcontractor_directory)
        self.price_pane.updatePCCalcRequested.connect(self._run_update_pc_calculations)
        self.price_pane.updateDayworkCalcRequested.connect(self._run_update_daywork_calculations)

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
        
        # We fetch physical columns PLUS logical subbee columns for fallback/sync
        logical_cols = [
            "SubbeePackage", "SubbeeName", "SubbeeRate", "SubbeeMarkup", "SubbeeCategory", "SubbeeCode",
            "ProvSum", "ProvSumCode", "ProvSumFormula", "ProvSumCategory", "ProvSumCurrency", "ProvSumExchangeRates",
            "PCSum", "PCSumCode", "PCSumFormula", "PCSumCategory", "PCSumCurrency", "PCSumExchangeRates",
            "PlugRate", "PlugCode", "PlugFormula", "PlugCategory", "PlugCurrency", "PlugExchangeRates"
        ]
        query = f"SELECT rowid, {', '.join(quoted_cols)}, {', '.join(logical_cols)} FROM pboq_items"
        cursor.execute(query)
        rows = cursor.fetchall()
        conn.close()
        
        self.rowid_to_item0 = {}
        sheet_groups = {}
        # logical_start_idx is row[0] (rowid) + physical_cols (len(db_columns))
        logical_start_idx = 1 + len(self.db_columns)
        
        for g_idx, row in enumerate(rows):
            row_id = row[0]
            physical_data = list(row[1:logical_start_idx])
            logical_data = row[logical_start_idx:]
            
            # --- Logic Layer MERGE ---
            # For subbee roles, prefer logical store values.
            # Category and Code ALWAYS use logical store (they are the source of truth).
            # Other roles only pull from logical store when the physical cell is empty.
            m = self.tools_pane.get_mappings()
            sub_roles = {
                'sub_package': 0, 'sub_name': 1, 'sub_rate': 2, 
                'sub_markup': 3, 'sub_category': 4, 'sub_code': 5,
                'prov_sum': 6, 'prov_sum_code': 7,
                'pc_sum': 12, 'pc_sum_code': 13,
                'plug_rate': 18, 'plug_code': 19
            }
            # Roles where the logical store is always authoritative
            logical_authoritative = {'sub_category', 'sub_code', 'prov_sum_code', 'pc_sum_code', 'plug_code', 'plug_rate', 'prov_sum', 'pc_sum'}
            for role, l_idx in sub_roles.items():
                p_idx = m.get(role, -1)
                if p_idx >= 0 and p_idx < len(physical_data) - 1:
                    logical_val = logical_data[l_idx]
                    if role in logical_authoritative:
                        # Always prefer the logical store for category/code
                        if logical_val is not None and str(logical_val) != "None":
                            physical_data[p_idx + 1] = logical_val
                    else:
                        # Fallback: only use logical if physical is empty
                        if not physical_data[p_idx + 1] or physical_data[p_idx + 1] == "None":
                            physical_data[p_idx + 1] = logical_val

            sheet_name = str(physical_data[0]) if physical_data[0] else "Sheet 1"
            if sheet_name not in sheet_groups: sheet_groups[sheet_name] = []
            sheet_groups[sheet_name].append((g_idx, row_id, physical_data[1:]))
            
        self.tools_pane.populate_column_combos(display_col_names)
        
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
                table.cellClicked.connect(self._on_table_cell_clicked)
                
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
        """Displays context-sensitive actions for PBOQ table cells."""
        m = self.tools_pane.get_mappings()
        file_path = self.pboq_file_selector.currentData()
        if not file_path: return
        
        if col == m.get('bill_amount', -1):
            menu = QMenu(self)
            clear_act = menu.addAction("Clear")
            
            action = menu.exec(table.viewport().mapToGlobal(pos))
            if not action: return
            
            if action == clear_act:
                item = table.item(row, col)
                if item:
                    item.setText("")
                    # Reset Color
                    def_color = table.get_column_default_color(col)
                    item.setBackground(def_color if def_color else QBrush(Qt.BrushStyle.NoBrush))
                    item.setForeground(Qt.GlobalColor.black)
                    
                    self._persist_updates(col, [(rowid, "")])
                    
                    # Clear Persisted Formatting
                    item0 = self.rowid_to_item0.get(rowid)
                    if item0:
                        g_idx = item0.data(Qt.ItemDataRole.UserRole + 1)
                        self.logic.clear_cell_formatting(file_path, g_idx, col)
                    
                    self._update_stats()
        
        elif col in [m.get('rate', -1), m.get('rate_code', -1)]:
            # Gross Rate context menu (applied to Rate or Rate Code column)
            self._handle_rate_context_menu(table, pos, row, col, rowid, is_plug=False)
            
        elif col in [m.get('plug_rate', -1), m.get('plug_code', -1)]:
            # Plug Rate context menu (applied to Plug Rate or Plug Code column)
            self._handle_rate_context_menu(table, pos, row, col, rowid, is_plug=True)
            
        elif col in [m.get('prov_sum', -1), m.get('prov_sum_code', -1)]:
            # Prov Sum context menu
            self._handle_rate_context_menu(table, pos, row, col, rowid, is_plug=False, is_prov=True)

        elif col in [m.get('pc_sum', -1), m.get('pc_sum_code', -1)]:
            # PC Sum context menu
            self._handle_rate_context_menu(table, pos, row, col, rowid, is_plug=False, is_prov=False, is_pc=True)

        elif col in [m.get('daywork', -1), m.get('daywork_code', -1)]:
            # Daywork context menu
            self._handle_rate_context_menu(table, pos, row, col, rowid, is_plug=False, is_prov=False, is_pc=False, is_dw=True)

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

        elif col in [m.get('sub_category', -1), m.get('sub_code', -1)] and col >= 0:
            # Subbee Category/Code - allow recategorization and SR- code regeneration
            menu = QMenu(self)
            edit_act = menu.addAction("Change Category & Regenerate Code")
            action = menu.exec(table.viewport().mapToGlobal(pos))
            if action == edit_act:
                self._recategorize_item(table, row, rowid)

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

    def _handle_rate_context_menu(self, table, pos, row, col, rowid, is_plug=True, is_prov=False, is_pc=False, is_dw=False):
        """Standardized rate context menu based on the SOR Table design."""
        m = self.tools_pane.get_mappings()
        
        if is_pc:
            rate_role = 'pc_sum'
            code_role = 'pc_sum_code'
        elif is_dw:
            rate_role = 'daywork'
            code_role = 'daywork_code'
        elif is_prov:
            rate_role = 'prov_sum'
            code_role = 'prov_sum_code'
        else:
            rate_role = 'plug_rate' if is_plug else 'rate'
            code_role = 'plug_code' if is_plug else 'rate_code'
        
        rate_col = m.get(rate_role, -1)
        code_col = m.get(code_role, -1)
        
        item_rate = table.item(row, rate_col) if rate_col >= 0 else None
        item_code = table.item(row, code_col) if code_col >= 0 else None
        
        rate_code = item_code.text().strip() if item_code else ""
        
        menu = QMenu(self)
        
        # 1. Build/Edit Rate
        if is_pc:
            action_text = "Edit PC Sum" if rate_code else "Build PC Sum"
        elif is_prov:
            action_text = "Edit Prov Sum" if rate_code else "Build Prov Sum"
        else:
            action_text = "Edit Rate" if rate_code else "Build Rate"
        
        link_rate_act = None
        link_amt_act = None
        if is_plug:
            link_rate_act = menu.addAction("Link to Bill Rate")
            link_amt_act = menu.addAction("Link to Bill Amount")
        elif is_prov or is_pc:
            link_amt_act = menu.addAction("Link to Bill Amount")

        build_act = None
        if not is_dw:
            build_act = menu.addAction(action_text)
        
        # 2. Clear Rate
        clear_act = menu.addAction("Clear Rate")
        
        menu.addSeparator()
        
        insert_mat_act = None
        insert_lab_act = None
        insert_plt_act = None
        insert_profit_act = None
        insert_gen_att_act = None
        insert_spec_att_act = None
        
        if is_dw:
            insert_mat_act = menu.addAction("Insert Material Daywork")
            insert_lab_act = menu.addAction("Insert Labour Daywork")
            insert_plt_act = menu.addAction("Insert Plant Daywork")
        elif is_pc:
            insert_profit_act = menu.addAction("Insert Profit")
            insert_gen_att_act = menu.addAction("Insert General Attendance")
            insert_spec_att_act = menu.addAction("Insert Special Attendance")

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
        if not rate_code or is_dw: # Daywork doesn't have a library rate usually
            goto_act.setEnabled(False)
            
        action = menu.exec(table.viewport().mapToGlobal(pos))
        if not action: return
        
        if action == build_act:
            self._build_rate(table, row, rowid, is_plug, is_prov, is_pc, is_dw)
        elif link_rate_act and action == link_rate_act:
            self._link_item_to_bill(table, row, rowid, is_plug=is_plug, is_prov=is_prov, is_pc=is_pc, is_dw=is_dw, target_role='bill_rate')
        elif link_amt_act and action == link_amt_act:
            self._link_item_to_bill(table, row, rowid, is_plug=is_plug, is_prov=is_prov, is_pc=is_pc, is_dw=is_dw, target_role='bill_amount')
        elif is_pc and action == insert_profit_act:
            self._insert_attendance_value(table, row, col, rowid, 'profit')
        elif is_pc and action == insert_gen_att_act:
            self._insert_attendance_value(table, row, col, rowid, 'gen_attendance')
        elif is_pc and action == insert_spec_att_act:
            self._insert_attendance_value(table, row, col, rowid, 'spec_attendance')
        elif is_dw and action == insert_mat_act:
            self._insert_daywork_value(table, row, col, rowid, 'mat')
        elif is_dw and action == insert_lab_act:
            self._insert_daywork_value(table, row, col, rowid, 'lab')
        elif is_dw and action == insert_plt_act:
            self._insert_daywork_value(table, row, col, rowid, 'plt')
        elif action == clear_act:
            self._clear_rate_at_row(table, row, rowid, is_plug, is_prov, is_pc, is_dw)
        elif action == copy_act:
            self._copy_rate_info(table, row, is_plug, is_prov, is_pc, is_dw)
        elif action == paste_act:
            self._paste_rate_info(table, row, rowid, is_plug, is_prov, is_pc, is_dw)
        elif action == goto_act:
            if self.main_window and hasattr(self.main_window, 'show_rate_in_database'):
                self.main_window.show_rate_in_database(rate_code)

    def _insert_attendance_value(self, table, row, col, rowid, field_type):
        """Starts PC Selection Mode to link this value to a parent PC Sum."""
        self._pc_selection_mode = True
        self._pc_selection_data = {
            'target_rowid': rowid,
            'target_row': row,
            'target_col': col,
            'field_type': field_type,
            'table': table
        }
        QApplication.setOverrideCursor(Qt.CursorShape.CrossCursor)
        if self.main_window:
            # Use a dedicated label for the blue notification to avoid styling other status bar items
            if not hasattr(self, '_pc_notif_label'):
                self._pc_notif_label = QLabel()
                self._pc_notif_label.setStyleSheet("color: #0000FF; font-weight: bold; margin-left: 10px;")
            
            self._pc_notif_label.setText("SELECT PARENT PC SUM: Click on the parent PC Sum row in the table (or press ESC to cancel)...")
            self.main_window.statusBar().addWidget(self._pc_notif_label)
            self._pc_notif_label.show()
            self.main_window.statusBar().showMessage("") # Clear standard message area

    def _insert_daywork_value(self, table, row, col, rowid, field_type):
        """Starts Daywork Selection Mode to link this value to a parent row."""
        self._pc_selection_mode = True
        self._pc_selection_data = {
            'target_rowid': rowid,
            'target_row': row,
            'target_col': col,
            'field_type': field_type,
            'table': table
        }
        QApplication.setOverrideCursor(Qt.CursorShape.CrossCursor)
        if self.main_window:
            if not hasattr(self, '_pc_notif_label'):
                self._pc_notif_label = QLabel()
                self._pc_notif_label.setStyleSheet("color: #0000FF; font-weight: bold; margin-left: 10px;")
            self._pc_notif_label.setText("SELECT PARENT ROW: Click on the parent row in the table (or press ESC to cancel)...")
            self.main_window.statusBar().addWidget(self._pc_notif_label)
            self._pc_notif_label.show()
            self.main_window.statusBar().showMessage("")

    def _on_table_cell_clicked(self, row, col):
        """Handles the selection of a parent PC Sum or Daywork row while in selection mode."""
        if not self._pc_selection_mode:
            return
            
        # Exit mode
        self._pc_selection_mode = False
        QApplication.restoreOverrideCursor()
        if self.main_window:
            if hasattr(self, '_pc_notif_label'):
                self.main_window.statusBar().removeWidget(self._pc_notif_label)
            self.main_window.statusBar().showMessage("Ready")
            
        # Determine the code of the row that was just clicked
        table = self.tabs.currentWidget()
        if not isinstance(table, PBOQTable): return
        
        m = self.tools_pane.get_mappings()
        
        # Determine current mode
        field_type = self._pc_selection_data['field_type']
        is_dw_mode = field_type in ['mat', 'lab', 'plt']
        
        # Parent Code Column
        # For PC mode, parent must have a PC Code. 
        # For DW mode, parent can be any row with a code (RateCode, PlugCode, etc.)
        # If the parent row is a PC item, we still look at its pc_sum_code.
        parent_code = ""
        
        if is_dw_mode:
            # Look for ANY code in the parent row
            for code_key in ['rate_code', 'plug_code', 'pc_sum_code', 'prov_sum_code', 'daywork_code']:
                c_idx = m.get(code_key, -1)
                if c_idx >= 0:
                    it = table.item(row, c_idx)
                    if it and it.text().strip():
                        parent_code = it.text().strip()
                        break
        else:
            # Standard PC Selection Mode
            pc_code_col = m.get('pc_sum_code', -1)
            if pc_code_col >= 0:
                code_item = table.item(row, pc_code_col)
                parent_code = code_item.text().strip() if code_item else ""

        if not parent_code:
            QMessageBox.warning(self, "Linking Error", "The selected row has no code to link from.")
            return

        # Transformation logic
        if is_dw_mode:
            # Strip common prefixes from parent_code (e.g., PS-, PC-)
            clean_parent = parent_code
            for pfx in ["PS-", "PC-", "PR-", "SR-", "DW-"]:
                if clean_parent.upper().startswith(pfx):
                    clean_parent = clean_parent[len(pfx):].strip()
                    break
            
            # P&O-[Cat]-[ParentCode]
            prefix_map = {'mat': 'P&O-MAT-', 'lab': 'P&O-LAB-', 'plt': 'P&O-PLT-'}
            new_code = f"{prefix_map[field_type]}{clean_parent}"
            target_role = 'daywork'
            target_code_role = 'daywork_code'
            link_color = const.COLOR_DAYWORK
        else:
            # Standard PC Transformation: (PC-ELEC1A) -> (P-ELEC1A)
            if parent_code.upper().startswith("PC-"):
                suffix = parent_code[3:].strip()
            else:
                suffix = parent_code.strip()
            
            prefix_map = {'profit': 'P', 'gen_attendance': 'GA', 'spec_attendance': 'SA'}
            new_prefix = prefix_map.get(field_type, 'X')
            new_code = f"{new_prefix}-{suffix}"
            target_role = 'pc_sum'
            target_code_role = 'pc_sum_code'
            link_color = const.COLOR_PC_SUM
        
        # Apply to the original target row
        target_table = self._pc_selection_data['table']
        target_row = self._pc_selection_data['target_row']
        target_rowid = self._pc_selection_data['target_rowid']
        
        # 1. Update Value Column (the percentage)
        val = ""
        if is_dw_mode:
            tool = self.price_pane.dw_tool
            if field_type == 'mat': val = tool.mat_input.text()
            elif field_type == 'lab': val = tool.lab_input.text()
            elif field_type == 'plt': val = tool.plt_input.text()
        else:
            tool = self.price_pane.pc_sum_tool
            if field_type == 'profit': val = tool.profit_input.text()
            elif field_type == 'gen_attendance': val = tool.gen_attendance_input.text()
            elif field_type == 'spec_attendance': val = tool.spec_attendance_input.text()
        
        val_col = m.get(target_role, -1)
        if val_col >= 0:
            item = target_table.item(target_row, val_col)
            if not item:
                item = QTableWidgetItem(val)
                target_table.setItem(target_row, val_col, item)
            else:
                item.setText(val)
            self._persist_updates(val_col, [(target_rowid, val)])

        # 2. Update Code Column
        cod_col = m.get(target_code_role, -1)
        if cod_col >= 0:
            item = target_table.item(target_row, cod_col)
            if not item:
                item = QTableWidgetItem(new_code)
                target_table.setItem(target_row, cod_col, item)
            else:
                item.setText(new_code)
            self._persist_updates(cod_col, [(target_rowid, new_code)])

        # 3. Calculate and Update Bill Amount
        # For Daywork, the parent value is the Bill Amount or Extension of the parent.
        # But wait, PC Sum logic uses the PC Sum column of the parent.
        # USER said "Just like the PC Sum". PC Sum parent holds the "Cost" in its pc_sum column.
        # So we look for the parent's value in its respective column.
        
        parent_val = 0.0
        # For PC, look in 'pc_sum'. For DW, look in 'bill_amount'?
        # Actually, if DW is just like PC, maybe there's a parent DW item? 
        # No, user said link to ANY row. So its Bill Amount is likely the cost.
        if is_dw_mode:
            amt_col = m.get('bill_amount', -1)
            if amt_col >= 0:
                p_item = table.item(row, amt_col)
                if p_item:
                    try: parent_val = float(p_item.text().replace(',', ''))
                    except: pass
        else:
            # PC Mode
            p_pc_col = m.get('pc_sum', -1)
            if p_pc_col >= 0:
                p_item = table.item(row, p_pc_col)
                if p_item:
                    try: parent_val = float(p_item.text().replace(',', ''))
                    except: pass
        
        # Convert tool percentage text (e.g. "1.00%") to float
        try:
            pct_val = float(val.replace('%', '').strip()) / 100.0
        except:
            pct_val = 0.0
            
        calculated_amount = parent_val * pct_val
        amount_str = "{:,.2f}".format(calculated_amount)
        
        bill_amt_col = m.get('bill_amount', -1)
        if bill_amt_col >= 0:
            amt_item = target_table.item(target_row, bill_amt_col)
            if not amt_item:
                amt_item = QTableWidgetItem(amount_str)
                target_table.setItem(target_row, bill_amt_col, amt_item)
            else:
                amt_item.setText(amount_str)
            
            amt_item.setBackground(QBrush(link_color))
            amt_item.setForeground(QBrush(const.COLOR_GRAY_TEXT))

            # Persist
            self._persist_updates(bill_amt_col, [(target_rowid, amount_str)])
            
            # Persist Formatting
            item0 = self.rowid_to_item0.get(target_rowid)
            if item0:
                g_idx = item0.data(Qt.ItemDataRole.UserRole + 1)
                file_path = self.pboq_file_selector.currentData()
                fmt_updates = [(g_idx, {'bg_color': link_color.name(), 'font_color': const.COLOR_GRAY_TEXT.name()})]
                self.logic.persist_batch_cell_formatting(file_path, bill_amt_col, fmt_updates)

            self._recalculate_row_extension(target_table, target_row, target_rowid)
            
        self._update_stats()

    def _link_item_to_bill(self, table, row, rowid, is_plug=False, is_prov=False, is_pc=False, is_dw=False, target_role=None):
        """Copies the Plug Rate (to Bill Rate or Amount) or Prov/PC Sum (to Bill Amount) for a single row."""
        m = self.tools_pane.get_mappings()
        
        if is_prov:
            source_role = 'prov_sum'
            if not target_role: target_role = 'bill_amount'
        elif is_dw:
            source_role = 'daywork'
            if not target_role: target_role = 'bill_amount'
        elif is_pc:
            source_role = 'pc_sum'
            if not target_role: target_role = 'bill_amount'
            
            # Limit PC Sum linking only to Prime Cost Items (PC- prefix)
            code_col = m.get('pc_sum_code', -1)
            if code_col < 0:
                QMessageBox.warning(self, "Mapping Error", "PC Code column must be mapped to link PC Sum items.")
                return
                
            code_item = table.item(row, code_col)
            code_text = code_item.text().strip().upper() if code_item else ""
            if not code_text.startswith("PC-"):
                QMessageBox.warning(self, "Invalid Selection", "Only Prime Cost Items (with code prefix 'PC-') can be linked to Bill Amount.\n\nProfit (P-) and Attendances (GA-/SA-) are linked automatically during the 'Insert...' process.")
                return
        elif is_plug:
            source_role = 'plug_rate'
            # SMART DUALITY: If no quantity, link to Amount column (Lumpsum). Otherwise link to Rate.
            if not target_role:
                target_role = 'bill_rate'
                qty_item = table.item(row, m['qty']) if m['qty'] >= 0 else None
                if not qty_item or not qty_item.text().strip():
                    target_role = 'bill_amount'
                else:
                    try:
                        if float(qty_item.text().replace(',','')) == 0:
                            target_role = 'bill_amount'
                    except: pass
        else:
            source_role = 'rate'
            if not target_role: target_role = 'bill_rate'

        source_col = m.get(source_role, -1)
        target_col = m.get(target_role, -1)
        
        if source_col < 0 or target_col < 0:
            QMessageBox.warning(self, "Mapping Error", f"Ensure '{source_role.replace('_',' ')}' and '{target_role.replace('_',' ')}' are mapped.")
            return

        source_item = table.item(row, source_col)
        if not source_item or not source_item.text().strip():
            QMessageBox.warning(self, "Missing Rate", f"There is no {source_role.replace('_',' ')} to link.")
            return

        rate_str = source_item.text().strip()
        
        # Consistent Rounding: Ensure the linked rates match the 2-decimal standard
        try:
            r_val = float(rate_str.replace(',', ''))
            rate_str = "{:,.2f}".format(r_val)
        except: pass

        # Apply to UI
        target_item = table.item(row, target_col)
        if not target_item:
            target_item = QTableWidgetItem()
            table.setItem(row, target_col, target_item)
        
        target_item.setText(rate_str)
        
        # Styling: Get source color (get_role_color handles this)
        color = table.get_role_color(source_role) or const.COLOR_LINK_CYAN
        if is_pc: color = const.COLOR_PC_SUM
        
        from PyQt6.QtGui import QBrush
        target_item.setBackground(QBrush(color))
        target_item.setForeground(QBrush(const.COLOR_GRAY_TEXT))
        
        # Persist Value
        db_path = self.pboq_file_selector.currentData()
        self._persist_updates(target_col, [(rowid, rate_str)])
        
        # Persist Formatting
        item0 = self.rowid_to_item0.get(rowid)
        if item0:
            g_idx = item0.data(Qt.ItemDataRole.UserRole + 1)
            fmt_updates = [(g_idx, {'bg_color': color.name(), 'font_color': const.COLOR_GRAY_TEXT.name()})]
            self.logic.persist_batch_cell_formatting(db_path, target_col, fmt_updates)

            # --- Recalculation logic ---
            # Now that we've updated the target cell and its color, trigger the recalc engine
            self._recalculate_row_extension(table, row, rowid)
            
        self._update_stats()

    def _copy_rate_info(self, table, row, is_plug, is_prov=False, is_pc=False, is_dw=False):
        m = self.tools_pane.get_mappings()
        if is_pc:
            rate_role, code_role = 'pc_sum', 'pc_sum_code'
        elif is_dw:
            rate_role, code_role = 'daywork', 'daywork_code'
        elif is_prov:
            rate_role, code_role = 'prov_sum', 'prov_sum_code'
        else:
            rate_role = 'plug_rate' if is_plug else 'rate'
            code_role = 'plug_code' if is_plug else 'rate_code'
        code_col = m.get(code_role, -1)
        rate_col = m.get(rate_role, -1)
        unit_col = m.get('unit', -1)
        
        if rate_col < 0 or code_col < 0: return
        
        self.clipboard_data = {
            'rate': table.item(row, rate_col).text() if table.item(row, rate_col) else "",
            'code': table.item(row, code_col).text() if table.item(row, code_col) else "",
            'unit': table.item(row, unit_col).text() if unit_col >= 0 and table.item(row, unit_col) else ""
        }
        if self.main_window:
            self.main_window.statusBar().showMessage(f"Rate {self.clipboard_data['code']} copied.", 2000)

    def _paste_rate_info(self, table, row, rowid, is_plug, is_prov=False, is_pc=False, is_dw=False):
        if not self.clipboard_data: return
        m = self.tools_pane.get_mappings()
        unit_col = m.get('unit', -1)
        target_unit = table.item(row, unit_col).text().strip() if unit_col >= 0 and table.item(row, unit_col) else ""
        
        if self.clipboard_data['unit'].strip().lower() != target_unit.lower():
            QMessageBox.warning(self, "Unit Mismatch", 
                              f"Cannot paste. Units do not match!\nSource: {self.clipboard_data['unit']} vs Target: {target_unit}")
            return
            
        if is_pc:
            rate_role, code_role = 'pc_sum', 'pc_sum_code'
        elif is_dw:
            rate_role, code_role = 'daywork', 'daywork_code'
        elif is_prov:
            rate_role, code_role = 'prov_sum', 'prov_sum_code'
        else:
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

    def _clear_rate_at_row(self, table, row, rowid, is_plug, is_prov=False, is_pc=False, is_dw=False):
        m = self.tools_pane.get_mappings()
        if is_pc:
            rate_role, code_role = 'pc_sum', 'pc_sum_code'
        elif is_dw:
            rate_role, code_role = 'daywork', 'daywork_code'
        elif is_prov:
            rate_role, code_role = 'prov_sum', 'prov_sum_code'
        else:
            rate_role = 'plug_rate' if is_plug else 'rate'
            code_role = 'plug_code' if is_plug else 'rate_code'
        
        rate_col = m.get(rate_role, -1)
        code_col = m.get(code_role, -1)
        
        for c in [rate_col, code_col]:
            if c >= 0:
                item = table.item(row, c)
                if item:
                    item.setText("")
                    self._persist_updates(c, [(rowid, "")])
        self._update_stats()

    def _build_rate(self, table, row, rowid, is_plug, is_prov=False, is_pc=False, is_dw=False):
        m = self.tools_pane.get_mappings()
        desc_col = m.get('desc', -1)
        unit_col = m.get('unit', -1)
        
        if is_pc:
            rate_role, code_role = 'pc_sum', 'pc_sum_code'
        elif is_prov:
            rate_role, code_role = 'prov_sum', 'prov_sum_code'
        elif is_plug:
            rate_role = 'plug_rate'
            code_role = 'plug_code'
        else:
            rate_role = 'rate'
            code_role = 'rate_code'
            
        code_col = m.get(code_role, -1)
        rate_col = m.get(rate_role, -1)
        
        desc = table.item(row, desc_col).text().strip() if desc_col >= 0 and table.item(row, desc_col) else "New Rate"
        unit = table.item(row, unit_col).text().strip() if unit_col >= 0 and table.item(row, unit_col) else "m"
        rate_code = table.item(row, code_col).text().strip() if code_col >= 0 and table.item(row, code_col) else ""
        file_path = self.pboq_file_selector.currentData()
        
        if is_plug or is_prov or is_pc:
            # Fetch existing data from DB
            formula_val = ""
            category_val = ""
            currency_val = ""
            plug_code_val = ""
            rate_val = 0.0
            ex_rates_json = "{}"
            
            prefix = "PCSum" if is_pc else ("ProvSum" if is_prov else "Plug")
            rate_col_name = "PCSum" if is_pc else ("ProvSum" if is_prov else "PlugRate")
            query = f"SELECT {prefix}Formula, {prefix}Category, {prefix}Currency, {prefix}ExchangeRates, {prefix}Code, {rate_col_name} FROM pboq_items WHERE rowid = ?"
            
            try:
                conn = sqlite3.connect(file_path)
                cursor = conn.cursor()
                cursor.execute(query, (rowid,))
                res = cursor.fetchone()
                if res:
                    formula_val = res[0] or ""
                    category_val = res[1] or ""
                    currency_val = res[2] or ""
                    ex_rates_json = res[3] or "{}"
                    plug_code_val = res[4] or ""
                    try: rate_val = float(str(res[5]).replace(',', '')) if res[5] else 0.0
                    except: rate_val = 0.0
                conn.close()
            except: pass
            
            if rate_val == 0.0 and rate_col >= 0:
                try: 
                    txt = table.item(row, rate_col).text().replace(',', '')
                    rate_val = float(txt) if txt else 0.0
                except: pass

            ex_rates = {}
            try: ex_rates = json.loads(ex_rates_json)
            except: pass
            
            item_data = {
                'name': desc,
                'unit': unit,
                'rate': rate_val,
                'formula': formula_val,
                'category': category_val,
                'currency': currency_val,
                'code': plug_code_val,
                'exchange_rates': ex_rates
            }
            
            # Open specialized Builder Dialog (PlugRateBuilderDialog handles Prov/PC/DW specifically)
            dialog = PlugRateBuilderDialog(item_data, self.project_dir, file_path, parent=self, is_prov=is_prov, is_pc=is_pc, is_dw=is_dw)
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
                    cursor.execute(f"""
                        UPDATE pboq_items 
                        SET {rate_col_name} = ?, {prefix}Formula = ?, {prefix}Code = ?, {prefix}Category = ?, {prefix}Currency = ?, {prefix}ExchangeRates = ?
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
            # Automate Link to Bill Rate to skip manual process
            self._link_item_to_bill(table, row, rowid)




    def _persist_updates(self, display_col, updates, trigger_recalc=True):
        if display_col < 0: return
        file_path = self.pboq_file_selector.currentData()
        self.logic.persist_batch_updates(file_path, self.db_columns, display_col, updates)
        
        # Code Synchronization: If a value column (Plug Rate, etc.) is updated, sync other rows with the same code.
        if not self._is_syncing_codes:
            self._is_syncing_codes = True
            try:
                self._sync_coded_updates(display_col, updates)
            finally:
                self._is_syncing_codes = False

        # Mirroring Logic: Sync physical edits to logical subbee columns
        m = self.tools_pane.get_mappings()
        mirror_map = {
            'sub_name': 'SubbeeName',
            'sub_package': 'SubbeePackage',
            'sub_category': 'SubbeeCategory',
            'sub_code': 'SubbeeCode',
            'sub_markup': 'SubbeeMarkup',
            'plug_rate': 'PlugRate',
            'plug_code': 'PlugCode',
            'prov_sum': 'ProvSum',
            'prov_sum_code': 'ProvSumCode',
            'pc_sum': 'PCSum',
            'pc_sum_code': 'PCSumCode'
        }
        for role, logical_col in mirror_map.items():
            if display_col == m.get(role):
                self.logic.persist_batch_named_updates(file_path, logical_col, updates)
                break

        # --- LIVE RECALCULATION ENGINE ---
        if trigger_recalc and not self.is_updating_logic:
            extension_updates = []
            # We must be careful not to create infinite recursion, so we only trigger this for non-recursive calls
            for rowid, new_val in updates:
                # Resolve the row in UI
                item0 = self.rowid_to_item0.get(rowid)
                if not item0: continue
                table = item0.tableWidget()
                row = item0.row()

                # Rule 1: If Qty or Bill Rate changes, recalculate Extension (if applicable)
                if display_col == m.get('qty') or display_col == m.get('bill_rate'):
                    ext_upd = self._recalculate_row_extension(table, row, rowid, batch_mode=True)
                    if ext_upd:
                        extension_updates.append(ext_upd)

                # Rule 2: If a Pricing Source changes, check for "Smart Links" (Propagation)
                # Gross Rate Edit
                elif display_col == m.get('rate') and m.get('bill_rate') >= 0:
                    bill_rate_item = table.item(row, m['bill_rate'])
                    # If Bill Rate is GREEN, propagate Gross Rate
                    if bill_rate_item and bill_rate_item.background().color().name().lower() == const.COL_COLOR_GREEN.name().lower():
                        bill_rate_item.setText(new_val)
                        self._persist_updates(m['bill_rate'], [(rowid, new_val)])

                # Plug Rate Edit
                elif display_col == m.get('plug_rate'):
                    # Plug can target Rate OR Amount
                    bill_rate_item = table.item(row, m.get('bill_rate', -1))
                    bill_amt_item = table.item(row, m.get('bill_amount', -1))
                    
                    p_color = const.COL_COLOR_PURPLE.name().lower()
                    if bill_rate_item and bill_rate_item.background().color().name().lower() == p_color:
                        bill_rate_item.setText(new_val)
                        self._persist_updates(m['bill_rate'], [(rowid, new_val)])
                    elif bill_amt_item and bill_amt_item.background().color().name().lower() == p_color:
                        bill_amt_item.setText(new_val)
                        self._persist_updates(m['bill_amount'], [(rowid, new_val)])

                # Subcontractor Rate Edit
                elif display_col == m.get('sub_rate') and m.get('bill_rate') >= 0:
                    bill_rate_item = table.item(row, m['bill_rate'])
                    # If Bill Rate is ORANGE, propagate Sub Rate
                    if bill_rate_item and bill_rate_item.background().color().name().lower() == const.COL_COLOR_ORANGE.name().lower():
                        bill_rate_item.setText(new_val)
                        self._persist_updates(m['bill_rate'], [(rowid, new_val)])

                # Prov Sum Edit
                elif display_col == m.get('prov_sum') and m.get('bill_amount') >= 0:
                    bill_amt_item = table.item(row, m['bill_amount'])
                    # If Bill Amt is LIGHT CYAN (Tangerine-like role), propagate Prov Sum
                    if bill_amt_item and bill_amt_item.background().color().name().lower() == const.COLOR_PROV_SUM.name().lower():
                        bill_amt_item.setText(new_val)
                        self._persist_updates(m['bill_amount'], [(rowid, new_val)])

            if extension_updates:
                self._persist_updates(m.get('bill_amount'), extension_updates, trigger_recalc=False)

        # Trigger Collection update IF we are currently in "Revert" mode (meaning it was clicked once)
        # AND we are not already in a logic update.
        if display_col == m['bill_amount'] and not self.is_updating_logic:
            if self.tools_pane.collect_btn.text() == "Revert":
                self._run_collect_logic(force_collect=True)
        
        # Stats update is fast enough to keep live
        self._update_stats()

    def _sync_coded_updates(self, display_col, updates):
        """Finds all other rows in the UI sharing the same code as the updated rows and updates their values."""
        m = self.tools_pane.get_mappings()
        
        # Map value columns to their respective source-of-truth code columns
        sync_map = {
            m.get('rate'): m.get('rate_code'),
            m.get('plug_rate'): m.get('plug_code'),
            m.get('prov_sum'): m.get('prov_sum_code'),
            m.get('pc_sum'): m.get('pc_sum_code'),
            m.get('sub_rate'): m.get('sub_code'),
            m.get('daywork'): m.get('daywork_code')
        }
        
        if display_col not in sync_map or sync_map[display_col] < 0:
            return
            
        code_col_idx = sync_map[display_col]
        
        # We collect all updates found to avoid N separate persist calls
        synced_updates = []
        
        for rowid, new_val in updates:
            # 1. Resolve code for THIS updated row
            item0 = self.rowid_to_item0.get(rowid)
            if not item0: continue
            table = item0.tableWidget()
            row = item0.row()
            
            code_item = table.item(row, code_col_idx)
            code_text = code_item.text().strip() if code_item else ""
            if not code_text: continue
            
            # 2. Iterate through ALL row items and find matches
            for other_rowid, other_item0 in self.rowid_to_item0.items():
                if other_rowid == rowid: continue
                
                other_table = other_item0.tableWidget()
                other_row = other_item0.row()
                
                other_code_item = other_table.item(other_row, code_col_idx)
                if other_code_item and other_code_item.text().strip() == code_text:
                    # Update UI directly
                    val_item = other_table.item(other_row, display_col)
                    if val_item and val_item.text() != new_val:
                        val_item.setText(new_val)
                        synced_updates.append((other_rowid, new_val))
                        
        # 3. Batch persist the synced results (recursion is prevented by the flag in _persist_updates)
        if synced_updates:
            self._persist_updates(display_col, synced_updates, trigger_recalc=True)

    def _recalculate_row_extension(self, table, row, rowid, batch_mode=False):
        """Intelligently recalculates Bill Amount based on item dynamics (Rate vs LumpSum)."""
        m = self.tools_pane.get_mappings()
        bill_rate_col = m.get('bill_rate', -1)
        bill_amount_col = m.get('bill_amount', -1)
        qty_col = m.get('qty', -1)

        if bill_amount_col < 0: return
        
        qty_item = table.item(row, qty_col) if qty_col >= 0 else None
        rate_item = table.item(row, bill_rate_col) if bill_rate_col >= 0 else None
        amt_item = table.item(row, bill_amount_col)
        
        if not amt_item: 
            amt_item = QTableWidgetItem()
            table.setItem(row, bill_amount_col, amt_item)

        # Check Price Type Logic (using colors as markers)
        bg_color = amt_item.background().color().name().lower()
        bill_rate_bg = rate_item.background().color().name().lower() if rate_item else ""
        
        # Lumpsum markers: Purple (if in Amount col) or Light Cyan (Prov Sum)
        is_lumpsum_plug = (bg_color in [const.COL_COLOR_PURPLE.name().lower(), const.COLOR_LINK_CYAN.name().lower()])
        is_prov_sum = (bg_color == const.COLOR_PROV_SUM.name().lower())
        
        # Rate-based markers: Purple (if in Rate col), Green (Gross), Orange (Subbee), Cyan (Linked) or Default (Yellow)
        is_rate_based = (bill_rate_bg in [const.COL_COLOR_PURPLE.name().lower(),
                                           const.COL_COLOR_GREEN.name().lower(),
                                           const.COL_COLOR_ORANGE.name().lower(),
                                           const.COLOR_LINK_CYAN.name().lower()])
        # Fallback: if it's default (Yellow/No Color), assume extension unless already marked as lump sum
        if not is_rate_based and not (is_lumpsum_plug or is_prov_sum):
            if bill_rate_bg == "" or bill_rate_bg == const.COL_COLOR_YELLOW.name().lower():
                is_rate_based = True

        if is_rate_based:
            # Multiplier Dynamics: Qty * Rate = Amount
            if qty_item and rate_item:
                try:
                    q_str = qty_item.text().replace(',', '').strip()
                    r_str = rate_item.text().replace(',', '').strip()
                    if not q_str or not r_str: return
                    
                    # Rounding values to standard construction precision (Qty:4, Rate:2)
                    # to match Excel's "Precision as Displayed" math.
                    q_val = round(float(q_str), 4)
                    r_val = round(float(r_str), 2)
                    amt_val = round(q_val * r_val, 2)
                    amt_str = "{:,.2f}".format(amt_val)
                    
                    changed = (amt_item.text() != amt_str)
                    if changed:
                        amt_item.setText(amt_str)
                        if batch_mode:
                            return (rowid, amt_str)
                        else:
                            # Avoid infinite recalc loops by passing trigger_recalc=False
                            self._persist_updates(bill_amount_col, [(rowid, amt_str)], trigger_recalc=False)
                except ValueError: pass
        else:
            # Lumpsum Dynamics: Amount is needed, ignore Quantity changes
            # (Logic handled by simply doing nothing here)
            pass
        return None



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
                    if hasattr(self, 'price_pane'):
                        p_type = self.price_pane.price_type_combo.currentText()
                        if p_type == "Plug Rate":
                            rate_col = m.get('plug_rate', -1)
                        elif p_type == "Prov Sum":
                            rate_col = m.get('prov_sum', -1)
                        elif p_type == "Subcontractor Rate":
                            rate_col = m.get('sub_rate', -1)
                            
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
            inactive_cols = [m.get('rate', -1), m.get('rate_code', -1), 
                             m.get('prov_sum', -1), m.get('prov_sum_code', -1),
                             m.get('pc_sum', -1), m.get('pc_sum_code', -1),
                             m.get('daywork', -1), m.get('daywork_code', -1),
                             m.get('sub_package', -1), m.get('sub_name', -1), m.get('sub_rate', -1), 
                             m.get('sub_markup', -1), m.get('sub_category', -1), m.get('sub_code', -1)]
        elif price_type == "Prov Sum":
            active_cols = [m.get('prov_sum', -1), m.get('prov_sum_code', -1)]
            inactive_cols = [m.get('rate', -1), m.get('rate_code', -1), 
                             m.get('plug_rate', -1), m.get('plug_code', -1),
                             m.get('pc_sum', -1), m.get('pc_sum_code', -1),
                             m.get('daywork', -1), m.get('daywork_code', -1),
                             m.get('sub_package', -1), m.get('sub_name', -1), m.get('sub_rate', -1), 
                             m.get('sub_markup', -1), m.get('sub_category', -1), m.get('sub_code', -1)]
        elif price_type == "PC Sum":
            active_cols = [m.get('pc_sum', -1), m.get('pc_sum_code', -1)]
            inactive_cols = [m.get('rate', -1), m.get('rate_code', -1), 
                             m.get('plug_rate', -1), m.get('plug_code', -1),
                             m.get('prov_sum', -1), m.get('prov_sum_code', -1),
                             m.get('daywork', -1), m.get('daywork_code', -1),
                             m.get('sub_package', -1), m.get('sub_name', -1), m.get('sub_rate', -1), 
                             m.get('sub_markup', -1), m.get('sub_category', -1), m.get('sub_code', -1)]
        elif price_type == "Subcontractor Rate":
            active_cols = [m.get('sub_package', -1), m.get('sub_name', -1), m.get('sub_rate', -1), 
                           m.get('sub_markup', -1), m.get('sub_category', -1), m.get('sub_code', -1)]
            inactive_cols = [m.get('rate', -1), m.get('rate_code', -1), m.get('plug_rate', -1), m.get('plug_code', -1),
                             m.get('prov_sum', -1), m.get('prov_sum_code', -1),
                             m.get('pc_sum', -1), m.get('pc_sum_code', -1),
                             m.get('daywork', -1), m.get('daywork_code', -1)]
        elif price_type == "Dayworks":
            active_cols = [m.get('daywork', -1), m.get('daywork_code', -1)]
            inactive_cols = [m.get('rate', -1), m.get('rate_code', -1), 
                             m.get('plug_rate', -1), m.get('plug_code', -1),
                             m.get('prov_sum', -1), m.get('prov_sum_code', -1),
                             m.get('pc_sum', -1), m.get('pc_sum_code', -1),
                             m.get('sub_package', -1), m.get('sub_name', -1), m.get('sub_rate', -1), 
                             m.get('sub_markup', -1), m.get('sub_category', -1), m.get('sub_code', -1)]
        else: # Gross Rate or others
            active_cols = [m.get('rate', -1), m.get('rate_code', -1)]
            inactive_cols = [m.get('plug_rate', -1), m.get('plug_code', -1), 
                             m.get('prov_sum', -1), m.get('prov_sum_code', -1),
                             m.get('pc_sum', -1), m.get('pc_sum_code', -1),
                             m.get('daywork', -1), m.get('daywork_code', -1),
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
            'prov_sum': "Prov Sum", 'prov_sum_code': "Prov Code",
            'pc_sum': "PC Sum", 'pc_sum_code': "PC Code",
            'daywork': "Daywork", 'daywork_code': "Daywork Code",
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
                
                # Automatically hide blank/extra columns beyond the standard pricing range (20 columns)
                # but only if they aren't mapped to anything.
                if i >= 20:
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
        """Backfills all hidden subbee logical columns from whatever physical columns are currently mapped."""
        m = self.tools_pane.get_mappings()
        sync_map = {
            'sub_name': 'SubbeeName',
            'sub_package': 'SubbeePackage',
            'sub_category': 'SubbeeCategory',
            'sub_code': 'SubbeeCode',
            'sub_markup': 'SubbeeMarkup',
            'plug_rate': 'PlugRate',
            'plug_code': 'PlugCode',
            'prov_sum': 'ProvSum',
            'prov_sum_code': 'ProvSumCode',
            'pc_sum': 'PCSum',
            'pc_sum_code': 'PCSumCode'
        }
        # Build {role: display_col_idx} for roles that are actually mapped
        active = {role: m.get(role, -1) for role in sync_map if m.get(role, -1) >= 0}
        if not active: return

        file_path = self.pboq_file_selector.currentData()
        updates = {role: [] for role in active}
        
        for i in range(self.tabs.count()):
            table = self.tabs.widget(i)
            if not isinstance(table, PBOQTable): continue
            for r in range(table.rowCount()):
                rowid = table.item(r, 0).data(Qt.ItemDataRole.UserRole)
                for role, col_idx in active.items():
                    item = table.item(r, col_idx)
                    val = item.text().strip() if item else ""
                    updates[role].append((rowid, val))
        
        for role, upd_list in updates.items():
            if upd_list:
                self.logic.persist_batch_named_updates(file_path, sync_map[role], upd_list)

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

    def _clear_prov_and_code(self):
        m = self.tools_pane.get_mappings()
        rate_col = m.get('prov_sum', -1)
        code_col = m.get('prov_sum_code', -1)
        self._clear_columns([rate_col, code_col], "Prov Sum & Code")

    def _clear_pc_and_code(self):
        m = self.tools_pane.get_mappings()
        rate_col = m.get('pc_sum', -1)
        code_col = m.get('pc_sum_code', -1)
        self._clear_columns([rate_col, code_col], "PC Sum & Code")

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
            # Automate Link to Bill Rate for the entire sheet to skip manual process
            self._run_link_bill_to_rate_logic()
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
        """Batch copies current Rate (Gross or Plug) or Prov Sum to Bill columns."""
        m = self.tools_pane.get_mappings()
        price_type = self.price_pane.price_type_combo.currentText()
        
        # We handle dynamic targeting for Plug Rate inside the loop
        static_target_role = None
        if price_type == "Prov Sum":
            static_target_role = 'bill_amount'
            source_col_key = 'prov_sum'
        elif price_type == "PC Sum":
            static_target_role = 'bill_amount'
            source_col_key = 'pc_sum'
        elif price_type == "Subcontractor Rate":
            static_target_role = 'bill_rate'
            source_col_key = 'sub_rate'
        elif price_type == "Plug Rate":
            source_col_key = 'plug_rate'
        else: # Gross Rate
            static_target_role = 'bill_rate'
            source_col_key = 'rate'

        if m[source_col_key] < 0:
            QMessageBox.warning(self, "Mapping Error", f"Please map the '{price_type}' source column first.")
            return

        db_path = self.pboq_file_selector.currentData()
        source_color = PBOQTable().get_role_color(source_col_key) or const.COLOR_LINK_CYAN

        # Fetch subbee markup map if needed
        db_markup_map = {}
        if price_type == "Subcontractor Rate":
             try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT rowid, SubbeeMarkup FROM pboq_items WHERE SubbeeMarkup IS NOT NULL AND SubbeeMarkup != ''")
                for rid, m_str in cursor.fetchall():
                    try:
                        clean_m = str(m_str).replace('%','').replace(',','').strip()
                        if clean_m: db_markup_map[rid] = float(clean_m)
                    except: pass
                conn.close()
             except: pass

        # We'll use two sets of updates since targets can vary by row for Plug Rate
        rate_updates, rate_fmt = [], []
        amt_updates, amt_fmt = [], []
        
        processed_count = 0

        for i in range(self.tabs.count()):
            table = self.tabs.widget(i)
            if not isinstance(table, PBOQTable): continue
            
            for r in range(table.rowCount()):
                row_id_item = table.item(r, 0)
                if not row_id_item: continue
                row_id = row_id_item.data(Qt.ItemDataRole.UserRole)
                
                source_item = table.item(r, m[source_col_key])
                if not source_item or not source_item.text().strip(): continue
                
                # If PC Sum, only link if it has the PC- prefix
                if price_type == "PC Sum":
                    code_col = m.get('pc_sum_code', -1)
                    if code_col < 0:
                        continue # Cannot verify without mapping
                    code_item = table.item(r, code_col)
                    code_text = code_item.text().strip().upper() if code_item else ""
                    if not code_text.startswith("PC-"):
                        continue
                
                # Determine Target Role for this row
                target_role = static_target_role
                if price_type == "Plug Rate":
                    qty_item = table.item(r, m['qty']) if m['qty'] >= 0 else None
                    if not qty_item or not qty_item.text().strip():
                        target_role = 'bill_amount'
                    else:
                        try:
                            if float(qty_item.text().replace(',','')) == 0:
                                target_role = 'bill_amount'
                            else:
                                target_role = 'bill_rate'
                        except: target_role = 'bill_rate'

                target_col = m.get(target_role, -1)
                if target_col < 0: continue

                val_str = source_item.text().strip()
                active_val_str = val_str

                try:
                    # Always treat linked rates as 2-decimal rounded figures to ensure 
                    # software math matches Excel physical math.
                    r_val = float(val_str.replace(',', ''))
                    
                    if price_type == "Subcontractor Rate":
                        effective_markup = db_markup_map.get(row_id, 0.0)
                        if effective_markup != 0:
                            r_val = r_val * (1 + (effective_markup / 100.0))
                    
                    active_val_str = "{:,.2f}".format(r_val)
                except: pass

                # Update UI
                item = table.item(r, target_col)
                if not item:
                    item = QTableWidgetItem()
                    table.setItem(r, target_col, item)
                item.setText(active_val_str)
                item.setBackground(source_color)
                item.setForeground(const.COLOR_GRAY_TEXT)
                
                # Buffer for Persistence
                fmt_info = (row_id_item.data(Qt.ItemDataRole.UserRole + 1), {'bg_color': source_color.name(), 'font_color': const.COLOR_GRAY_TEXT.name()})
                if target_role == 'bill_rate':
                    rate_updates.append((row_id, active_val_str))
                    rate_fmt.append(fmt_info)
                else:
                    amt_updates.append((row_id, active_val_str))
                    amt_fmt.append(fmt_info)
                
                # We skip inline recalculation here because _persist_updates handles it natively in batch mode.
                processed_count += 1

        # Persistence
        if rate_updates:
            self._persist_updates(m['bill_rate'], rate_updates)
            self.logic.persist_batch_cell_formatting(db_path, m['bill_rate'], rate_fmt)
        if amt_updates:
            self._persist_updates(m['bill_amount'], amt_updates)
            self.logic.persist_batch_cell_formatting(db_path, m['bill_amount'], amt_fmt)
        
        if processed_count > 0:
            QMessageBox.information(self, "Success", f"Linked {processed_count} items from {price_type} to Bill.")
        
        self._update_stats()
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



    # Note: Redundant _handle_context_menu removed (consolidated at top)

    def _apply_individual_subbee_quote(self, table, row, rowid, sub_name, rate, pkg_name):
        """Applies a specific subcontractor quote to a single row."""
        file_path = self.pboq_file_selector.currentData()
        m = self.tools_pane.get_mappings()
        
        mapping = {
            'sub_name': sub_name,
            'sub_rate': f"{rate:,.2f}",
        }
        
        # 1. Logical Persistence
        self.logic.persist_batch_named_updates(file_path, "SubbeeName", [(rowid, sub_name)])
        self.logic.persist_batch_named_updates(file_path, "SubbeeRate", [(rowid, str(rate))])
        
        # 2. UI and Physical Persistence
        for role, val in mapping.items():
            col_idx = m.get(role, -1)
            if col_idx >= 0:
                # UI
                item = table.item(row, col_idx)
                if not item:
                    item = QTableWidgetItem()
                    table.setItem(row, col_idx, item)
                item.setText(val)
                # Physical
                self.logic.persist_batch_updates(file_path, self.db_columns, col_idx, [(rowid, val)])
        
        self._update_stats()
        self.main_window.statusBar().showMessage(f"Assigned {sub_name} to item {rowid}", 3000)

    def _recategorize_item(self, table, row, rowid):
        """Prompts user for a new category and regenerates the SR- code for that item."""
        # 1. Resolve Project Categories - ALWAYS use the global database for software-wide categories
        db_mgr = DatabaseManager()
        cat_prefixes = db_mgr.get_category_prefixes_dict()
        categories = sorted(list(cat_prefixes.keys()))
        
        if not categories:
            QMessageBox.warning(self, "No Categories", "Could not find any project categories in construction_costs.db.")
            return

        # 2. Prompt for selection
        m = self.tools_pane.get_mappings()
        cur_cat_item = table.item(row, m.get('sub_category', -1))
        cur_cat = cur_cat_item.text() if cur_cat_item else ""
        
        new_cat, ok = QInputDialog.getItem(self, "Recategorize Item", "Select New Project Category:", 
                                         categories, categories.index(cur_cat) if cur_cat in categories else 0, False)
        
        if not ok or not new_cat: return

        # 3. Generate New Code Logic (Matches apply_winning_subcontractor)
        raw_prefix = cat_prefixes.get(new_cat, "MISC")
        clean_prefix = re.sub(r'[^A-Z]', '', raw_prefix.upper())
        sr_prefix = f"SR-{clean_prefix}"
        
        file_path = self.pboq_file_selector.currentData()
        existing_codes = []
        try:
            conn = sqlite3.connect(file_path)
            cursor = conn.cursor()
            cursor.execute("SELECT SubbeeCode FROM pboq_items WHERE SubbeeCode LIKE ?", (f"{sr_prefix}%",))
            existing_codes = [r[0] for r in cursor.fetchall() if r[0]]
            conn.close()
        except: pass

        import re
        pattern = re.compile(rf"^{re.escape(sr_prefix)}(\d+)([A-Z])$")
        max_num = 1
        max_letter = '@'
        if existing_codes:
            for c in existing_codes:
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

        if max_letter == '@': n, l = 1, 'A'
        elif max_letter == 'Z': n, l = max_num + 1, 'A'
        else: n, l = max_num, chr(ord(max_letter) + 1)
        
        new_code = f"{sr_prefix}{n}{l}"

        # 4. Update UI & Database
        cols = {
            'sub_category': m.get('sub_category', -1),
            'sub_code': m.get('sub_code', -1)
        }
        
        # Update Table UI
        if cols['sub_category'] >= 0:
            itm = table.item(row, cols['sub_category'])
            if not itm: itm = QTableWidgetItem(); table.setItem(row, cols['sub_category'], itm)
            itm.setText(new_cat)
        if cols['sub_code'] >= 0:
            itm = table.item(row, cols['sub_code'])
            if not itm: itm = QTableWidgetItem(); table.setItem(row, cols['sub_code'], itm)
            itm.setText(new_code)

        # Update Database (Both Logical and Physical)
        try:
            conn = sqlite3.connect(file_path)
            cursor = conn.cursor()
            # Logical
            cursor.execute("UPDATE pboq_items SET SubbeeCategory = ?, SubbeeCode = ? WHERE rowid = ?", (new_cat, new_code, rowid))
            # Physical
            if cols['sub_category'] >= 0:
                col_name = self.db_columns[cols['sub_category'] + 1]
                cursor.execute(f'UPDATE pboq_items SET "{col_name}" = ? WHERE rowid = ?', (new_cat, rowid))
            if cols['sub_code'] >= 0:
                col_name = self.db_columns[cols['sub_code'] + 1]
                cursor.execute(f'UPDATE pboq_items SET "{col_name}" = ? WHERE rowid = ?', (new_code, rowid))
            
            conn.commit()
            conn.close()
            QMessageBox.information(self, "Updated", f"Item recategorized to '{new_cat}'.\nNew Code: {new_code}")
        except Exception as e:
            QMessageBox.critical(self, "DB Error", f"Failed to persist recategorization: {e}")

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

    def _open_subcontractor_directory(self):
        """Opens the Subcontractor Directory directly from the Tool Pane."""
        file_path = self.pboq_file_selector.currentData()
        if not file_path: return
        
        from subcontractor_directory import SubcontractorDirectoryDialog
        dialog = SubcontractorDirectoryDialog(file_path, self.project_dir, self)
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
        # ALWAYS use the global database for software-wide categories
        db_mgr = DatabaseManager()
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

                        # Prepare DB Update List
                        # We build a list of (ColumnName, Value) pairs for THIS specific row
                        physical_updates = []
                        if cols['sub_name'] >= 0: physical_updates.append((self.db_columns[cols['sub_name'] + 1], winner_name))
                        if cols['sub_rate'] >= 0: physical_updates.append((self.db_columns[cols['sub_rate'] + 1], rate_str))
                        if cols['sub_markup'] >= 0: physical_updates.append((self.db_columns[cols['sub_markup'] + 1], markup_str))
                        if cols['sub_category'] >= 0: physical_updates.append((self.db_columns[cols['sub_category'] + 1], category))
                        if cols['sub_code'] >= 0: physical_updates.append((self.db_columns[cols['sub_code'] + 1], sub_code))

                        db_updates.append({
                            'rowid': row_id,
                            'logical': (winner_name, rate_str, markup_str, category, sub_code),
                            'physical': physical_updates
                        })
                        current_item_index += 1

        # 5. Persist to Database
        if db_updates:
            try:
                conn = sqlite3.connect(file_path)
                cursor = conn.cursor()
                for up in db_updates:
                    # Sync logical columns
                    cursor.execute("""
                        UPDATE pboq_items 
                        SET SubbeeName = ?, SubbeeRate = ?, SubbeeMarkup = ?, 
                            SubbeeCategory = ?, SubbeeCode = ?
                        WHERE rowid = ?
                    """, up['logical'] + (up['rowid'],))
                    
                    # Sync physical mapped columns
                    for col_name, val in up['physical']:
                        cursor.execute(f'UPDATE pboq_items SET "{col_name}" = ? WHERE rowid = ?', (val, up['rowid']))
                
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

        # Resolve Project Categories for the summary dialog - ALWAYS use global DB for categories
        db_mgr = DatabaseManager()
        categories_dict = db_mgr.get_category_prefixes_dict()

        dialog = PackageSummaryDialog(file_path, self.project_dir, pkg_db_col, markup_db_col, categories_dict, self)
        dialog.dataChanged.connect(lambda: self._load_pboq_db(self.pboq_file_selector.currentIndex()))
        dialog.exec()

    def keyPressEvent(self, event):
        """Allows ESC key to cancel specific modes like PC Selection."""
        if event.key() == Qt.Key.Key_Escape and self._pc_selection_mode:
            self._pc_selection_mode = False
            QApplication.restoreOverrideCursor()
            if self.main_window:
                if hasattr(self, '_pc_notif_label'):
                    self.main_window.statusBar().removeWidget(self._pc_notif_label)
                self.main_window.statusBar().showMessage("Selection cancelled.", 2000)
            event.accept()
            return
        super().keyPressEvent(event)

    def _run_update_pc_calculations(self):
        """Updates all Profit and Attendance items in the project based on current tool percentages."""
        m = self.tools_pane.get_mappings()
        pc_sum_col = m.get('pc_sum', -1)
        pc_code_col = m.get('pc_sum_code', -1)
        bill_amt_col = m.get('bill_amount', -1)
        
        if pc_sum_col < 0 or pc_code_col < 0 or bill_amt_col < 0:
            QMessageBox.warning(self, "Mapping Required", "Please map PC Sum, PC Code, and Bill Amount columns first.")
            return

        # 1. Get current percentages from tool
        tool = self.price_pane.pc_sum_tool
        percents = {
            'P-': tool.profit_input.text(),
            'GA-': tool.gen_attendance_input.text(),
            'SA-': tool.spec_attendance_input.text()
        }
        
        # 2. Build map of Parent Codes to Values across all sheets
        parent_values = {} # code_suffix -> float_val
        
        # Collect parents first
        for i in range(self.tabs.count()):
            table = self.tabs.widget(i)
            if not isinstance(table, PBOQTable): continue
            for r in range(table.rowCount()):
                code_item = table.item(r, pc_code_col)
                code_text = code_item.text().strip().upper() if code_item else ""
                
                if code_text.startswith("PC-"):
                    suffix = code_text[3:].strip()
                    val_item = table.item(r, pc_sum_col)
                    if val_item:
                        try:
                            parent_values[suffix] = float(val_item.text().replace(',', ''))
                        except: pass

        # 3. Update children across all sheets
        updated_count = 0
        from PyQt6.QtGui import QBrush
        
        for i in range(self.tabs.count()):
            table = self.tabs.widget(i)
            if not isinstance(table, PBOQTable): continue
            
            # Batch collection for this sheet
            sheet_updates_pct = []
            sheet_updates_amt = []
            
            for r in range(table.rowCount()):
                code_item = table.item(r, pc_code_col)
                code_text = code_item.text().strip().upper() if code_item else ""
                
                prefix = None
                if code_text.startswith("P-"): prefix = "P-"
                elif code_text.startswith("GA-"): prefix = "GA-"
                elif code_text.startswith("SA-"): prefix = "SA-"
                
                if prefix:
                    suffix = code_text[len(prefix):].strip()
                    if suffix in parent_values:
                        new_pct_str = percents[prefix] # e.g. "1.00%"
                        if not new_pct_str: continue
                        
                        parent_val = parent_values[suffix]
                        
                        try:
                            pct_float = float(new_pct_str.replace('%', '').strip()) / 100.0
                        except: pct_float = 0.0
                        
                        new_amt = parent_val * pct_float
                        amt_str = "{:,.2f}".format(new_amt)
                        
                        # Update UI
                        pct_item = table.item(r, pc_sum_col)
                        if not pct_item:
                            pct_item = QTableWidgetItem(new_pct_str)
                            table.setItem(r, pc_sum_col, pct_item)
                        else:
                            pct_item.setText(new_pct_str)
                            
                        amt_item = table.item(r, bill_amt_col)
                        if not amt_item:
                            amt_item = QTableWidgetItem(amt_str)
                            table.setItem(r, bill_amt_col, amt_item)
                        else:
                            amt_item.setText(amt_str)
                        
                        # Apply styling to Bill Amount (Lime Background, Gray Text)
                        amt_item.setBackground(QBrush(const.COLOR_PC_SUM))
                        amt_item.setForeground(QBrush(const.COLOR_GRAY_TEXT))
                        
                        rowid = table.item(r, 0).data(Qt.ItemDataRole.UserRole)
                        sheet_updates_pct.append((rowid, new_pct_str))
                        sheet_updates_amt.append((rowid, amt_str))
                        
                        # Recalculate extension locally
                        self._recalculate_row_extension(table, r, rowid)
                        updated_count += 1
            
            # Persist batch updates for this sheet
            if sheet_updates_pct:
                self._persist_updates(pc_sum_col, sheet_updates_pct)
            if sheet_updates_amt:
                self._persist_updates(bill_amt_col, sheet_updates_amt)
                
        self._update_stats()
        QMessageBox.information(self, "Update Complete", f"Successfully updated and recalculated {updated_count} Profit and Attendance items across all project sheets.")

    def _insert_daywork_value(self, table, row, col, rowid, field_type):
        """Starts Daywork Selection Mode to link this value to a parent cost item."""
        self._pc_selection_mode = True # Reusing same mode flag
        self._pc_selection_data = {
            'target_rowid': rowid,
            'target_row': row,
            'target_col': col,
            'field_type': field_type,
            'table': table
        }
        QApplication.setOverrideCursor(Qt.CursorShape.CrossCursor)
        if self.main_window:
            if not hasattr(self, '_pc_notif_label'):
                self._pc_notif_label = QLabel()
                self._pc_notif_label.setStyleSheet("color: #0000FF; font-weight: bold; margin-left: 10px;")
            
            self._pc_notif_label.setText("SELECT PARENT ITEM: Click on the parent row in the table (or press ESC to cancel)...")
            self.main_window.statusBar().addWidget(self._pc_notif_label)
            self._pc_notif_label.show()
            self.main_window.statusBar().showMessage("")

    def _run_update_daywork_calculations(self):
        """Updates all Daywork items in the project based on current tool percentages."""
        m = self.tools_pane.get_mappings()
        dw_sum_col = m.get('daywork', -1)
        dw_code_col = m.get('daywork_code', -1)
        bill_amt_col = m.get('bill_amount', -1)
        
        if dw_sum_col < 0 or dw_code_col < 0 or bill_amt_col < 0:
            QMessageBox.warning(self, "Mapping Required", "Please map Daywork, Daywork Code, and Bill Amount columns first.")
            return

        # 1. Get current percentages from tool
        tool = self.price_pane.dw_tool
        percents = {
            'P&O-MAT-': tool.mat_input.text(),
            'P&O-LAB-': tool.lab_input.text(),
            'P&O-PLT-': tool.plt_input.text()
        }
        
        # 2. Build map of ALL item Codes to their Bill Amounts (Potential parents)
        all_codes_to_values = {} 
        for i in range(self.tabs.count()):
            table = self.tabs.widget(i)
            if not isinstance(table, PBOQTable): continue
            for r in range(table.rowCount()):
                # Check all possible code columns
                row_code = None
                for code_key in ['rate_code', 'plug_code', 'pc_sum_code', 'prov_sum_code', 'daywork_code']:
                    c_idx = m.get(code_key, -1)
                    if c_idx >= 0:
                        it = table.item(r, c_idx)
                        if it and it.text().strip():
                            row_code = it.text().strip()
                            break
                
                if row_code:
                    amt_item = table.item(r, bill_amt_col)
                    if amt_item:
                        try:
                            all_codes_to_values[row_code] = float(amt_item.text().replace(',', ''))
                        except: pass

        # 3. Update Daywork children across all sheets
        updated_count = 0
        from PyQt6.QtGui import QBrush
        
        for i in range(self.tabs.count()):
            table = self.tabs.widget(i)
            if not isinstance(table, PBOQTable): continue
            
            sheet_updates_pct = []
            sheet_updates_amt = []
            
            for r in range(table.rowCount()):
                code_item = table.item(r, dw_code_col)
                code_text = code_item.text().strip().upper() if code_item else ""
                
                prefix = None
                if code_text.startswith("P&O-MAT-"): prefix = "P&O-MAT-"
                elif code_text.startswith("P&O-LAB-"): prefix = "P&O-LAB-"
                elif code_text.startswith("P&O-PLT-"): prefix = "P&O-PLT-"
                
                if prefix:
                    suffix = code_text[len(prefix):].strip() # The Parent Code
                    if suffix in all_codes_to_values:
                        new_pct_str = percents[prefix]
                        if not new_pct_str: continue
                        
                        parent_val = all_codes_to_values[suffix]
                        try: pct_float = float(new_pct_str.replace('%', '').strip()) / 100.0
                        except: pct_float = 0.0
                        
                        new_amt = parent_val * pct_float
                        amt_str = "{:,.2f}".format(new_amt)
                        
                        # Update UI
                        pct_item = table.item(r, dw_sum_col)
                        if not pct_item:
                            pct_item = QTableWidgetItem(new_pct_str); table.setItem(r, dw_sum_col, pct_item)
                        else: pct_item.setText(new_pct_str)
                            
                        amt_item = table.item(r, bill_amt_col)
                        if not amt_item:
                            amt_item = QTableWidgetItem(amt_str); table.setItem(r, bill_amt_col, amt_item)
                        else: amt_item.setText(amt_str)
                        
                        amt_item.setBackground(QBrush(const.COLOR_DAYWORK))
                        amt_item.setForeground(QBrush(const.COLOR_GRAY_TEXT))
                        
                        rowid = table.item(r, 0).data(Qt.ItemDataRole.UserRole)
                        sheet_updates_pct.append((rowid, new_pct_str))
                        sheet_updates_amt.append((rowid, amt_str))
                        
                        self._recalculate_row_extension(table, r, rowid)
                        updated_count += 1
            
            if sheet_updates_pct: self._persist_updates(dw_sum_col, sheet_updates_pct)
            if sheet_updates_amt: self._persist_updates(bill_amt_col, sheet_updates_amt)
            
        self._update_stats()
        QMessageBox.information(self, "Update Complete", f"Successfully updated and recalculated {updated_count} Daywork items.")

    def _clear_daywork_and_code(self):
        m = self.tools_pane.get_mappings()
        self._clear_columns([m.get('daywork', -1), m.get('daywork_code', -1)], "Daywork & Code")
