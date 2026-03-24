import sqlite3
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, 
                             QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
                             QMessageBox, QInputDialog, QAbstractItemView)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QBrush

# Number of fixed (read-only) base columns: Ref, Description, Qty, Unit
BASE_COL_COUNT = 4

# Colors for comparison highlighting
COLOR_LOWEST = QColor("#c8e6c9")   # Light green — best rate
COLOR_HIGHEST = QColor("#ffcdd2")  # Light red — worst rate
COLOR_TOTAL_BEST = QColor("#2E7D32")  # Dark green text for lowest total


class PackageAdjudicatorDialog(QDialog):
    def __init__(self, pboq_db_path, pkg_db_col, parent=None):
        super().__init__(parent)
        self.pboq_db_path = pboq_db_path
        self.pkg_db_col = pkg_db_col
        self.setWindowTitle("Subcontractor Package Adjudicator")
        self.setMinimumSize(900, 550)
        self._init_ui()
        self._load_packages()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # Top Bar
        top_bar = QHBoxLayout()
        top_bar.addWidget(QLabel("Select Work Package:"))
        self.package_combo = QComboBox()
        self.package_combo.setMinimumWidth(200)
        self.package_combo.currentIndexChanged.connect(self._on_package_selected)
        top_bar.addWidget(self.package_combo)
        top_bar.addStretch()
        
        self.add_subbee_btn = QPushButton("Add Subcontractor")
        self.add_subbee_btn.clicked.connect(self._add_subcontractor)
        top_bar.addWidget(self.add_subbee_btn)

        self.remove_subbee_btn = QPushButton("Remove Subcontractor")
        self.remove_subbee_btn.clicked.connect(self._remove_subcontractor)
        top_bar.addWidget(self.remove_subbee_btn)
        
        layout.addLayout(top_bar)

        # Main Table
        self.table = QTableWidget()
        self.table.setColumnCount(BASE_COL_COUNT)
        self.table.setHorizontalHeaderLabels(["Ref/Item", "Description", "Qty", "Unit"])
        
        # UI Refinements: Adjustable columns and wrapping
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.setWordWrap(True)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.table)
        
        # Summary Row (totals)
        self.summary_table = QTableWidget()
        self.summary_table.setColumnCount(BASE_COL_COUNT)
        self.summary_table.setRowCount(1)
        self.summary_table.setFixedHeight(50)
        self.summary_table.horizontalHeader().hide()
        self.summary_table.verticalHeader().hide()

        lbl_item = QTableWidgetItem("PACKAGE TOTAL:")
        lbl_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        font = lbl_item.font()
        font.setBold(True)
        lbl_item.setFont(font)
        self.summary_table.setItem(0, 0, lbl_item)
        
        # Winner display cell next to label
        winner_lbl = QTableWidgetItem("")
        winner_lbl.setForeground(COLOR_TOTAL_BEST)
        f = winner_lbl.font()
        f.setBold(True)
        winner_lbl.setFont(f)
        winner_lbl.setFlags(winner_lbl.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.summary_table.setItem(0, 1, winner_lbl)

        # Make remaining BASE_COL_COUNT cells non-editable
        for c in range(2, BASE_COL_COUNT):
            it = QTableWidgetItem("")
            it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.summary_table.setItem(0, c, it)

        self.summary_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.summary_table)

        # Bottom Bar
        bottom_bar = QHBoxLayout()
        self.apply_btn = QPushButton("Select Winning Subcontractor")
        self.apply_btn.clicked.connect(self._select_winner)
        bottom_bar.addStretch()
        bottom_bar.addWidget(self.apply_btn)
        
        layout.addLayout(bottom_bar)

        # State vars
        self.items_data = []      # list of dicts: rowid, ref, desc, qty, unit
        self.subcontractors = []  # list of names

    def _sync_table_widths(self):
        for i in range(self.table.columnCount()):
            self.summary_table.setColumnWidth(i, self.table.columnWidth(i))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._sync_table_widths()

    # ── Data Loading ──────────────────────────────────────────────

    def _load_packages(self):
        self.package_combo.blockSignals(True)
        self.package_combo.clear()
        
        conn = sqlite3.connect(self.pboq_db_path)
        cursor = conn.cursor()
        try:
            cursor.execute(f'SELECT DISTINCT "{self.pkg_db_col}" FROM pboq_items WHERE "{self.pkg_db_col}" IS NOT NULL AND "{self.pkg_db_col}" != \'\'')
            packages = [row[0] for row in cursor.fetchall()]
            self.package_combo.addItems(["-- Select Package --"] + sorted(packages))
        except sqlite3.Error:
            pass
        finally:
            conn.close()
            
        self.package_combo.blockSignals(False)

    def _on_package_selected(self):
        pkg = self.package_combo.currentText()
        if pkg == "-- Select Package --" or not pkg:
            self.table.setRowCount(0)
            self.subcontractors = []
            self._update_headers()
            return
            
        # Get items from parent PBOQ dialog
        if hasattr(self.parent(), 'get_package_items'):
            self.items_data = self.parent().get_package_items(pkg)
        else:
            self.items_data = []
        
        # Load existing quotes from DB
        self.subcontractors = []
        quotes = {}
        try:
            conn = sqlite3.connect(self.pboq_db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT subcontractor_name, row_idx, rate FROM subcontractor_quotes WHERE package_name=?", (pkg,))
            for sub_name, rid, rate in cursor.fetchall():
                if sub_name not in self.subcontractors:
                    self.subcontractors.append(sub_name)
                    quotes[sub_name] = {}
                quotes[sub_name][rid] = rate
            conn.close()
        except sqlite3.Error:
            pass

        self._build_table(quotes)
        self._load_current_winner(pkg)

    def _load_current_winner(self, pkg):
        """Looks up currently assigned subcontractor in PBOQ and shows in summary."""
        winner_name = ""
        try:
            # We assume SubbeeName is standard or we check parent's mapping
            if hasattr(self.parent(), 'tools_pane'):
                m = self.parent().tools_pane.get_mappings()
                name_disp_col = m.get('sub_name', -1)
                if name_disp_col >= 0 and hasattr(self.parent(), 'db_columns'):
                    name_db_col = self.parent().db_columns[name_disp_col + 1]
                    
                    conn = sqlite3.connect(self.pboq_db_path)
                    cursor = conn.cursor()
                    cursor.execute(f'SELECT "{name_db_col}" FROM pboq_items WHERE "{self.pkg_db_col}" = ? AND "{name_db_col}" != \'\' LIMIT 1', (pkg,))
                    res = cursor.fetchone()
                    if res: winner_name = res[0]
                    conn.close()
        except:
            pass
        
        it = self.summary_table.item(0, 1)
        if it:
            it.setText(f" [{winner_name.upper()}]" if winner_name else " [NONE SELECTED]")

    # ── Table Construction ────────────────────────────────────────

    def _build_table(self, quotes):
        self.table.blockSignals(True)
        self.table.setRowCount(len(self.items_data))
        self._update_headers()
        
        for r, d in enumerate(self.items_data):
            # Base columns: Ref, Description, Qty, Unit
            self.table.setItem(r, 0, QTableWidgetItem(str(d.get('ref', ''))))
            self.table.setItem(r, 1, QTableWidgetItem(str(d.get('desc', ''))))
            self.table.setItem(r, 2, QTableWidgetItem(str(d.get('qty', ''))))
            self.table.setItem(r, 3, QTableWidgetItem(str(d.get('unit', ''))))
            
            # Make base columns read-only
            for c in range(BASE_COL_COUNT):
                item = self.table.item(r, c)
                if item:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)

            # Fill quotes
            rid = d.get('rowid')
            for s_idx, sub in enumerate(self.subcontractors):
                col = BASE_COL_COUNT + s_idx
                rate = quotes.get(sub, {}).get(rid, "")
                if rate:
                    self.table.setItem(r, col, QTableWidgetItem(f"{rate:,.2f}"))
                else:
                    self.table.setItem(r, col, QTableWidgetItem(""))
        
        self.table.blockSignals(False)
        self._calculate_totals()
        self._apply_comparison_colors()

    def _update_headers(self):
        base = ["Ref/Item", "Description", "Qty", "Unit"]
        total_cols = BASE_COL_COUNT + len(self.subcontractors)
        self.table.setColumnCount(total_cols)
        self.summary_table.setColumnCount(total_cols)
        
        headers = base + self.subcontractors
        self.table.setHorizontalHeaderLabels(headers)
        
        # Initial sizing
        self.table.setColumnWidth(0, 80)
        self.table.setColumnWidth(1, 300)
        self.table.setColumnWidth(2, 70)
        self.table.setColumnWidth(3, 60)
        
        self._sync_table_widths()

    # ── Subcontractor Management ──────────────────────────────────

    def _add_subcontractor(self):
        pkg = self.package_combo.currentText()
        if pkg == "-- Select Package --" or not pkg:
            QMessageBox.warning(self, "Select Package", "Please select a work package first.")
            return
            
        name, ok = QInputDialog.getText(self, "New Subcontractor", "Enter Subcontractor Name:")
        if ok and name.strip():
            name = name.strip()
            if name in self.subcontractors:
                QMessageBox.warning(self, "Duplicate", "Subcontractor already exists.")
                return
            self.subcontractors.append(name)
            self._update_headers()
            
            # Add empty column cells
            self.table.blockSignals(True)
            col = BASE_COL_COUNT + len(self.subcontractors) - 1
            for r in range(self.table.rowCount()):
                self.table.setItem(r, col, QTableWidgetItem(""))
            self.table.blockSignals(False)
            self._calculate_totals()

    def _remove_subcontractor(self):
        pkg = self.package_combo.currentText()
        if not self.subcontractors:
            QMessageBox.warning(self, "No Subcontractors", "No subcontractors to remove.")
            return
            
        name, ok = QInputDialog.getItem(self, "Remove Subcontractor", 
                                        "Select subcontractor to remove:", 
                                        self.subcontractors, 0, False)
        if ok and name:
            reply = QMessageBox.question(self, "Confirm Removal", 
                                         f"Remove '{name}' and all their quotes for this package?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply != QMessageBox.StandardButton.Yes:
                return

            # Delete from database
            try:
                conn = sqlite3.connect(self.pboq_db_path)
                cursor = conn.cursor()
                cursor.execute("DELETE FROM subcontractor_quotes WHERE package_name=? AND subcontractor_name=?", (pkg, name))
                conn.commit()
                conn.close()
            except sqlite3.Error as e:
                QMessageBox.critical(self, "Error", f"Failed to remove quotes: {e}")
                return

            # Rebuild table
            self.subcontractors.remove(name)
            # Reload quotes for remaining subcontractors
            quotes = {}
            try:
                conn = sqlite3.connect(self.pboq_db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT subcontractor_name, row_idx, rate FROM subcontractor_quotes WHERE package_name=?", (pkg,))
                for sub_name, rid, rate in cursor.fetchall():
                    if sub_name not in quotes:
                        quotes[sub_name] = {}
                    quotes[sub_name][rid] = rate
                conn.close()
            except sqlite3.Error:
                pass
            self._build_table(quotes)

    # ── Quote Editing & Persistence ───────────────────────────────

    def _on_item_changed(self, item):
        col = item.column()
        if col >= BASE_COL_COUNT:  # Quote column
            self._save_quote(item)
            
            # Format to 2 decimal places with commas
            txt = item.text().replace(',', '')
            try:
                val = float(txt)
                self.table.blockSignals(True)
                item.setText(f"{val:,.2f}")
                self.table.blockSignals(False)
            except ValueError:
                pass

            self._calculate_totals()
            self._apply_comparison_colors()

    def _save_quote(self, item):
        r = item.row()
        c = item.column()
        sub_name = self.subcontractors[c - BASE_COL_COUNT]
        rowid = self.items_data[r]['rowid']
        pkg = self.package_combo.currentText()
        
        txt = item.text().replace(',', '')
        try:
            rate = float(txt) if txt else 0.0
        except ValueError:
            rate = 0.0
            
        try:
            conn = sqlite3.connect(self.pboq_db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT id FROM subcontractor_quotes WHERE package_name=? AND row_idx=? AND subcontractor_name=?", (pkg, rowid, sub_name))
            res = cursor.fetchone()
            if res:
                cursor.execute("UPDATE subcontractor_quotes SET rate=? WHERE id=?", (rate, res[0]))
            else:
                cursor.execute("INSERT INTO subcontractor_quotes (package_name, row_idx, subcontractor_name, rate) VALUES (?, ?, ?, ?)", (pkg, rowid, sub_name, rate))
            
            conn.commit()
            conn.close()
        except sqlite3.Error as e:
            print(f"Error saving quote: {e}")

    # ── Totals & Comparison ───────────────────────────────────────

    def _calculate_totals(self):
        totals = []
        for s_idx, sub_name in enumerate(self.subcontractors):
            col = BASE_COL_COUNT + s_idx
            total = 0.0
            for r in range(self.table.rowCount()):
                qty_txt = self.table.item(r, 2).text().replace(',', '') if self.table.item(r, 2) else ""
                rate_txt = self.table.item(r, col).text().replace(',', '') if self.table.item(r, col) else ""
                
                try:
                    qty = float(qty_txt) if qty_txt else 0.0
                    rate = float(rate_txt) if rate_txt else 0.0
                    total += qty * rate
                except ValueError:
                    pass
            
            totals.append(total)
            
            total_item = QTableWidgetItem(f"{total:,.2f}")
            font = total_item.font()
            font.setBold(True)
            total_item.setFont(font)
            total_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            total_item.setFlags(total_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.summary_table.setItem(0, col, total_item)

        # Highlight lowest total in green
        if len(totals) > 1:
            non_zero = [t for t in totals if t > 0]
            if non_zero:
                min_total = min(non_zero)
                for s_idx, total in enumerate(totals):
                    col = BASE_COL_COUNT + s_idx
                    item = self.summary_table.item(0, col)
                    if item:
                        if total == min_total and total > 0:
                            item.setForeground(COLOR_TOTAL_BEST)
                        else:
                            item.setForeground(Qt.GlobalColor.black)

    def _apply_comparison_colors(self):
        """Color-code the lowest rate per row (green) and highest (red)."""
        if len(self.subcontractors) < 2:
            return

        for r in range(self.table.rowCount()):
            rates = []
            for s_idx in range(len(self.subcontractors)):
                col = BASE_COL_COUNT + s_idx
                item = self.table.item(r, col)
                txt = item.text().replace(',', '') if item else ""
                try:
                    val = float(txt) if txt else None
                except ValueError:
                    val = None
                rates.append(val)

            # Filter to non-zero, non-None values
            valid_rates = [v for v in rates if v is not None and v > 0]
            if len(valid_rates) < 2:
                # Clear any prior coloring if not enough to compare
                for s_idx in range(len(self.subcontractors)):
                    col = BASE_COL_COUNT + s_idx
                    item = self.table.item(r, col)
                    if item:
                        item.setBackground(QBrush(Qt.BrushStyle.NoBrush))
                continue

            min_rate = min(valid_rates)
            max_rate = max(valid_rates)

            self.table.blockSignals(True)
            for s_idx in range(len(self.subcontractors)):
                col = BASE_COL_COUNT + s_idx
                item = self.table.item(r, col)
                if not item:
                    continue
                val = rates[s_idx]
                if val is None or val == 0:
                    item.setBackground(QBrush(Qt.BrushStyle.NoBrush))
                elif val == min_rate:
                    item.setBackground(COLOR_LOWEST)
                elif val == max_rate:
                    item.setBackground(COLOR_HIGHEST)
                else:
                    item.setBackground(QBrush(Qt.BrushStyle.NoBrush))
            self.table.blockSignals(False)

    # ── Winner Selection ──────────────────────────────────────────

    def _select_winner(self):
        pkg = self.package_combo.currentText()
        if not self.subcontractors:
            QMessageBox.warning(self, "No Subcontractors", "No subcontractors to select.")
            return
            
        winner, ok = QInputDialog.getItem(self, "Select Winner", "Choose winning subcontractor for this package:", self.subcontractors, 0, False)
        if ok and winner:
            col = self.subcontractors.index(winner) + BASE_COL_COUNT
            winning_rates = []
            
            for r in range(self.table.rowCount()):
                rowid = self.items_data[r]['rowid']
                item = self.table.item(r, col)
                rate = item.text().strip() if item else ""
                if rate:
                    winning_rates.append((rowid, rate.replace(',', '')))
            
            # Update summary UI
            it = self.summary_table.item(0, 1)
            if it: it.setText(f" [{winner.upper()}]")
            
            # Tell parent to apply this to pboq_items
            if hasattr(self.parent(), 'apply_winning_subcontractor'):
                self.parent().apply_winning_subcontractor(pkg, winner, winning_rates)
                
            self.accept()
