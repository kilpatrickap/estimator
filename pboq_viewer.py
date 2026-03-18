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
        
        self.setWindowTitle("Priced Bills of Quantities (PBOQ)")
        self.setMinimumSize(950, 400)
        
        self._init_ui()
        self._load_initial_configuration()

    def _init_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 5, 10, 10)
        
        # 1. Top Bar
        self._setup_top_bar()
        
        # 2. Tabs for Sheets
        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.TabPosition.South)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.main_layout.addWidget(self.tabs)
        
        # 3. Tools Pane (Docked)
        self.tools_pane = PBOQToolsPane(self)
        self.price_pane = PBOQPricePane(self)
        self.tools_pane.hide()
        self.price_pane.hide()
        
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
        self.price_pane.linkBillRateRequested.connect(self._run_link_bill_to_gross_logic)
        self.price_pane.clearPlugRequested.connect(self._clear_plug_and_code)

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
                        item = QTableWidgetItem(str(val) if val is not None else "")
                        
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
                            item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                            
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
                    self.logic.remove_link(self.pboq_file_selector.currentData(), rowid)
                    self._persist_updates(m['bill_amount'], [(rowid, "")])
                    self._update_stats()
        
        elif col in [m['rate_code'], m.get('plug_code', -1)]:
            item = table.item(row, col)
            if not item or not item.text().strip(): return
            
            rate_code = item.text().strip()
            menu = QMenu(self)
            goto_act = menu.addAction("Go To")
            
            action = menu.exec(table.viewport().mapToGlobal(pos))
            if not action: return
            
            if action == goto_act:
                if self.main_window and hasattr(self.main_window, 'show_rate_in_database'):
                    self.main_window.show_rate_in_database(rate_code)





    def _persist_updates(self, display_col, updates):
        if display_col < 0: return
        file_path = self.pboq_file_selector.currentData()
        self.logic.persist_batch_updates(file_path, self.db_columns, display_col, updates)
        
        # Trigger Collection update IF we are currently in "Revert" mode (meaning it was clicked once)
        # AND we are not already in a logic update.
        m = self.tools_pane.get_mappings()
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
            inactive_cols = [m.get('rate', -1), m.get('rate_code', -1)]
        else: # Gross Rate or others
            active_cols = [m.get('rate', -1), m.get('rate_code', -1)]
            inactive_cols = [m.get('plug_rate', -1), m.get('plug_code', -1)]

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

    def _update_column_headers(self):
        m = self.tools_pane.get_mappings()
        
        friends = {
            'ref': "Ref/Item", 'desc': "Description", 'qty': "Quantity", 'unit': "Unit",
            'bill_rate': "Bill Rate", 'bill_amount': "Bill Amount",
            'rate': "Gross Rate", 'rate_code': "Rate Code",
            'plug_rate': "Plug Rate", 'plug_code': "Plug Code"
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
                
                # Automatically hide blank/extra columns beyond the standard 8
                # but only if they aren't mapped to anything.
                if i >= 8:
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
        
        # Ensure Rate visibility is synced with current mapping
        self._toggle_rate_visibility(self.price_pane.get_rate_visibility())
        
        self._update_stats()

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
                        rate_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
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
                            amt_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
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

    def _clear_columns(self, col_indices, label):
        """Generic helper to clear one or more columns across all sheets."""
        if all(c < 0 for c in col_indices):
            QMessageBox.warning(self, "Clear", f"Please map the {label} columns first.")
            return

        confirm = QMessageBox.question(self, "Clear", f"Are you sure you want to clear {label} content in ALL sheets?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if confirm != QMessageBox.StandardButton.Yes: return

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
                
                # If sticky mode was active, refresh it
                if self.tools_pane.collect_btn.text() == "Revert":
                    self._run_collect_logic(force_collect=True)

    def _save_viewer_state(self):
        settings_file = os.path.join(self.project_dir, "PBOQ States", "viewer_state.json")
        os.makedirs(os.path.dirname(settings_file), exist_ok=True)
        
        state = {
            'last_bill': self.pboq_file_selector.currentText(),
            'active_pane': 'price' if hasattr(self, 'price_pane') and self.tools_dock.widget() == self.price_pane else 'tools'
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
        mapping = self.tools_pane.get_mapping()
        if mapping['desc'] < 0 or mapping['qty'] < 0 or mapping['gross_rate'] < 0 or mapping['rate_code'] < 0:
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
                    gross_item = table.item(r, mapping['gross_rate'])
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
                if mapping['gross_rate'] < 0 or mapping['rate_code'] < 0:
                    conn.close()
                    return
                gross_col_name = self.db_columns[mapping['gross_rate'] + 1]
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
        mapping = self.tools_pane.get_mapping()
        
        if mapping['gross_rate'] < 0 or mapping['rate_code'] < 0:
            QMessageBox.warning(self, "Mapping Error", "Gross Rate or Rate Code columns are not mapped. Cannot revert correctly.")
            return

        revert_count = 0
        db_updates = []

        for i in range(self.tabs.count()):
            table = self.tabs.widget(i)
            if not isinstance(table, PBOQTable): continue
            
            for r in range(table.rowCount()):
                gross_item = table.item(r, mapping['gross_rate'])
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

    def _run_link_bill_to_gross_logic(self):
        """Batch copies Gross Rates to Bill Rates and recalculates Bill Amounts."""
        m = self.tools_pane.get_mappings()
        if m['bill_rate'] < 0 or m['rate'] < 0:
            QMessageBox.warning(self, "Mapping Error", "Please ensure 'Bill Rate' and 'Gross Rate' columns are mapped first.")
            return

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
                
                gross_item = table.item(r, m['rate'])
                if not gross_item or not gross_item.text().strip(): continue
                
                val_str = gross_item.text().strip()
                
                # Update Bill Rate UI
                bill_rate_item = table.item(r, m['bill_rate'])
                if not bill_rate_item:
                    bill_rate_item = QTableWidgetItem()
                    table.setItem(r, m['bill_rate'], bill_rate_item)
                
                bill_rate_item.setText(val_str)
                # Cyan shows it's linked
                bill_rate_item.setBackground(const.COLOR_LINK_CYAN)
                bill_rate_item.setForeground(const.COLOR_GRAY_TEXT)
                bill_rate_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                
                link_updates.append((row_id, val_str))
                
                # Also update Bill Amount if Quantity exists
                if m['qty'] >= 0 and m['bill_amount'] >= 0:
                    qty_item = table.item(r, m['qty'])
                    if qty_item and qty_item.text().strip():
                        try:
                            # Parse Qty and Rate (handle commas)
                            q_val = float(qty_item.text().replace(',', ''))
                            r_val = float(val_str.replace(',', ''))
                            a_val = q_val * r_val
                            a_str = "{:,.2f}".format(a_val)
                            
                            amt_item = table.item(r, m['bill_amount'])
                            if not amt_item:
                                amt_item = QTableWidgetItem()
                                table.setItem(r, m['bill_amount'], amt_item)
                            
                            amt_item.setText(a_str)
                            amt_item.setForeground(const.COLOR_GRAY_TEXT)
                            amt_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                            amt_updates.append((row_id, a_str))
                        except ValueError: pass

        if link_updates:
            self._persist_updates(m['bill_rate'], link_updates)
            
            # Persist formatting (Cyan BG + Gray Text)
            fmt_updates = []
            for rid, _ in link_updates:
                item0 = self.rowid_to_item0.get(rid)
                if not item0: continue
                g_idx = item0.data(Qt.ItemDataRole.UserRole + 1)
                fmt_updates.append((g_idx, {'bg_color': const.COLOR_LINK_CYAN.name(), 'font_color': const.COLOR_GRAY_TEXT.name()}))
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

            QMessageBox.information(self, "Linked", f"Successfully linked {len(link_updates)} Bill Rate cells to Gross Rates.\nBill Amounts have been updated where quantities were available.")
            self._update_stats()
        else:
            QMessageBox.information(self, "No Links", "No items with Gross Rates were found to link in the current view.")

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
