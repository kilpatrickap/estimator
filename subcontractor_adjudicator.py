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
COLOR_MIDDLE = QColor("#fff9c4")   # Light yellow — middle rate
COLOR_TOTAL_BEST = QColor("#2E7D32")  # Dark green text for lowest total


class PackageAdjudicatorDialog(QDialog):
    def __init__(self, pboq_db_path, pkg_db_col, parent=None):
        super().__init__(parent)
        self.pboq_db_path = pboq_db_path
        self.pkg_db_col = pkg_db_col
        self.setWindowTitle("Subcontractor Package Adjudicator")
        self.resize(1250, 680) # Optimized default for 1366x768
        self.setMinimumSize(900, 500)
        self._init_ui()
        self._load_packages()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8) # Tighter margins
        layout.setSpacing(6)                  # Tighter spacing
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
        
        # Link header resizing to the summary table
        self.table.horizontalHeader().sectionResized.connect(self._on_section_resized)
        
        layout.addWidget(self.table)
        
        # Summary Row (totals)
        self.summary_table = QTableWidget()
        self.summary_table.setColumnCount(BASE_COL_COUNT)
        self.summary_table.setRowCount(1)
        self.summary_table.setFixedHeight(36)
        self.summary_table.horizontalHeader().hide()
        
        # Show vertical header to match the main table's row number offset
        self.summary_table.verticalHeader().setVisible(True)
        self.summary_table.setVerticalHeaderLabels([""])
        self.summary_table.verticalHeader().setFixedWidth(self.table.verticalHeader().width())
        
        # Hide summary scrollbars visually, but link horizontal scroll to main table
        self.summary_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.summary_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.table.horizontalScrollBar().valueChanged.connect(
            self.summary_table.horizontalScrollBar().setValue
        )

        # Winner Display (Col 1 - Description)
        winner_lbl = QTableWidgetItem("WINNER: [NONE SELECTED]")
        winner_lbl.setForeground(COLOR_TOTAL_BEST)
        f = winner_lbl.font()
        f.setBold(True)
        winner_lbl.setFont(f)
        winner_lbl.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        winner_lbl.setFlags(winner_lbl.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.summary_table.setItem(0, 1, winner_lbl)

        # "TOTALS:" Label right next to the figures (Col 3 / Unit)
        lbl_item = QTableWidgetItem("TOTALS:")
        lbl_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        font = lbl_item.font()
        font.setBold(True)
        lbl_item.setFont(font)
        lbl_item.setFlags(lbl_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.summary_table.setItem(0, BASE_COL_COUNT - 1, lbl_item)

        # Fill remaining base cells
        for c in [0, 2]: # Ref and Qty columns are empty
            it = QTableWidgetItem("")
            it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.summary_table.setItem(0, c, it)
            
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
        # Match vertical header width (row numbers)
        self.summary_table.verticalHeader().setFixedWidth(self.table.verticalHeader().width())
        for i in range(self.table.columnCount()):
            self.summary_table.setColumnWidth(i, self.table.columnWidth(i))

    def _on_section_resized(self, logicalIndex, oldSize, newSize):
        """Keep summary table perfectly aligned when user drags headers."""
        self.summary_table.setColumnWidth(logicalIndex, newSize)

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
        
        it = self.summary_table.item(0, 1) # Winner is now in cell 1 (Description)
        if it:
            it.setText(f"WINNER: {winner_name.upper()}" if winner_name else "WINNER: [NONE SELECTED]")

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
        
        # Initial sizing - tightened for 768p efficiency
        self.table.setColumnWidth(0, 60)  # Ref/Item
        self.table.setColumnWidth(1, 400) # Description (keep wide)
        self.table.setColumnWidth(2, 60)  # Qty
        self.table.setColumnWidth(3, 50)  # Unit
        
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
        """Calculates package totals per subcontractor with robust numeric parsing."""
        def clean_float(text):
            if not text: return 0.0
            try:
                # Remove commas, spaces, and other non-numeric visual formatting
                clean_text = text.replace(',', '').replace(' ', '').strip()
                return float(clean_text) if clean_text else 0.0
            except (ValueError, TypeError):
                return 0.0

        totals = []
        for s_idx, sub_name in enumerate(self.subcontractors):
            col = BASE_COL_COUNT + s_idx
            total = 0.0
            for r in range(self.table.rowCount()):
                qty_item = self.table.item(r, 2)
                rate_item = self.table.item(r, col)
                
                qty = clean_float(qty_item.text()) if qty_item else 0.0
                rate = clean_float(rate_item.text()) if rate_item else 0.0
                total += qty * rate
            
            totals.append(total)
            
            total_item = QTableWidgetItem(f"{total:,.2f}")
            font = total_item.font()
            font.setBold(True)
            total_item.setFont(font)
            total_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            total_item.setFlags(total_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.summary_table.setItem(0, col, total_item)

        # Identify and display the dynamic winner (lowest total)
        current_winner_name = ""
        if len(totals) > 0:
            non_zero = [t for t in totals if t > 0]
            if non_zero:
                min_total = min(non_zero)
                # Find the name matching this min total
                for s_idx, total in enumerate(totals):
                    col = BASE_COL_COUNT + s_idx
                    item = self.summary_table.item(0, col)
                    if item:
                        if total == min_total and total > 0:
                            item.setForeground(COLOR_TOTAL_BEST)
                            current_winner_name = self.subcontractors[s_idx] # This is the dynamic winner
                        else:
                            item.setForeground(Qt.GlobalColor.black)
        
        # Update summary label dynamically
        it = self.summary_table.item(0, 1)
        if it:
            if current_winner_name:
                it.setText(f"WINNER: {current_winner_name.upper()}")
            else:
                it.setText("WINNER: [NONE SELECTED]")

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
                    # Anything else is a "middle" value
                    item.setBackground(COLOR_MIDDLE)
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
            if it: it.setText(f"WINNER: {winner.upper()}")
            
            # Tell parent to apply this to pboq_items
            if hasattr(self.parent(), 'apply_winning_subcontractor'):
                self.parent().apply_winning_subcontractor(pkg, winner, winning_rates)
                
            self.accept()
