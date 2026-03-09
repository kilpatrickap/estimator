import os
import sqlite3
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QSplitter, 
                             QListWidget, QTableWidget, QTableWidgetItem, 
                             QLabel, QMessageBox, QHeaderView, QListWidgetItem,
                             QLineEdit, QWidget, QCheckBox, QComboBox, QTabWidget,
                             QGroupBox, QFormLayout, QAbstractItemView, QMenu, QPushButton)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QAction
import json

class PBOQDialog(QDialog):
    """Priced Bill of Quantities viewer - Excel-style tabbed view with column mapping."""
    def __init__(self, project_dir, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self.project_dir = project_dir
        self.pboq_folder = os.path.join(self.project_dir, "Priced BOQs")
        self.clipboard_data = None
        
        # Color codes matching BOQ Setup
        self.COLOR_HEADING = QColor("#e8f5e9")
        self.COLOR_ITEM = QColor("#fff9c4")
        self.COLOR_IGNORE = QColor("#ffffff")
        
        self.setWindowTitle("Priced Bills of Quantities (PBOQ)")
        self.setMinimumSize(950, 600)
        
        self._init_ui()
        
        # Auto-load first PBOQ if available
        if self.pboq_file_selector.count() > 0:
            self._load_pboq_db(self.pboq_file_selector.currentIndex())

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # Top bar: PBOQ file selector
        top_bar = QHBoxLayout()
        top_bar.addWidget(QLabel("Select Priced BOQ:"))
        self.pboq_file_selector = QComboBox()
        
        if os.path.exists(self.pboq_folder):
            for f in sorted(os.listdir(self.pboq_folder)):
                if f.lower().endswith('.db'):
                    self.pboq_file_selector.addItem(f, os.path.join(self.pboq_folder, f))
        
        self.pboq_file_selector.activated.connect(self._load_pboq_db)
        top_bar.addWidget(self.pboq_file_selector, stretch=1)
        main_layout.addLayout(top_bar)

        
        # Main splitter: Left (Excel-style table) | Right (Column Mapping + Stats)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(4)
        splitter.setStyleSheet("QSplitter::handle { background-color: #cccccc; border-radius: 2px; }")
        
        # LEFT PANE: Excel-style tabbed table
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        left_layout.addWidget(QLabel("Priced BOQ Data:"))
        
        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.TabPosition.South)
        left_layout.addWidget(self.tabs)
        
        splitter.addWidget(left_widget)
        
        # RIGHT PANE: Column Mapping + Stats + Search
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # Column Mapping Group
        col_group = QGroupBox("Column Mapping")
        col_layout = QFormLayout(col_group)
        col_layout.setContentsMargins(5, 5, 5, 5)
        col_layout.setSpacing(5)
        
        self.cb_ref = QComboBox()
        self.cb_desc = QComboBox()
        self.cb_qty = QComboBox()
        self.cb_unit = QComboBox()
        self.cb_bill_rate = QComboBox()
        self.cb_bill_amount = QComboBox()
        self.cb_rate = QComboBox()
        self.cb_rate_code = QComboBox()
        
        col_layout.addRow("Ref / Item No:", self.cb_ref)
        col_layout.addRow("Description:", self.cb_desc)
        col_layout.addRow("Quantity:", self.cb_qty)
        col_layout.addRow("Unit:", self.cb_unit)
        col_layout.addRow("Bill Rate:", self.cb_bill_rate)
        col_layout.addRow("Bill Amount:", self.cb_bill_amount)
        col_layout.addRow("Gross Rate:", self.cb_rate)
        col_layout.addRow("Rate Code:", self.cb_rate_code)
        
        right_layout.addWidget(col_group)
        
        # Search
        search_group = QGroupBox("Search")
        search_layout = QVBoxLayout(search_group)
        search_layout.setContentsMargins(5, 5, 5, 5)
        search_layout.setSpacing(5)
        
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search across all sheets...")
        self.search_bar.textChanged.connect(self._filter_current_table)
        search_layout.addWidget(self.search_bar)
        
        right_layout.addWidget(search_group)
        
        # Stats
        stats_group = QGroupBox("Statistics")
        stats_layout = QVBoxLayout(stats_group)
        stats_layout.setContentsMargins(5, 5, 5, 5)
        stats_layout.setSpacing(4)
        
        label_style = "font-weight: bold; font-size: 9pt;"
        self.total_items_label = QLabel("Total Items : 0")
        self.total_items_label.setStyleSheet(f"{label_style} color: blue;")
        self.priced_items_label = QLabel("Priced Items : 0")
        self.priced_items_label.setStyleSheet(f"{label_style} color: green;")
        self.outstanding_items_label = QLabel("Outstanding : 0")
        self.outstanding_items_label.setStyleSheet(f"{label_style} color: red;")
        
        stats_layout.addWidget(self.total_items_label)
        stats_layout.addWidget(self.priced_items_label)
        stats_layout.addWidget(self.outstanding_items_label)
        
        right_layout.addWidget(stats_group)
        right_layout.addStretch()
        
        splitter.addWidget(right_widget)
        
        # Give the Excel-style table most of the space
        splitter.setStretchFactor(0, 7)
        splitter.setStretchFactor(1, 3)
        
        main_layout.addWidget(splitter)

    def _load_pboq_db(self, index):
        """Loads a PBOQ .db file and renders it in Excel-style tabs."""
        if index < 0 or index >= self.pboq_file_selector.count():
            return
            
        file_path = self.pboq_file_selector.itemData(index)
        if not file_path or not os.path.exists(file_path):
            return
            
        self.tabs.clear()
        
        from PyQt6.QtWidgets import QApplication, QProgressDialog
        
        conn = None
        try:
            conn = sqlite3.connect(file_path)
            cursor = conn.cursor()
            
            # Check for pboq_items table
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pboq_items';")
            if not cursor.fetchone():
                QMessageBox.warning(self, "Format Error", "This database does not contain valid PBOQ data.")
                return
            
            # Get column info
            cursor.execute("PRAGMA table_info(pboq_items)")
            db_columns = [info[1] for info in cursor.fetchall()]
            
            # Ensure GrossRate and RateCode columns exist in DB
            if "GrossRate" not in db_columns:
                cursor.execute("ALTER TABLE pboq_items ADD COLUMN GrossRate TEXT")
                db_columns.append("GrossRate")
            if "RateCode" not in db_columns:
                cursor.execute("ALTER TABLE pboq_items ADD COLUMN RateCode TEXT")
                db_columns.append("RateCode")
            conn.commit()
            
            # Fetch all data (quote column names since they may contain spaces)
            quoted_cols = [f'"{c}"' for c in db_columns]
            query = f"SELECT {', '.join(quoted_cols)} FROM pboq_items"
            cursor.execute(query)
            rows = cursor.fetchall()
            
            if not rows:
                QMessageBox.information(self, "Empty", "No data found in this PBOQ database.")
                return
            
            # Load formatting data from DB before building tables
            formatting_data = {}
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pboq_formatting';")
            if cursor.fetchone():
                cursor.execute("SELECT row_idx, col_idx, fmt_json FROM pboq_formatting")
                for row_idx, col_idx, fmt_json in cursor.fetchall():
                    formatting_data[(row_idx, col_idx)] = json.loads(fmt_json)
            
        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"Failed to load PBOQ database:\n{e}")
            return
        finally:
            if conn:
                conn.close()
        
        # Store DB column names for persistence
        self.db_columns = db_columns
        
        # The first column is always "Sheet" — the rest are data columns
        display_col_names = db_columns[1:]
        num_display_cols = len(display_col_names)
        
        # Group rows by Sheet name (first column), preserving global row index
        sheet_groups = {}
        for g_idx, row in enumerate(rows):
            sheet_name = str(row[0]) if row[0] else "Sheet 1"
            if sheet_name not in sheet_groups:
                sheet_groups[sheet_name] = []
            sheet_groups[sheet_name].append((g_idx, row[1:]))
        
        # Populate combo boxes with the display column count
        self._populate_column_combos(num_display_cols)
        
        total_items = 0
        priced_items = 0
        
        # Find GrossRate column index in the display columns
        rate_display_idx = display_col_names.index("GrossRate") if "GrossRate" in display_col_names else -1
        qty_mapped = self.cb_qty.currentIndex() - 1
        
        # Progress dialog
        total_rows = len(rows)
        progress = QProgressDialog("Loading PBOQ data...", None, 0, total_rows, self)
        progress.setWindowTitle("Loading")
        progress.setMinimumDuration(0)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setValue(0)
        QApplication.processEvents()
        
        rows_loaded = 0
        
        # Create a tab for each sheet
        for sheet_name, sheet_entries in sheet_groups.items():
            table = QTableWidget()
            table.setRowCount(len(sheet_entries))
            table.setColumnCount(num_display_cols)
            table.setHorizontalHeaderLabels([f"Column {i}" for i in range(num_display_cols)])
            table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
            table.setAlternatingRowColors(True)
            table.setWordWrap(True)
            table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            table.customContextMenuRequested.connect(lambda pos, t=table: self._show_context_menu(pos, t))
            
            for r_idx, (global_row_idx, row_data) in enumerate(sheet_entries):
                for c_idx in range(num_display_cols):
                    col_val = row_data[c_idx] if c_idx < len(row_data) else ""
                    t_item = QTableWidgetItem(str(col_val) if col_val is not None else "")
                    
                    # Apply formatting inline from saved data
                    fmt = formatting_data.get((global_row_idx, c_idx))
                    if fmt:
                        font = t_item.font()
                        if fmt.get('bold'): font.setBold(True)
                        if fmt.get('italic'): font.setItalic(True)
                        if fmt.get('underline'): font.setUnderline(True)
                        t_item.setFont(font)
                        
                        if 'font_color' in fmt:
                            color = QColor(fmt['font_color'])
                            if color.isValid():
                                t_item.setForeground(color)
                        
                        if 'bg_color' in fmt:
                            color = QColor(fmt['bg_color'])
                            if color.isValid():
                                t_item.setBackground(color)
                    
                    table.setItem(r_idx, c_idx, t_item)
                
                # Count stats
                if qty_mapped >= 0 and qty_mapped < len(row_data):
                    qty_val = str(row_data[qty_mapped]).strip() if row_data[qty_mapped] else ""
                    if qty_val and qty_val.lower() not in ('', 'nan', 'none', '<na>'):
                        total_items += 1
                        if rate_display_idx >= 0 and rate_display_idx < len(row_data):
                            rate_val = str(row_data[rate_display_idx]).strip() if row_data[rate_display_idx] else ""
                            if rate_val and rate_val.lower() not in ('', 'none', 'nan'):
                                priced_items += 1
                
                rows_loaded += 1
                if rows_loaded % 100 == 0:
                    progress.setValue(rows_loaded)
                    QApplication.processEvents()
            
            # Auto-size columns
            table.resizeColumnsToContents()
            for c in range(table.columnCount()):
                if table.columnWidth(c) > 400:
                    table.setColumnWidth(c, 400)
            
            # Stretch the Description column if mapped
            desc_mapped = self.cb_desc.currentIndex() - 1
            if desc_mapped >= 0 and desc_mapped < num_display_cols:
                header = table.horizontalHeader()
                header.setSectionResizeMode(desc_mapped, QHeaderView.ResizeMode.Stretch)
            
            self.tabs.addTab(table, sheet_name)
        
        progress.setValue(total_rows)
        
        # Update stats
        outstanding = total_items - priced_items
        self.total_items_label.setText(f"Total Items : {total_items}")
        self.priced_items_label.setText(f"Priced Items : {priced_items}")
        self.outstanding_items_label.setText(f"Outstanding : {outstanding}")

    def _populate_column_combos(self, num_columns):
        """Populates the column mapping combo boxes with generic Column numbers."""
        explicit_columns = [f"Column {i}" for i in range(num_columns)]
        
        for cb in [self.cb_ref, self.cb_desc, self.cb_qty, self.cb_unit, self.cb_bill_rate, self.cb_bill_amount, self.cb_rate, self.cb_rate_code]:
            cb.clear()
            cb.addItem("-- Select Column --")
            cb.addItems(explicit_columns)
        
        # Auto-select defaults based on known PBOQ DB column order
        # db_columns = [Sheet, Column 0, Column 1, ..., GrossRate, RateCode]
        # display_col_names = db_columns[1:] (Sheet is excluded from display)
        db_cols = getattr(self, 'db_columns', [])
        display_cols = db_cols[1:] if len(db_cols) > 1 else []
        
        # Map combo boxes to known DB column names
        col_map = {
            self.cb_rate: "GrossRate",
            self.cb_rate_code: "RateCode"
        }
        for cb, col_name in col_map.items():
            if col_name in display_cols:
                idx = display_cols.index(col_name)
                cb.setCurrentIndex(idx + 1)  # +1 because of "-- Select Column --"

    def _filter_current_table(self, text):
        """Filters rows in the currently visible tab's table."""
        current_table = self.tabs.currentWidget()
        if not isinstance(current_table, QTableWidget):
            return
            
        search_text = text.lower()
        for row in range(current_table.rowCount()):
            row_texts = []
            for col in range(current_table.columnCount()):
                item = current_table.item(row, col)
                if item:
                    row_texts.append(item.text().lower())
            
            full_row_text = " ".join(row_texts)
            current_table.setRowHidden(row, search_text not in full_row_text if search_text else False)

    def _show_context_menu(self, pos, table):
        """Context menu for the table."""
        selected_indexes = table.selectionModel().selectedRows()
        if not selected_indexes:
            return
            
        index = selected_indexes[0]
        row = index.row()
        
        menu = QMenu(self)
        
        # Get current column mapping
        rate_code_col = self.cb_rate_code.currentIndex() - 1
        rate_code = ""
        if rate_code_col >= 0:
            item = table.item(row, rate_code_col)
            rate_code = item.text().strip() if item else ""
        
        # Build/Edit Rate
        action_text = "Edit Rate" if rate_code else "Build Rate"
        build_rate_action = QAction(action_text, self)
        build_rate_action.triggered.connect(lambda: self._build_rate(table, row))
        menu.addAction(build_rate_action)
        
        # Clear Rate
        clear_rate_action = QAction("Clear Rate", self)
        clear_rate_action.triggered.connect(lambda: self._clear_rate(table, row))
        menu.addAction(clear_rate_action)
        
        menu.addSeparator()
        
        # Copy Rate
        copy_action = QAction("Copy Rate", self)
        copy_action.triggered.connect(lambda: self._copy_rate(table, row))
        menu.addAction(copy_action)
        
        # Paste Rate
        paste_action = QAction("Paste Rate", self)
        paste_action.setEnabled(bool(self.clipboard_data))
        paste_action.triggered.connect(lambda: self._paste_rate(table, row))
        menu.addAction(paste_action)
        
        menu.addSeparator()
        
        # Go-To Rate
        goto_rate_action = QAction("Go-To Rate", self)
        goto_rate_action.setEnabled(bool(rate_code))
        goto_rate_action.triggered.connect(lambda: self._goto_project_rates(rate_code))
        menu.addAction(goto_rate_action)
        
        menu.exec(table.viewport().mapToGlobal(pos))

    def _get_mapped_values(self, table, row):
        """Returns a dict of mapped column values for a given row."""
        result = {}
        mappings = {
            'ref': self.cb_ref,
            'desc': self.cb_desc,
            'qty': self.cb_qty,
            'unit': self.cb_unit,
            'rate': self.cb_rate,
            'rate_code': self.cb_rate_code
        }
        for key, cb in mappings.items():
            col = cb.currentIndex() - 1
            if col >= 0:
                item = table.item(row, col)
                result[key] = item.text().strip() if item else ""
            else:
                result[key] = ""
        return result

    def _build_rate(self, table, row):
        """Build or edit a rate for the selected PBOQ item."""
        vals = self._get_mapped_values(table, row)
        desc = vals['desc'] or "New Rate"
        unit = vals['unit'] or "m"
        rate_code = vals['rate_code']
        
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
            QMessageBox.warning(self, "No Project Database", "No Project Database found to build rate into.")
            return
        
        db = DatabaseManager(db_path)
        
        if rate_code:
            from orm_models import DBEstimate
            est_id = None
            with db.Session() as session:
                db_est = session.query(DBEstimate).filter(DBEstimate.rate_code == rate_code).first()
                if db_est:
                    est_id = db_est.id
            if est_id:
                estimate_obj = db.load_estimate_details(est_id)
                if estimate_obj and self.main_window:
                    self.main_window.open_rate_buildup_window(estimate_obj, db_path=db_path)
                return
            else:
                QMessageBox.warning(self, "Not Found", f"Rate '{rate_code}' could not be found in the Project Database.")
                return
        
        cat = "Miscellaneous"
        new_est = Estimate(project_name=desc, client_name="", overhead=15.0, profit=10.0, unit=unit)
        new_est.category = cat
        new_est.rate_code = db.generate_next_rate_code(cat)
        
        def refresh_manager():
            if self.main_window:
                for s in self.main_window.mdi_area.subWindowList():
                    widget = s.widget()
                    if getattr(widget, '__class__', None).__name__ == 'RateManagerDialog':
                        if hasattr(widget, 'load_project_rates'):
                            widget.load_project_rates()
        
        dialog = RateBuildUpDialog(new_est, main_window=self.main_window, parent=self, db_path=db_path)
        dialog.dataCommitted.connect(refresh_manager)
        dialog.exec()
        
        if hasattr(dialog, 'estimate') and dialog.estimate.id:
            totals = dialog.estimate.calculate_totals()
            gross_rate = totals.get('grand_total', 0.0)
            formatted_gross = f"{gross_rate:,.2f}"
            
            # Update table cells using mapped columns
            rate_col = self.cb_rate.currentIndex() - 1
            rate_code_col = self.cb_rate_code.currentIndex() - 1
            
            if rate_col >= 0:
                gross_item = QTableWidgetItem(formatted_gross)
                gross_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                table.setItem(row, rate_col, gross_item)
            
            if rate_code_col >= 0:
                table.setItem(row, rate_code_col, QTableWidgetItem(str(dialog.estimate.rate_code)))
            
            # Persist to PBOQ DB
            self._persist_to_pboq_db(table, row, formatted_gross, str(dialog.estimate.rate_code))
            self._update_stats()

    def _copy_rate(self, table, row):
        vals = self._get_mapped_values(table, row)
        self.clipboard_data = {
            'gross_rate': vals['rate'],
            'rate_code': vals['rate_code'],
            'unit': vals['unit']
        }
        if self.main_window:
            self.main_window.statusBar().showMessage(f"Rate {vals['rate_code']} copied to clipboard.", 3000)

    def _paste_rate(self, table, row):
        if not self.clipboard_data:
            return
            
        vals = self._get_mapped_values(table, row)
        target_unit = vals['unit']
        data = self.clipboard_data if isinstance(self.clipboard_data, dict) else self.clipboard_data[0]
        
        if data['unit'].strip().lower() != target_unit.lower():
            QMessageBox.warning(self, "Unit Mismatch",
                                f"Cannot paste rate. Units do not match!\n\n"
                                f"Source: {data['unit']}\nTarget: {target_unit}")
            return
        
        rate_col = self.cb_rate.currentIndex() - 1
        rate_code_col = self.cb_rate_code.currentIndex() - 1
        
        if rate_col >= 0:
            gross_item = QTableWidgetItem(data['gross_rate'])
            gross_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            table.setItem(row, rate_col, gross_item)
        
        if rate_code_col >= 0:
            table.setItem(row, rate_code_col, QTableWidgetItem(data['rate_code']))
        
        self._persist_to_pboq_db(table, row, data['gross_rate'], data['rate_code'])
        self._update_stats()
        
        if self.main_window:
            self.main_window.statusBar().showMessage("Rate pasted and persisted to PBOQ database.", 3000)

    def _clear_rate(self, table, row):
        desc_col = self.cb_desc.currentIndex() - 1
        desc = table.item(row, desc_col).text() if desc_col >= 0 and table.item(row, desc_col) else "this item"
        
        reply = QMessageBox.question(self, "Clear Rate",
                                   f"Are you sure you want to clear the Gross Rate and Rate Code for:\n\n{desc}?",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                   QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            rate_col = self.cb_rate.currentIndex() - 1
            rate_code_col = self.cb_rate_code.currentIndex() - 1
            
            if rate_col >= 0:
                table.setItem(row, rate_col, QTableWidgetItem(""))
            if rate_code_col >= 0:
                table.setItem(row, rate_code_col, QTableWidgetItem(""))
            
            self._persist_to_pboq_db(table, row, "", "")
            self._update_stats()
            
            if self.main_window:
                self.main_window.statusBar().showMessage("Rate cleared and persisted to PBOQ database.", 3000)

    def _goto_project_rates(self, rate_code):
        if self.main_window and rate_code:
            self.main_window.show_rate_in_database(rate_code)

    def _persist_to_pboq_db(self, table, row, gross_rate, rate_code):
        """Persists the Gross Rate and Rate Code back to the PBOQ SQLite database."""
        file_path = self.pboq_file_selector.currentData()
        if not file_path or not os.path.exists(file_path):
            return
        
        # Get the sheet name from the current tab
        current_tab_idx = self.tabs.indexOf(table)
        sheet_name = self.tabs.tabText(current_tab_idx) if current_tab_idx >= 0 else ""
        
        # Get the DB column names (db_columns[1:] = display columns)
        db_cols = getattr(self, 'db_columns', [])
        display_cols = db_cols[1:] if len(db_cols) > 1 else []
        
        try:
            conn = sqlite3.connect(file_path)
            cursor = conn.cursor()
            
            # Ensure columns exist
            cursor.execute("PRAGMA table_info(pboq_items)")
            cols = [info[1] for info in cursor.fetchall()]
            
            if "GrossRate" not in cols:
                cursor.execute("ALTER TABLE pboq_items ADD COLUMN GrossRate TEXT")
            if "RateCode" not in cols:
                cursor.execute("ALTER TABLE pboq_items ADD COLUMN RateCode TEXT")
            
            # Build WHERE clause using Sheet + all data columns (excluding GrossRate and RateCode)
            where_parts = ["Sheet = ?"]
            where_values = [sheet_name]
            
            for c_idx, col_name in enumerate(display_cols):
                if col_name in ("GrossRate", "RateCode"):
                    continue
                item = table.item(row, c_idx)
                val = item.text() if item else ""
                where_parts.append(f'"{col_name}" = ?')
                where_values.append(val)
            
            where_clause = " AND ".join(where_parts)
            
            cursor.execute(f"""
                UPDATE pboq_items 
                SET GrossRate = ?, RateCode = ? 
                WHERE {where_clause}
            """, [gross_rate, rate_code] + where_values)
            
            conn.commit()
            conn.close()
        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"Failed to persist PBOQ data:\n{e}")

    def _update_stats(self):
        """Recalculates the priced/outstanding stats across all tabs."""
        total_items = 0
        priced_items = 0
        
        rate_col = self.cb_rate.currentIndex() - 1
        qty_col = self.cb_qty.currentIndex() - 1
        
        for tab_idx in range(self.tabs.count()):
            table = self.tabs.widget(tab_idx)
            if not isinstance(table, QTableWidget):
                continue
                
            for row in range(table.rowCount()):
                # Only count items that have a quantity (not headings)
                if qty_col >= 0:
                    qty_item = table.item(row, qty_col)
                    qty_val = qty_item.text().strip() if qty_item else ""
                    if not qty_val or qty_val.lower() in ('', 'nan', 'none', '<na>'):
                        continue
                
                total_items += 1
                
                if rate_col >= 0:
                    rate_item = table.item(row, rate_col)
                    rate_val = rate_item.text().strip() if rate_item else ""
                    if rate_val and rate_val.lower() not in ('', 'none', 'nan'):
                        priced_items += 1
        
        outstanding = total_items - priced_items
        self.total_items_label.setText(f"Total Items : {total_items}")
        self.priced_items_label.setText(f"Priced Items : {priced_items}")
        self.outstanding_items_label.setText(f"Outstanding : {outstanding}")
