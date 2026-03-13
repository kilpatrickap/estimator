import os
import sqlite3
import json
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QMessageBox, QComboBox, QTabWidget, QWidget,
                             QDockWidget, QApplication, QProgressDialog, QTableWidgetItem, QMenu)
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QColor, QBrush, QAction

import pboq_constants as const
from pboq_logic import PBOQLogic
from pboq_table import PBOQTable
from pboq_tools import PBOQToolsPane

class PBOQDialog(QDialog):
    """Priced Bill of Quantities viewer - Modularized and Maintainable."""
    
    def __init__(self, project_dir, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self.project_dir = project_dir
        self.pboq_folder = os.path.join(self.project_dir, "Priced BOQs")
        
        self.logic = PBOQLogic()
        self.active_links = {}     # source_rowid -> list of dest_rowids
        self.is_syncing_links = False
        self.rowid_to_item0 = {}   # rowid -> QTableWidgetItem (the one in column 0)
        self.db_columns = []
        self.linking_source = None
        
        self.setWindowTitle("Priced Bills of Quantities (PBOQ)")
        self.setMinimumSize(1000, 700)
        
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
        self.tools_pane.populateRequested.connect(self._run_populate_collection)
        self.tools_pane.summarizeRequested.connect(self._run_summary_logic)

    def _setup_top_bar(self):
        top_bar = QHBoxLayout()
        
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
        
        # Stats
        self.stats_label = QLabel("Items: 0 | Priced: 0 | Outstanding: 0")
        self.stats_label.setStyleSheet("font-weight: bold; margin-left: 20px;")
        top_bar.addWidget(self.stats_label)
        
        top_bar.addStretch()
        self.main_layout.addLayout(top_bar)

    def _load_initial_configuration(self):
        last_bill = self._load_viewer_state()
        if last_bill:
            index = self.pboq_file_selector.findText(last_bill)
            if index >= 0:
                self.pboq_file_selector.setCurrentIndex(index)
        
        if self.pboq_file_selector.count() > 0:
            self._load_pboq_db(self.pboq_file_selector.currentIndex())

    def _load_pboq_db(self, index):
        if index < 0: return
        file_path = self.pboq_file_selector.itemData(index)
        
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
        num_display_cols = min(8, len(display_col_names))
        
        formatting_data = self.logic.load_formatting(conn)
        self.active_links = self.logic.load_links(conn)
        
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
                table.setRowCount(len(sheet_entries))
                table.setColumnCount(num_display_cols)
                table.setHorizontalHeaderLabels([f"Column {i}" for i in range(num_display_cols)])
                table.cellClicked.connect(self._handle_table_cell_click)
                
                for r_idx, (global_row_idx, row_id, row_data) in enumerate(sheet_entries):
                    for c_idx in range(num_display_cols):
                        val = row_data[c_idx] if c_idx < len(row_data) else ""
                        item = QTableWidgetItem(str(val) if val is not None else "")
                        
                        if c_idx == 0:
                            item.setData(Qt.ItemDataRole.UserRole, row_id)
                            self.rowid_to_item0[row_id] = item
                        item.setData(Qt.ItemDataRole.UserRole + 1, global_row_idx)
                        
                        # Apply Formatting
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
                
                table.apply_column_colors(num_display_cols)
                table.resizeColumnsToContents()
                self.tabs.addTab(table, sheet_name)
                if progress.wasCanceled():
                    break
            
            progress.setValue(len(rows))
        finally:
            progress.close()
            self.tabs.blockSignals(False)
            
        self._load_pboq_state(index)
        self._update_column_headers()
        self._update_stats()

    def _apply_item_format(self, item, fmt):
        font = item.font()
        if fmt.get('bold'): font.setBold(True)
        if fmt.get('italic'): font.setItalic(True)
        item.setFont(font)
        if 'font_color' in fmt: item.setForeground(QColor(fmt['font_color']))
        if 'bg_color' in fmt: item.setBackground(QColor(fmt['bg_color']))

    def _handle_context_menu(self, table, pos, row, col, rowid):
        m = self.tools_pane.get_mappings()
        if col != m['bill_amount']: return
        
        menu = QMenu(self)
        clear_act = menu.addAction("Clear")
        link_act = menu.addAction("Link to Collection")
        
        action = menu.exec(table.viewport().mapToGlobal(pos))
        if not action: return
        
        if action == clear_act:
            item = table.item(row, col)
            if item:
                item.setText("")
                self.logic.remove_link(self.pboq_file_selector.currentData(), rowid)
                self._persist_updates(m['bill_amount'], [(rowid, "")])
                self._update_stats()
        elif action == link_act:
            self._start_link_mode(table, row, col, rowid)

    def _start_link_mode(self, table, row, col, rowid):
        item = table.item(row, col)
        if not item or not item.text().strip(): return
        
        self._clear_link_mode()
        self.linking_source = {
            'table': table, 'row': row, 'col': col, 'rowid': rowid,
            'val': item.text(), 'item': item, 'orig_bg': item.background()
        }
        item.setBackground(const.COLOR_LINK_CYAN)

    def _handle_table_cell_click(self, row, col):
        if not self.linking_source: return
        table = self.sender()
        m = self.tools_pane.get_mappings()
        
        if col == m['bill_amount'] and (table != self.linking_source['table'] or row != self.linking_source['row']):
            dest_rowid = table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            source_rowid = self.linking_source['rowid']
            val = self.linking_source['val']

            # Update DB
            self.logic.remove_link(self.pboq_file_selector.currentData(), dest_rowid)
            self.logic.save_link(self.pboq_file_selector.currentData(), source_rowid, dest_rowid)
            
            # Update cache
            if source_rowid not in self.active_links: self.active_links[source_rowid] = []
            if dest_rowid not in self.active_links[source_rowid]: self.active_links[source_rowid].append(dest_rowid)

            # Update UI
            item = table.item(row, col)
            if not item:
                item = QTableWidgetItem()
                table.setItem(row, col, item)
            item.setText(val)
            item.setBackground(const.COLOR_POPULATE)
            item.setForeground(const.COLOR_GRAY_TEXT)
            
            self._persist_updates(m['bill_amount'], [(dest_rowid, val)])
            self._update_stats()
            self._clear_link_mode()

    def _clear_link_mode(self):
        if self.linking_source:
            self.linking_source['item'].setBackground(self.linking_source['orig_bg'])
            self.linking_source = None

    def _persist_updates(self, display_col, updates):
        file_path = self.pboq_file_selector.currentData()
        self.logic.persist_batch_updates(file_path, self.db_columns, display_col, updates)
        
        # Trigger Live Sync if it's the Bill Amount
        m = self.tools_pane.get_mappings()
        if display_col == m['bill_amount'] and not self.is_syncing_links:
            self._sync_live_links(updates)

    def _sync_live_links(self, updates):
        self.is_syncing_links = True
        m = self.tools_pane.get_mappings()
        cascading = []
        for src_id, val in updates:
            if src_id in self.active_links:
                for dst_id in self.active_links[src_id]:
                    item0 = self.rowid_to_item0.get(dst_id)
                    if item0:
                        table = item0.tableWidget()
                        row = table.row(item0)
                        item = table.item(row, m['bill_amount'])
                        if not item:
                            item = QTableWidgetItem()
                            table.setItem(row, m['bill_amount'], item)
                        item.setText(str(val))
                        item.setBackground(const.COLOR_POPULATE)
                        cascading.append((dst_id, val))
        if cascading:
            self._persist_updates(m['bill_amount'], cascading)
        self.is_syncing_links = False

    def _update_stats(self):
        m = self.tools_pane.get_mappings()
        total, priced = 0, 0
        for i in range(self.tabs.count()):
            t = self.tabs.widget(i)
            for r in range(t.rowCount()):
                qty_item = t.item(r, m['qty'])
                if qty_item and qty_item.text().strip():
                    total += 1
                    rate_item = t.item(r, m['rate'])
                    if rate_item and rate_item.text().strip():
                        priced += 1
        self.stats_label.setText(f"Items: {total} | Priced: {priced} | Outstanding: {total - priced}")

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
        headers = ["Column 0", "Column 1", "Column 2", "Column 3", 
                   "Column 4", "Column 5", "Column 6", "Column 7"]
        
        map_inv = {v: k for k, v in m.items() if v >= 0}
        for i in range(8):
            if i in map_inv:
                headers[i] = f"[{map_inv[i].upper()}] Col {i}"
        
        for idx in range(self.tabs.count()):
            self.tabs.widget(idx).setHorizontalHeaderLabels(headers)

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
                
                if is_revert:
                    if rate_item and rate_item.text() == d_rate_str and rate_item.foreground().color().name().lower() == const.COLOR_GRAY_TEXT.name().lower():
                        rate_item.setText("")
                        rate_updates.append((rowid, ""))
                        if m['bill_amount'] >= 0:
                            amt_item = table.item(r, m['bill_amount'])
                            if amt_item: amt_item.setText("")
                            amt_updates.append((rowid, ""))
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
            if amt_updates: self._persist_updates(m['bill_amount'], amt_updates)
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

    def _run_collect_logic(self):
        m = self.tools_pane.get_mappings()
        if m['desc'] < 0 or m['bill_amount'] < 0: return
        
        is_revert = self.tools_pane.collect_btn.text() == "Revert"
        kw = self.tools_pane.collect_search_bar.text().lower().strip()
        updates = []
        
        for i in range(self.tabs.count()):
            t = self.tabs.widget(i)
            cur_sum = 0.0
            for r in range(t.rowCount()):
                item_desc = t.item(r, m['desc'])
                item_amt = t.item(r, m['bill_amount'])
                rowid = t.item(r, 0).data(Qt.ItemDataRole.UserRole)
                g_idx = item_amt.data(Qt.ItemDataRole.UserRole + 1) if item_amt else None
                
                if is_revert:
                    if item_amt and item_amt.background().color() == const.COLOR_COLLECT:
                        item_amt.setText("")
                        item_amt.setBackground(QBrush()) # Table will reset to alternating color
                        updates.append((rowid, ""))
                        if g_idx is not None: self.logic.clear_cell_formatting(self.pboq_file_selector.currentData(), g_idx, m['bill_amount'])
                else:
                    if not kw: continue
                    if item_desc and kw in item_desc.text().lower():
                        if not item_amt:
                            item_amt = QTableWidgetItem()
                            t.setItem(r, m['bill_amount'], item_amt)
                        
                        f_sum = "{:,.2f}".format(cur_sum)
                        item_amt.setText(f_sum)
                        item_amt.setBackground(const.COLOR_COLLECT)
                        item_amt.setForeground(const.COLOR_GRAY_TEXT)
                        updates.append((rowid, f_sum))
                        if g_idx is not None: 
                            self.logic.persist_cell_formatting(self.pboq_file_selector.currentData(), g_idx, m['bill_amount'], bg_color=const.COLOR_COLLECT.name(), fg_color=const.COLOR_GRAY_TEXT.name())
                        cur_sum = 0.0
                    else:
                        if item_amt and item_amt.text().strip():
                            try: cur_sum += float(item_amt.text().replace(',', ''))
                            except ValueError: pass
        
        if updates:
            self._persist_updates(m['bill_amount'], updates)
            self.tools_pane.collect_btn.setText("Collect" if is_revert else "Revert")

    def _run_populate_collection(self):
        m = self.tools_pane.get_mappings()
        tgt = self.tools_pane.collection_target_bar.text().strip()
        is_revert = self.tools_pane.populate_btn.text() == "Un-Populate"
        if not tgt and not is_revert: return
        
        updates = []
        for i in range(self.tabs.count()):
            t = self.tabs.widget(i)
            bucket = []
            if not is_revert:
                for r in range(t.rowCount()):
                    item = t.item(r, m['bill_amount'])
                    if item and item.background().color() == const.COLOR_COLLECT:
                        rowid = t.item(r, 0).data(Qt.ItemDataRole.UserRole)
                        bucket.append((rowid, item.text()))
            
            found = False
            b_idx = 0
            for r in range(t.rowCount()):
                id_item = t.item(r, 0)
                rowid = id_item.data(Qt.ItemDataRole.UserRole)
                desc_text = t.item(r, m['desc']).text() if t.item(r, m['desc']) else ""
                
                if not found:
                    if tgt in desc_text: found = True
                    continue
                
                has_qty = t.item(r, m['qty']) and t.item(r, m['qty']).text().strip()
                amt_item = t.item(r, m['bill_amount'])
                
                if is_revert:
                    if desc_text.strip() and not has_qty and amt_item and amt_item.background().color() == const.COLOR_POPULATE:
                        amt_item.setText("")
                        amt_item.setBackground(QBrush())
                        updates.append((rowid, ""))
                        self.logic.remove_link(self.pboq_file_selector.currentData(), rowid)
                else:
                    if desc_text.strip() and not has_qty and (not amt_item or not amt_item.text().strip()):
                        if b_idx < len(bucket):
                            src_id, val = bucket[b_idx]
                            if not amt_item:
                                amt_item = QTableWidgetItem()
                                t.setItem(r, m['bill_amount'], amt_item)
                            amt_item.setText(val)
                            amt_item.setBackground(const.COLOR_POPULATE)
                            amt_item.setForeground(const.COLOR_GRAY_TEXT)
                            updates.append((rowid, val))
                            self.logic.save_link(self.pboq_file_selector.currentData(), src_id, rowid)
                            b_idx += 1
                        else: break
        
        if updates:
            self._persist_updates(m['bill_amount'], updates)
            self.tools_pane.populate_btn.setText("Populate" if is_revert else "Un-Populate")

    def _run_summary_logic(self):
        m = self.tools_pane.get_mappings()
        tgt = self.tools_pane.summary_target_bar.text().lower().strip()
        if not tgt: return
        
        for i in range(self.tabs.count()):
            t = self.tabs.widget(i)
            total_val = 0.0
            for r in range(t.rowCount()):
                item = t.item(r, m['bill_amount'])
                if item and item.background().color() == const.COLOR_COLLECT:
                    try: total_val += float(item.text().replace(',', ''))
                    except ValueError: pass
            
            updates = []
            f_sum = "{:,.2f}".format(total_val)
            for r in range(t.rowCount()):
                desc = t.item(r, m['desc']).text().lower() if t.item(r, m['desc']) else ""
                if tgt in desc:
                    item = t.item(r, m['bill_amount'])
                    if not item:
                        item = QTableWidgetItem()
                        t.setItem(r, m['bill_amount'], item)
                    item.setText(f_sum)
                    item.setBackground(const.COLOR_SUMMARY)
                    item.setForeground(const.COLOR_GRAY_TEXT)
                    rowid = t.item(r, 0).data(Qt.ItemDataRole.UserRole)
                    updates.append((rowid, f_sum))
                    g_idx = item.data(Qt.ItemDataRole.UserRole + 1)
                    if g_idx is not None: self.logic.persist_cell_formatting(self.pboq_file_selector.currentData(), g_idx, m['bill_amount'], bg_color=const.COLOR_SUMMARY.name(), fg_color=const.COLOR_GRAY_TEXT.name())
            
            if updates: self._persist_updates(m['bill_amount'], updates)

    def _clear_gross_and_code(self):
        m = self.tools_pane.get_mappings()
        reply = QMessageBox.question(self, "Clear All?", "Clear ALL Gross Rates and Codes?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.No: return
        
        for i in range(self.tabs.count()):
            t = self.tabs.widget(i)
            r_updates, c_updates = [], []
            for r in range(t.rowCount()):
                rowid = t.item(r, 0).data(Qt.ItemDataRole.UserRole)
                if m['rate'] >= 0:
                    item = t.item(r, m['rate'])
                    if item: item.setText(""); r_updates.append((rowid, ""))
                if m['rate_code'] >= 0:
                    item = t.item(r, m['rate_code'])
                    if item: item.setText(""); c_updates.append((rowid, ""))
            if r_updates: self._persist_updates(m['rate'], r_updates)
            if c_updates: self._persist_updates(m['rate_code'], c_updates)

    # --- State Management ---
    def _save_pboq_state(self):
        idx = self.pboq_file_selector.currentIndex()
        if idx < 0: return
        file_path = self.pboq_file_selector.itemData(idx)
        state_dir = os.path.join(self.project_dir, "PBOQ States")
        os.makedirs(state_dir, exist_ok=True)
        
        state = {
            'mappings': self.tools_pane.get_mappings(),
            'active_tab': self.tabs.currentIndex(),
            'wrap_text': self.tools_pane.wrap_text_btn.isChecked()
        }
        
        state_file = os.path.join(state_dir, os.path.basename(file_path) + ".json")
        with open(state_file, 'w') as f:
            json.dump(state, f)

    def _load_pboq_state(self, index):
        file_path = self.pboq_file_selector.itemData(index)
        state_file = os.path.join(self.project_dir, "PBOQ States", os.path.basename(file_path) + ".json")
        if os.path.exists(state_file):
            with open(state_file, 'r') as f:
                state = json.load(f)
                self.tools_pane.set_mappings(state.get('mappings', {}))
                self.tabs.setCurrentIndex(state.get('active_tab', 0))
                self.tools_pane.wrap_text_btn.setChecked(state.get('wrap_text', False))
                # Apply word wrap state after loading
                self._toggle_wrap_text(self.tools_pane.wrap_text_btn.isChecked())

    def _save_viewer_state(self):
        settings_file = os.path.join(self.project_dir, "PBOQ States", "viewer_state.json")
        os.makedirs(os.path.dirname(settings_file), exist_ok=True)
        with open(settings_file, 'w') as f:
            json.dump({'last_bill': self.pboq_file_selector.currentText()}, f)

    def _load_viewer_state(self):
        settings_file = os.path.join(self.project_dir, "PBOQ States", "viewer_state.json")
        if os.path.exists(settings_file):
            with open(settings_file, 'r') as f:
                return json.load(f).get('last_bill')
        return None

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
