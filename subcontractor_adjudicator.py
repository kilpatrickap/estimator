import sqlite3
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, 
                             QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
                             QMessageBox, QInputDialog, QAbstractItemView)
from PyQt6.QtCore import Qt

class PackageAdjudicatorDialog(QDialog):
    def __init__(self, pboq_db_path, parent=None):
        super().__init__(parent)
        self.pboq_db_path = pboq_db_path
        self.setWindowTitle("Subcontractor Package Adjudicator")
        self.setMinimumSize(800, 500)
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
        
        layout.addLayout(top_bar)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Description", "Qty", "Unit"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.table)
        
        # Summary Row (totals)
        self.summary_table = QTableWidget()
        self.summary_table.setColumnCount(3)
        self.summary_table.setRowCount(1)
        self.summary_table.setFixedHeight(60)
        self.summary_table.horizontalHeader().hide()
        self.summary_table.verticalHeader().hide()
        self.summary_table.setItem(0, 0, QTableWidgetItem("PACKAGE TOTAL:"))
        self.summary_table.item(0, 0).setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        font = self.summary_table.item(0, 0).font()
        font.setBold(True)
        self.summary_table.item(0, 0).setFont(font)
        
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
        self.items_data = [] # list of dicts: rowid, desc, qty, unit
        self.subcontractors = [] # list of names

    def _sync_table_widths(self):
        for i in range(1, self.table.columnCount()):
            self.summary_table.setColumnWidth(i, self.table.columnWidth(i))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._sync_table_widths()

    def _load_packages(self):
        self.package_combo.blockSignals(True)
        self.package_combo.clear()
        
        conn = sqlite3.connect(self.pboq_db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT DISTINCT SubbeePackage FROM pboq_items WHERE SubbeePackage IS NOT NULL AND SubbeePackage != ''")
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
            
        # Extract columns logic requires finding mapped desc/qty/unit, but here we'll just read db columns directly via PBOQDialog knowledge, or dynamically.
        # Actually, pboq_items columns: Sheet, Column 1..N. Since formatting table maps row,col -> we can't easily query desc if we don't know the column. 
        # But we can query the rowid. For now, let's fetch all rows for the package and assume standard column order if possible, or query the view.
        # Wait, the parent (PBOQDialog) has the mappings. We can ask parent for data.
        if hasattr(self.parent(), 'get_package_items'):
            self.items_data = self.parent().get_package_items(pkg)
        else:
            self.items_data = [] # fallback if not implemented
        
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

    def _build_table(self, quotes):
        self.table.blockSignals(True)
        self.table.setRowCount(len(self.items_data))
        self._update_headers()
        
        for r, d in enumerate(self.items_data):
            self.table.setItem(r, 0, QTableWidgetItem(str(d.get('desc', ''))))
            self.table.setItem(r, 1, QTableWidgetItem(str(d.get('qty', ''))))
            self.table.setItem(r, 2, QTableWidgetItem(str(d.get('unit', ''))))
            
            # Make first 3 cols read-only
            for c in range(3):
                item = self.table.item(r, c)
                if item: item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)

            # Fill quotes
            rid = d.get('rowid')
            for c, sub in enumerate(self.subcontractors):
                col = c + 3
                rate = quotes.get(sub, {}).get(rid, "")
                if rate:
                    self.table.setItem(r, col, QTableWidgetItem(f"{rate:,.2f}"))
                else:
                    self.table.setItem(r, col, QTableWidgetItem(""))
        
        self.table.blockSignals(False)
        self._calculate_totals()

    def _update_headers(self):
        base = ["Description", "Qty", "Unit"]
        self.table.setColumnCount(len(base) + len(self.subcontractors))
        self.summary_table.setColumnCount(len(base) + len(self.subcontractors))
        
        headers = base + self.subcontractors
        self.table.setHorizontalHeaderLabels(headers)
        self._sync_table_widths()

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
            
            # add empty column
            self.table.blockSignals(True)
            col = len(self.subcontractors) + 2
            for r in range(self.table.rowCount()):
                self.table.setItem(r, col, QTableWidgetItem(""))
            self.table.blockSignals(False)
            self._calculate_totals()

    def _on_item_changed(self, item):
        col = item.column()
        if col >= 3: # Quote column
            self._save_quote(item)
            self._calculate_totals()

    def _save_quote(self, item):
        r = item.row()
        c = item.column()
        sub_name = self.subcontractors[c - 3]
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
            
            # Check if exists
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

    def _calculate_totals(self):
        for c, sub_name in enumerate(self.subcontractors):
            col = c + 3
            total = 0.0
            for r in range(self.table.rowCount()):
                qty_txt = self.table.item(r, 1).text().replace(',', '')
                rate_txt = self.table.item(r, col).text().replace(',', '') if self.table.item(r, col) else ""
                
                try:
                    qty = float(qty_txt) if qty_txt else 0.0
                    rate = float(rate_txt) if rate_txt else 0.0
                    total += qty * rate
                except ValueError:
                    pass
            
            self.summary_table.setItem(0, col, QTableWidgetItem(f"{total:,.2f}"))
            font = self.summary_table.item(0, col).font()
            font.setBold(True)
            self.summary_table.item(0, col).setFont(font)
            self.summary_table.item(0, col).setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

    def _select_winner(self):
        pkg = self.package_combo.currentText()
        if not self.subcontractors:
            QMessageBox.warning(self, "No Subcontractors", "No subcontractors to select.")
            return
            
        winner, ok = QInputDialog.getItem(self, "Select Winner", "Choose winning subcontractor for this package:", self.subcontractors, 0, False)
        if ok and winner:
            col = self.subcontractors.index(winner) + 3
            winning_rates = []
            
            for r in range(self.table.rowCount()):
                rowid = self.items_data[r]['rowid']
                item = self.table.item(r, col)
                rate = item.text().strip() if item else ""
                if rate:
                    winning_rates.append((rowid, rate))
            
            # tell parent to apply this to pboq_items
            if hasattr(self.parent(), 'apply_winning_subcontractor'):
                self.parent().apply_winning_subcontractor(pkg, winner, winning_rates)
                
            self.accept()
