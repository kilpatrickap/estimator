import sqlite3
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, 
                             QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
                             QMessageBox, QInputDialog, QAbstractItemView, QCheckBox, 
                             QFileDialog, QRadioButton, QLineEdit, QGroupBox)
import os
import shutil
from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtGui import QColor, QBrush

# Number of fixed (read-only) base columns: Ref, Description, Qty, Unit, Ref Rate
BASE_COL_COUNT = 5

# Colors for comparison highlighting
COLOR_LOWEST = QColor("#c8e6c9")   # Light green — best rate
COLOR_HIGHEST = QColor("#ffcdd2")  # Light red — worst rate
COLOR_MIDDLE = QColor("#fff9c4")   # Light yellow — middle rate
COLOR_TOTAL_BEST = QColor("#2E7D32")  # Dark green text for lowest total
COLOR_BASE_COL = QColor("#e3f2fd")    # Very Light Blue for base columns
COLOR_PRICE_COL = QColor("#ffe0b2")   # Light Orange for Rate columns
COLOR_AMOUNT_COL = QColor("#e1bee7")  # Light Violet for Amount columns


class AddSubcontractorDialog(QDialog):
    """Wizard for adding a subcontractor, optionally managing RFQ Excel file imports."""
    def __init__(self, project_dir, pkg_name, parent=None):
        super().__init__(parent)
        self.project_dir = project_dir
        self.pkg_name = pkg_name
        self.safe_pkg = pkg_name.replace('/', '_').replace('\\', '_')
        self.selected_file_path = ""
        self.setWindowTitle("New Subcontractor Wizard")
        self.resize(500, 300)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        
        # Subcontractor Name
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Subcontractor Name:"))
        self.name_input = QLineEdit()
        self.name_input.textChanged.connect(self._on_name_changed)
        name_layout.addWidget(self.name_input)
        layout.addLayout(name_layout)
        
        # Import Options
        self.import_group = QGroupBox("Import Options")
        ig_layout = QVBoxLayout(self.import_group)
        
        self.radio_manual = QRadioButton("Manual Entry (Add blank column)")
        self.radio_manual.setChecked(True)
        self.radio_manual.toggled.connect(self._toggle_ui)
        ig_layout.addWidget(self.radio_manual)
        
        self.radio_new_file = QRadioButton("Import New Excel RFQ...")
        self.radio_new_file.toggled.connect(self._toggle_ui)
        ig_layout.addWidget(self.radio_new_file)
        
        # Browse UI
        self.browse_layout = QHBoxLayout()
        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.clicked.connect(self._browse_file)
        self.browse_btn.setEnabled(False)
        self.browse_layout.addWidget(self.browse_btn)
        
        self.file_lbl = QLabel("No file selected")
        self.file_lbl.setStyleSheet("color: gray; font-style: italic;")
        self.browse_layout.addWidget(self.file_lbl)
        ig_layout.addLayout(self.browse_layout)
        
        self.radio_existing = QRadioButton("Import Existing Received RFQ")
        self.radio_existing.toggled.connect(self._toggle_ui)
        ig_layout.addWidget(self.radio_existing)
        
        # Dropdown UI
        self.existing_combo = QComboBox()
        self.existing_combo.setEnabled(False)
        ig_layout.addWidget(self.existing_combo)
        
        layout.addWidget(self.import_group)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.ok_btn = QPushButton("OK")
        self.ok_btn.clicked.connect(self.accept)
        self.ok_btn.setEnabled(False) # Require name
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(self.ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def _on_name_changed(self, text):
        self.ok_btn.setEnabled(bool(text.strip()))
        self._refresh_existing_dropdown()

    def _toggle_ui(self):
        self.browse_btn.setEnabled(self.radio_new_file.isChecked())
        self.existing_combo.setEnabled(self.radio_existing.isChecked())
        if self.radio_existing.isChecked() and self.existing_combo.count() == 0:
            # If they checked existing but none exist, warn them
            self.file_lbl.setText("No existing files found for this subbee.")

    def _browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Priced RFQ", "", "Excel Files (*.xlsx *.xls)")
        if file_path:
            self.selected_file_path = file_path
            self.file_lbl.setText(os.path.basename(file_path))
            self.file_lbl.setStyleSheet("color: black;")

    def _refresh_existing_dropdown(self):
        self.existing_combo.clear()
        name = self.name_input.text().strip()
        if not name: return
        
        safe_name = name.replace('/', '_').replace('\\', '_')
        target_dir = os.path.join(self.project_dir, "Received RFQs", self.safe_pkg, safe_name)
        
        if os.path.exists(target_dir):
            files = [f for f in os.listdir(target_dir) if f.endswith(('.xlsx', '.xls'))]
            for f in sorted(files, reverse=True): # Newest first typically
                self.existing_combo.addItem(f, os.path.join(target_dir, f))
                
        if self.existing_combo.count() > 0:
            self.radio_existing.setEnabled(True)
        else:
            self.radio_existing.setEnabled(False)
            if self.radio_existing.isChecked():
                self.radio_manual.setChecked(True)

    def get_result(self):
        name = self.name_input.text().strip()
        if self.radio_manual.isChecked():
            return name, "MANUAL", None
        elif self.radio_new_file.isChecked():
            return name, "NEW", self.selected_file_path
        elif self.radio_existing.isChecked():
            return name, "EXISTING", self.existing_combo.currentData()
        return name, "MANUAL", None

class PackageAdjudicatorDialog(QDialog):
    def __init__(self, pboq_db_path, pkg_db_col, project_dir, parent=None):
        super().__init__(parent)
        self.pboq_db_path = pboq_db_path
        self.pkg_db_col = pkg_db_col
        self.project_dir = project_dir
        self.setWindowTitle("Subcontractor Package Adjudicator")
        self.resize(1250, 680)
        self.setMinimumSize(900, 500)
        self._init_ui()
        
        self.settings = QSettings("Consar", "EstimatorSubAdjudicator")
        self._load_state()
        
        self._load_packages()
        
        # Restore last selected package if it exists
        last_pkg = self.settings.value("selected_package", "")
        if last_pkg:
            idx = self.package_combo.findText(last_pkg)
            if idx >= 0:
                self.package_combo.setCurrentIndex(idx)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8) # Tighter margins
        layout.setSpacing(6)                  # Tighter spacing
        # Top Bar
        top_bar = QHBoxLayout()
        
        # Left side: combo and checkbox
        left_vbox = QVBoxLayout()
        
        combo_hbox = QHBoxLayout()
        combo_hbox.addWidget(QLabel("Select Work Package:"))
        self.package_combo = QComboBox()
        self.package_combo.setMinimumWidth(200)
        self.package_combo.currentIndexChanged.connect(self._on_package_selected)
        combo_hbox.addWidget(self.package_combo)
        left_vbox.addLayout(combo_hbox)
        
        self.toggle_amounts_cb = QCheckBox("Toggle Amounts")
        self.toggle_amounts_cb.setChecked(False)
        self.toggle_amounts_cb.stateChanged.connect(self._on_toggle_amounts)
        left_vbox.addWidget(self.toggle_amounts_cb)
        
        top_bar.addLayout(left_vbox)
        top_bar.addStretch()
        
        self.add_subbee_btn = QPushButton("Add Subcontractor")
        self.add_subbee_btn.clicked.connect(self._add_subcontractor)
        top_bar.addWidget(self.add_subbee_btn)

        self.remove_subbee_btn = QPushButton("Remove Subcontractor")
        self.remove_subbee_btn.clicked.connect(self._remove_subcontractor)
        top_bar.addWidget(self.remove_subbee_btn)
        
        # Add Excel IO Buttons
        self.export_rfq_btn = QPushButton("Export RFQ Template (Excel)")
        self.export_rfq_btn.clicked.connect(self._export_rfq)
        top_bar.addWidget(self.export_rfq_btn)

        
        layout.addLayout(top_bar)

        # Main Table
        self.table = QTableWidget()
        self.table.setColumnCount(BASE_COL_COUNT)
        self.table.setHorizontalHeaderLabels(["Ref/Item", "Description", "Qty", "Unit", "Est. Rate"])
        
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
        self.summary_table.setItem(0, 3, lbl_item) # Col 3 (Unit)

        # Fill remaining base cells
        for c in [0, 2, 4]: # Ref, Qty, and Ref Rate columns are empty in summary for now
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
        self.items_data = []      # list of dicts: rowid, ref, desc, qty, unit, bill_rate
        self.subcontractors = []  # list of names
        self.current_winner_name = ""

    def _sync_table_widths(self):
        # Match vertical header width (row numbers)
        self.summary_table.verticalHeader().setFixedWidth(self.table.verticalHeader().width())
        for i in range(self.table.columnCount()):
            self.summary_table.setColumnWidth(i, self.table.columnWidth(i))

    def _on_section_resized(self, logicalIndex, oldSize, newSize):
        """Keep summary table perfectly aligned when user drags headers."""
        self.summary_table.setColumnWidth(logicalIndex, newSize)

    def _on_toggle_amounts(self, state):
        self._apply_toggle_amounts()
        self._sync_table_widths()

    def _apply_toggle_amounts(self):
        show_amounts = self.toggle_amounts_cb.isChecked()
        for s_idx in range(len(self.subcontractors)):
            amt_col = BASE_COL_COUNT + (s_idx * 2) + 1
            self.table.setColumnHidden(amt_col, not show_amounts)
            self.summary_table.setColumnHidden(amt_col, not show_amounts)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._sync_table_widths()

    # ── State Persistence ─────────────────────────────────────────

    def _save_state(self):
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("show_amounts", self.toggle_amounts_cb.isChecked())
        if self.package_combo.currentText() != "-- Select Package --":
            self.settings.setValue("selected_package", self.package_combo.currentText())
        else:
            self.settings.setValue("selected_package", "")

    def _load_state(self):
        geom = self.settings.value("geometry")
        if geom:
            self.restoreGeometry(geom)
            
        show_amounts = self.settings.value("show_amounts", False, type=bool)
        # block signals briefly to avoid premature UI updates before packages load
        self.toggle_amounts_cb.blockSignals(True)
        self.toggle_amounts_cb.setChecked(show_amounts)
        self.toggle_amounts_cb.blockSignals(False)

    def closeEvent(self, event):
        self._save_state()
        super().closeEvent(event)

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

    # ── Table Construction ────────────────────────────────────────

    def _build_table(self, quotes):
        self.table.blockSignals(True)
        self.table.setRowCount(len(self.items_data))
        self._update_headers()
        
        for r, d in enumerate(self.items_data):
            self.table.setItem(r, 0, QTableWidgetItem(str(d.get('ref', ''))))
            self.table.setItem(r, 1, QTableWidgetItem(str(d.get('desc', ''))))
            self.table.setItem(r, 2, QTableWidgetItem(str(d.get('qty', ''))))
            self.table.setItem(r, 3, QTableWidgetItem(str(d.get('unit', ''))))
            
            # Apply light blue to base columns
            for c in range(4):
                item = self.table.item(r, c)
                if item:
                    item.setBackground(QBrush(COLOR_BASE_COL))
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)

            rate_val = d.get('bill_rate', '')
            try:
                rate_float = float(rate_val.replace(',', '')) if rate_val else 0.0
                rate_str = f"{rate_float:,.2f}" if rate_float != 0 else ""
            except:
                rate_str = str(rate_val)
            
            ref_rate_item = QTableWidgetItem(rate_str)
            ref_rate_item.setBackground(QBrush(COLOR_PRICE_COL))
            self.table.setItem(r, 4, ref_rate_item)
            ref_rate_item.setFlags(ref_rate_item.flags() & ~Qt.ItemFlag.ItemIsEditable)

            # Fill quotes and empty amounts
            rid = d.get('rowid')
            for s_idx, sub in enumerate(self.subcontractors):
                col = BASE_COL_COUNT + (s_idx * 2)
                amt_col = col + 1
                rate = quotes.get(sub, {}).get(rid, "")
                
                rate_item = QTableWidgetItem(f"{rate:,.2f}" if rate else "")
                rate_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                rate_item.setBackground(QBrush(COLOR_PRICE_COL)) # Same consistency color
                self.table.setItem(r, col, rate_item)
                    
                # Setup Amount Cell
                amt_item = QTableWidgetItem("")
                amt_item.setFlags(amt_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                amt_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                amt_item.setBackground(QBrush(COLOR_AMOUNT_COL)) # Light Violet
                self.table.setItem(r, amt_col, amt_item)
        
        self.table.blockSignals(False)
        self._calculate_totals()
        self._apply_comparison_colors()

    def _update_headers(self):
        base = ["Ref/Item", "Description", "Qty", "Unit", "Ref Rate (Bill)"]
        total_cols = BASE_COL_COUNT + (len(self.subcontractors) * 2)
        self.table.setColumnCount(total_cols)
        self.summary_table.setColumnCount(total_cols)
        
        headers = base.copy()
        for sub in self.subcontractors:
            headers.append(f"{sub}")
            headers.append("Amount")
            
        self.table.setHorizontalHeaderLabels(headers)
        
        # Initial sizing - tightened for 768p efficiency
        self.table.setColumnWidth(0, 60)  # Ref/Item
        self.table.setColumnWidth(1, 400) # Description (keep wide)
        self.table.setColumnWidth(2, 60)  # Qty
        self.table.setColumnWidth(3, 50)  # Unit
        self.table.setColumnWidth(4, 100) # Ref Rate
        
        for s_idx in range(len(self.subcontractors)):
            amt_col = BASE_COL_COUNT + (s_idx * 2) + 1
            self.table.setColumnWidth(amt_col, 100) # Give amount columns width
            
        self._sync_table_widths()
        self._apply_toggle_amounts()

    # ── Subcontractor Management ──────────────────────────────────

    def _add_subcontractor(self):
        pkg = self.package_combo.currentText()
        if pkg == "-- Select Package --" or not pkg:
            QMessageBox.warning(self, "No Package", "Please select a work package first.")
            return

        wizard = AddSubcontractorDialog(self.project_dir, pkg, self)
        if wizard.exec() == QDialog.DialogCode.Accepted:
            name, import_type, file_path = wizard.get_result()
            if not name: return

            if name in self.subcontractors:
                QMessageBox.warning(self, "Duplicate", f"Subcontractor '{name}' already exists.")
                return

            # Handle DMS Import Logic
            if import_type in ("NEW", "EXISTING") and file_path:
                if import_type == "NEW":
                    # Copy to DMS structure
                    safe_pkg = pkg.replace('/', '_').replace('\\', '_')
                    safe_sub = name.replace('/', '_').replace('\\', '_')
                    boq_name = os.path.splitext(os.path.basename(self.pboq_db_path))[0]
                    safe_boq = boq_name.replace('/', '_').replace('\\', '_')
                    
                    target_dir = os.path.join(self.project_dir, "Received RFQs", safe_pkg, safe_sub)
                    os.makedirs(target_dir, exist_ok=True)
                    
                    # Generate filename with timestamp or revision to avoid overwrite if multiple
                    import datetime
                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    new_filename = f"{safe_boq}_Received_RFQ_{safe_pkg}_{safe_sub}_{timestamp}.xlsx"
                    dms_filepath = os.path.join(target_dir, new_filename)
                    
                    try:
                        shutil.copy2(file_path, dms_filepath)
                        file_path_to_import = dms_filepath # Use the new safe copy
                    except Exception as e:
                        QMessageBox.critical(self, "Copy Error", f"Failed to save file to project DMS:\n{e}")
                        return
                else:
                    file_path_to_import = file_path # Already in DMS

                # Execute Import
                try:
                    from subcontractor_io import SubcontractorIO
                    updates = SubcontractorIO.import_rfq(self.pboq_db_path, pkg, file_path_to_import, name)
                    if updates > 0:
                        QMessageBox.information(self, "Import Successful", 
                                              f"Successfully imported {updates} rates from '{name}'.")
                    else:
                        QMessageBox.information(self, "No Quotes", "No valid quotes found in file.")
                except Exception as e:
                    QMessageBox.critical(self, "Import Error", f"Failed to parse RFQ:\n{e}")
                    # Even if import failed, we continue to add the name column

            # Add manual/imported subbee column
            self.subcontractors.append(name)
            self._update_headers()
            
            # Rebuild view data to include newly imported quotes AND the new column
            if import_type in ("NEW", "EXISTING"):
                self._on_package_selected() # This handles full DB reload for imports
            else:
                # Manual entry: just add the visual column since it's not in DB yet
                self.table.blockSignals(True)
                col = BASE_COL_COUNT + ((len(self.subcontractors) - 1) * 2)
                amt_col = col + 1
                for r in range(self.table.rowCount()):
                    rate_item = QTableWidgetItem("")
                    rate_item.setBackground(QBrush(COLOR_PRICE_COL))
                    self.table.setItem(r, col, rate_item)
                    
                    amt_item = QTableWidgetItem("")
                    amt_item.setFlags(amt_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    amt_item.setBackground(QBrush(COLOR_AMOUNT_COL)) # Light Violet
                    self.table.setItem(r, amt_col, amt_item)
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

    # ── Excel RFQ Import/Export ──────────────────────────────────
    
    def _export_rfq(self):
        pkg = self.package_combo.currentText()
        if pkg == "-- Select Package --" or not pkg:
            QMessageBox.warning(self, "Select Package", "Please select a work package to export.")
            return

        # Grab the FULL structured PBOQ just for export
        if hasattr(self.parent(), 'get_full_pboq_for_export'):
            full_export_data = self.parent().get_full_pboq_for_export(pkg)
        else:
            QMessageBox.critical(self, "Export Error", "Parent viewer does not support full export.")
            return

        if not full_export_data:
            QMessageBox.warning(self, "Empty Export", "No data available to export.")
            return

        # Extract the BOQ name from the database path (e.g., "Bill A.db" -> "Bill A")
        boq_name = os.path.splitext(os.path.basename(self.pboq_db_path))[0]
        safe_boq_name = boq_name.replace('/', '_').replace('\\', '_')
        safe_pkg_name = pkg.replace('/', '_').replace('\\', '_')
        
        # Automatically construct the target path: project_dir/RFQs/[Package Name]/[BOQ Name]_RFQ_[Package Name].xlsx
        rfq_base_folder = os.path.join(self.project_dir, "RFQs")
        pkg_folder = os.path.join(rfq_base_folder, safe_pkg_name)
        
        try:
            os.makedirs(pkg_folder, exist_ok=True)
            file_path = os.path.join(pkg_folder, f"{safe_boq_name}_RFQ_{safe_pkg_name}.xlsx")
            
            from subcontractor_io import SubcontractorIO
            SubcontractorIO.export_rfq(self.pboq_db_path, pkg, file_path, full_export_data)
            
            if hasattr(self.parent(), 'main_window') and hasattr(self.parent().main_window, 'statusBar'):
                self.parent().main_window.statusBar().showMessage(f"Target RFQ exported: {file_path}", 4000)
            
            reply = QMessageBox.information(self, "Export Successful", 
                                         f"RFQ Template generated successfully at:\n{file_path}\n\nWould you like to open the folder?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                import subprocess
                if os.name == 'nt':
                    # /select, flag opens the folder AND highlights the specific file
                    subprocess.run(['explorer', '/select,', os.path.normpath(file_path)])
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to generate Excel RFQ:\n{e}")

    # ── Quote Editing & Persistence ───────────────────────────────

    def _on_item_changed(self, item):
        col = item.column()
        # Verify it's a rate column and not an amount column
        if col >= BASE_COL_COUNT and (col - BASE_COL_COUNT) % 2 == 0:
            self._save_quote(item)
            
            # Format to 2 decimal places with commas
            txt = item.text().replace(',', '')
            try:
                val = float(txt)
                self.table.blockSignals(True)
                item.setText(f"{val:,.2f}")
                item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                self.table.blockSignals(False)
            except ValueError:
                pass

            self._calculate_totals()
            self._apply_comparison_colors()

    def _save_quote(self, item):
        r = item.row()
        c = item.column()
        s_idx = (c - BASE_COL_COUNT) // 2
        sub_name = self.subcontractors[s_idx]
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

        rate_totals = []
        amount_totals = []
        ref_amt_total = 0.0
        
        for r in range(self.table.rowCount()):
            qty_item = self.table.item(r, 2)
            ref_rate_item = self.table.item(r, 4)
            qty = clean_float(qty_item.text()) if qty_item else 0.0
            ref_rate = clean_float(ref_rate_item.text()) if ref_rate_item else 0.0
            ref_amt_total += (qty * ref_rate)

        # Set summary background colors for base and pricing columns
        for c in range(4):
            it = self.summary_table.item(0, c)
            if it: it.setBackground(QBrush(COLOR_BASE_COL))
            
        for c in range(4, self.summary_table.columnCount()):
            itp = self.summary_table.item(0, c)
            if itp: itp.setBackground(QBrush(COLOR_PRICE_COL))

        # Place Ref Total in column 4 (under Ref Rate) if desired, or just use it in the winner label
        if ref_amt_total > 0:
            it = self.summary_table.item(0, 4)
            if it:
                it.setText(f"{ref_amt_total:,.2f}")
                it.setForeground(QColor("#78909c")) # Slate gray
                font = it.font()
                font.setBold(True)
                it.setFont(font)
                it.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        for s_idx, sub_name in enumerate(self.subcontractors):
            col = BASE_COL_COUNT + (s_idx * 2)
            amt_col = col + 1
            r_total = 0.0
            a_total = 0.0
            
            for r in range(self.table.rowCount()):
                qty_item = self.table.item(r, 2)
                rate_item = self.table.item(r, col)
                
                qty = clean_float(qty_item.text()) if qty_item else 0.0
                rate = clean_float(rate_item.text()) if rate_item else 0.0
                row_total = qty * rate
                
                r_total += rate
                a_total += row_total
                
                # Dynamically update the amount cell
                amt_item = self.table.item(r, amt_col)
                if amt_item:
                    if row_total > 0:
                        amt_item.setText(f"{row_total:,.2f}")
                    else:
                        amt_item.setText("")
                        
            rate_totals.append(r_total)
            amount_totals.append(a_total)
            
            # Place the Rate total
            r_item = QTableWidgetItem(f"{r_total:,.2f}")
            font = r_item.font()
            font.setBold(True)
            r_item.setFont(font)
            r_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            r_item.setFlags(r_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.summary_table.setItem(0, col, r_item)
            
            # Place the Amount total
            a_item = QTableWidgetItem(f"{a_total:,.2f}")
            a_item.setFont(font)
            a_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            a_item.setFlags(a_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.summary_table.setItem(0, amt_col, a_item)

        # Identify and display the dynamic winner based on AMOUNT
        self.current_winner_name = ""
        if len(amount_totals) > 0:
            non_zero = [t for t in amount_totals if t > 0]
            if non_zero:
                min_total = min(non_zero)
                for s_idx, total in enumerate(amount_totals):
                    col = BASE_COL_COUNT + (s_idx * 2)
                    amt_col = col + 1
                    r_item = self.summary_table.item(0, col)
                    a_item = self.summary_table.item(0, amt_col)
                    
                    if total == min_total and total > 0:
                        if r_item: r_item.setForeground(COLOR_TOTAL_BEST)
                        if a_item: a_item.setForeground(COLOR_TOTAL_BEST)
                        self.current_winner_name = self.subcontractors[s_idx]
                    else:
                        if r_item: r_item.setForeground(Qt.GlobalColor.black)
                        if a_item: a_item.setForeground(Qt.GlobalColor.black)
        
        # Update summary label dynamically
        it = self.summary_table.item(0, 1)
        if it:
            if self.current_winner_name:
                it.setText(f"WINNER: {self.current_winner_name.upper()}")
            else:
                it.setText("WINNER: [NONE SELECTED]")

        # --- Calculate and show comparison stats ---
        if len(self.subcontractors) > 0 and it:
            valid_totals = [t for t in amount_totals if t > 0]
            if valid_totals:
                # 1. Average Quote
                if len(valid_totals) > 1:
                    avg_total = sum(valid_totals) / len(valid_totals)
                    it.setText(f"{it.text()}  |  AVG: {avg_total:,.2f}")
                
                # 2. Saving compared to Estimated Budget
                if ref_amt_total > 0:
                    min_total = min(valid_totals)
                    saving = ref_amt_total - min_total
                    saving_pct = (saving / ref_amt_total) * 100
                    it.setText(f"{it.text()}  |  SAVING: {saving:,.2f} ({saving_pct:,.1f}%)")

    def _apply_comparison_colors(self):
        """Color-code the lowest rate per row (green) and highest (red)."""
        if len(self.subcontractors) < 2:
            return

        for r in range(self.table.rowCount()):
            rates = []
            for s_idx in range(len(self.subcontractors)):
                col = BASE_COL_COUNT + (s_idx * 2)
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
                # Clear any prior coloring if not enough to compare (+ keep consistency color)
                for s_idx in range(len(self.subcontractors)):
                    col = BASE_COL_COUNT + (s_idx * 2)
                    item = self.table.item(r, col)
                    if item:
                        item.setBackground(QBrush(COLOR_PRICE_COL))
                continue

            min_rate = min(valid_rates)
            max_rate = max(valid_rates)

            self.table.blockSignals(True)
            for s_idx in range(len(self.subcontractors)):
                col = BASE_COL_COUNT + (s_idx * 2)
                item = self.table.item(r, col)
                if not item:
                    continue
                val = rates[s_idx]
                if val is None or val == 0:
                    item.setBackground(QBrush(COLOR_PRICE_COL))
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
            
        # Default to the lowest bidder (identified in self.current_winner_name)
        default_idx = 0
        if self.current_winner_name in self.subcontractors:
            default_idx = self.subcontractors.index(self.current_winner_name)
            
        winner, ok = QInputDialog.getItem(self, "Select Winner", "Choose winning subcontractor for this package:", self.subcontractors, default_idx, False)
        if ok and winner:
            col = BASE_COL_COUNT + (self.subcontractors.index(winner) * 2)
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
