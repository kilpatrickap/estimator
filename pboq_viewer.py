import os
import sqlite3
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QSplitter, 
                             QListWidget, QTableWidget, QTableWidgetItem, 
                             QLabel, QMessageBox, QHeaderView, QListWidgetItem,
                             QLineEdit, QWidget, QCheckBox, QComboBox, QTabWidget,
                             QGroupBox, QFormLayout, QAbstractItemView, QMenu, QPushButton, QDoubleSpinBox)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QAction, QBrush

import json

class PBOQDialog(QDialog):
    """Priced Bill of Quantities viewer - Excel-style tabbed view with column mapping."""
    def __init__(self, project_dir, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self.project_dir = project_dir
        self.pboq_folder = os.path.join(self.project_dir, "Priced BOQs")
        self.clipboard_data = None
        self.wrap_text_enabled = False
        
        # Color codes matching BOQ Setup
        self.COLOR_HEADING = QColor("#e8f5e9")
        self.COLOR_ITEM = QColor("#fff9c4")
        self.COLOR_IGNORE = QColor("#ffffff")
        
        # Column identifying colors (Soft pastels for high readability)
        self.COL_COLOR_BLUE = QColor("#e3f2fd")
        self.COL_COLOR_YELLOW = QColor("#fff9c4")
        self.COL_COLOR_RED = QColor("#ffebee")
        self.linking_source = None # Stores (table, item, original_bg)
        self.active_links = {}     # source_rowid -> list of dest_rowids
        self.is_syncing_links = False


        
        self.setWindowTitle("Priced Bills of Quantities (PBOQ)")
        self.setMinimumSize(950, 600)
        
        self._init_ui()
        
        # Restore last selected bill if available
        last_bill = self._load_viewer_state()
        if last_bill:
            index = self.pboq_file_selector.findText(last_bill)
            if index >= 0:
                self.pboq_file_selector.blockSignals(True)
                self.pboq_file_selector.setCurrentIndex(index)
                self.pboq_file_selector.blockSignals(False)
        
        # Auto-load selected PBOQ if available
        if self.pboq_file_selector.count() > 0:
            self._load_pboq_db(self.pboq_file_selector.currentIndex())

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 5, 10, 10)
        
        # Top bar: PBOQ file selector + Search + Stats
        top_bar = QHBoxLayout()
        top_bar.setSpacing(15)
        
        # 1. File Selector Group
        self.pboq_sel_group = QGroupBox("Select Priced BOQ")
        self.pboq_sel_group.setFixedHeight(55)
        file_sel_layout = QVBoxLayout(self.pboq_sel_group)
        file_sel_layout.setContentsMargins(5, 8, 5, 2)
        
        self.pboq_file_selector = QComboBox()
        self.pboq_file_selector.setMaximumWidth(250)
        
        if os.path.exists(self.pboq_folder):
            for f in sorted(os.listdir(self.pboq_folder)):
                if f.lower().endswith('.db'):
                    self.pboq_file_selector.addItem(f, os.path.join(self.pboq_folder, f))
        
        self.pboq_file_selector.activated.connect(self._load_pboq_db)
        file_sel_layout.addWidget(self.pboq_file_selector)
        top_bar.addWidget(self.pboq_sel_group)
        
        # 2. Search Group (Moved to top)
        self.search_group = QGroupBox("Search")
        self.search_group.setFixedHeight(55)
        search_layout = QHBoxLayout(self.search_group)
        search_layout.setContentsMargins(10, 8, 10, 2)
        search_layout.setSpacing(10)
        
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Type to search...")
        self.search_bar.setMinimumWidth(200)
        self.search_bar.textChanged.connect(self._filter_tables)
        search_layout.addWidget(self.search_bar)
        
        scope_layout = QHBoxLayout()
        self.search_this_sheet = QCheckBox("This Sheet")
        self.search_this_sheet.setChecked(True)
        self.search_all_sheets = QCheckBox("All Sheets")
        self.search_all_sheets.setChecked(False)
        
        self.search_this_sheet.toggled.connect(lambda checked: self.search_all_sheets.setChecked(not checked) if checked else None)
        self.search_all_sheets.toggled.connect(lambda checked: self.search_this_sheet.setChecked(not checked) if checked else None)
        self.search_this_sheet.toggled.connect(lambda: self._filter_tables(self.search_bar.text()))
        self.search_this_sheet.toggled.connect(self._save_pboq_state)
        
        scope_layout.addWidget(self.search_this_sheet)
        scope_layout.addWidget(self.search_all_sheets)
        search_layout.addLayout(scope_layout)
        top_bar.addWidget(self.search_group)
        
        # 3. Stats Group (Moved to top)
        self.stats_group = QGroupBox("Statistics")
        self.stats_group.setFixedHeight(55)
        stats_layout = QHBoxLayout(self.stats_group)
        stats_layout.setContentsMargins(10, 8, 10, 2)
        stats_layout.setSpacing(15)
        
        label_style = "font-weight: bold; font-size: 9pt;"
        self.total_items_label = QLabel("Total Items: 0")
        self.total_items_label.setStyleSheet(f"{label_style} color: blue;")
        self.priced_items_label = QLabel("Priced Items: 0")
        self.priced_items_label.setStyleSheet(f"{label_style} color: green;")
        self.outstanding_items_label = QLabel("Outstanding: 0")
        self.outstanding_items_label.setStyleSheet(f"{label_style} color: red;")
        
        stats_layout.addWidget(self.total_items_label)
        stats_layout.addWidget(self.priced_items_label)
        stats_layout.addWidget(self.outstanding_items_label)
        top_bar.addWidget(self.stats_group)
        
        top_bar.addStretch()
        main_layout.addLayout(top_bar)

        
        # LEFT PANE: Excel-style tabbed table (Now takes full window)
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.TabPosition.South)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        # Excel-style sheet navigation arrows on the left
        self.tabs.tabBar().setUsesScrollButtons(False)  # Hide default right-side scroll buttons
        
        nav_widget = QWidget()
        nav_layout = QHBoxLayout(nav_widget)
        nav_layout.setContentsMargins(2, 0, 2, 0)
        nav_layout.setSpacing(1)
        
        btn_style = "QPushButton { border: 1px solid #ccc; background: #f5f5f5; padding: 1px 4px; font-size: 8pt; } QPushButton:hover { background: #e0e0e0; }"
        
        first_btn = QPushButton("⏮")
        first_btn.setFixedSize(22, 18)
        first_btn.setStyleSheet(btn_style)
        first_btn.setToolTip("First Sheet")
        first_btn.clicked.connect(lambda: self.tabs.setCurrentIndex(0))
        
        prev_btn = QPushButton("◀")
        prev_btn.setFixedSize(22, 18)
        prev_btn.setStyleSheet(btn_style)
        prev_btn.setToolTip("Previous Sheet")
        prev_btn.clicked.connect(lambda: self.tabs.setCurrentIndex(max(0, self.tabs.currentIndex() - 1)))
        
        next_btn = QPushButton("▶")
        next_btn.setFixedSize(22, 18)
        next_btn.setStyleSheet(btn_style)
        next_btn.setToolTip("Next Sheet")
        next_btn.clicked.connect(lambda: self.tabs.setCurrentIndex(min(self.tabs.count() - 1, self.tabs.currentIndex() + 1)))
        
        last_btn = QPushButton("⏭")
        last_btn.setFixedSize(22, 18)
        last_btn.setStyleSheet(btn_style)
        last_btn.setToolTip("Last Sheet")
        last_btn.clicked.connect(lambda: self.tabs.setCurrentIndex(self.tabs.count() - 1))
        
        nav_layout.addWidget(first_btn)
        nav_layout.addWidget(prev_btn)
        nav_layout.addWidget(next_btn)
        nav_layout.addWidget(last_btn)
        
        
        self.tabs.setCornerWidget(nav_widget, Qt.Corner.BottomLeftCorner)
        left_layout.addWidget(self.tabs)
        
        # RIGHT PANE is moved to a DockWidget in the main window
        from PyQt6.QtWidgets import QDockWidget, QScrollArea
        
        # Tools Pane
        self.tools_dock = QDockWidget("PBOQ Tools", self.main_window)
        self.tools_dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.tools_dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetClosable | QDockWidget.DockWidgetFeature.DockWidgetFloatable | QDockWidget.DockWidgetFeature.DockWidgetMovable)
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(5, 5, 5, 5)
        
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
        
        # Auto-save state when column mappings change
        # Connect signals for auto-saving
        self.cb_ref.currentIndexChanged.connect(self._save_pboq_state)
        self.cb_ref.currentIndexChanged.connect(self._update_column_headers)
        self.cb_desc.currentIndexChanged.connect(self._save_pboq_state)
        self.cb_desc.currentIndexChanged.connect(self._update_column_headers)
        self.cb_qty.currentIndexChanged.connect(self._save_pboq_state)
        self.cb_qty.currentIndexChanged.connect(self._update_column_headers)
        self.cb_unit.currentIndexChanged.connect(self._save_pboq_state)
        self.cb_unit.currentIndexChanged.connect(self._update_column_headers)
        self.cb_bill_rate.currentIndexChanged.connect(self._save_pboq_state)
        self.cb_bill_rate.currentIndexChanged.connect(self._update_column_headers)
        self.cb_bill_amount.currentIndexChanged.connect(self._save_pboq_state)
        self.cb_bill_amount.currentIndexChanged.connect(self._update_column_headers)
        self.cb_rate.currentIndexChanged.connect(self._save_pboq_state)
        self.cb_rate.currentIndexChanged.connect(self._update_column_headers)
        self.cb_rate_code.currentIndexChanged.connect(self._save_pboq_state)
        self.cb_rate_code.currentIndexChanged.connect(self._update_column_headers)
        
        right_layout.addWidget(col_group)
        
        # Format Group
        format_group = QGroupBox("Format")
        format_layout = QVBoxLayout(format_group)
        format_layout.setContentsMargins(5, 5, 5, 5)
        format_layout.setSpacing(5)
        
        format_btns_layout = QHBoxLayout()
        self.wrap_text_btn = QPushButton("Wrap Text")
        self.wrap_text_btn.setCheckable(True)
        self.wrap_text_btn.setChecked(False)
        self.wrap_text_btn.clicked.connect(self._toggle_wrap_text)
        self.wrap_text_btn.clicked.connect(self._save_pboq_state)
        
        self.clear_all_btn = QPushButton("Clear Gross & Code")
        self.clear_all_btn.clicked.connect(self._clear_gross_and_code)
        
        format_btns_layout.addWidget(self.wrap_text_btn)
        format_btns_layout.addWidget(self.clear_all_btn)
        format_layout.addLayout(format_btns_layout)
        
        right_layout.addWidget(format_group)
        
        # Extend Group
        extend_group = QGroupBox("Extend")
        extend_layout = QVBoxLayout(extend_group)
        extend_layout.setContentsMargins(5, 5, 5, 5)
        extend_layout.setSpacing(2)
        
        formula_label = QLabel("Bill Amount = Bill Rate x Qty")
        formula_label.setStyleSheet("font-size: 8pt; color: #555; font-style: italic; margin-bottom: 0px;")
        extend_layout.addWidget(formula_label)
        
        align_label = QLabel("(aligned to :)")
        align_label.setStyleSheet("font-size: 8pt; color: #777; font-style: italic; margin-bottom: 2px;")
        extend_layout.addWidget(align_label)
        
        self.extend_cb0 = QCheckBox("Column 0")
        self.extend_cb1 = QCheckBox("Column 1")
        self.extend_cb2 = QCheckBox("Column 2")
        self.extend_cb3 = QCheckBox("Column 3")
        
        self.extend_cb0.toggled.connect(self._save_pboq_state)
        self.extend_cb1.toggled.connect(self._save_pboq_state)
        self.extend_cb2.toggled.connect(self._save_pboq_state)
        self.extend_cb3.toggled.connect(self._save_pboq_state)
        
        extend_layout.addWidget(self.extend_cb0)
        extend_layout.addWidget(self.extend_cb1)
        extend_layout.addWidget(self.extend_cb2)
        extend_layout.addWidget(self.extend_cb3)
        
        # Dummy Rate Input
        dummy_rate_row = QHBoxLayout()
        dummy_rate_label = QLabel("Dummy Rate :")
        dummy_rate_label.setStyleSheet("font-size: 9pt;")
        self.dummy_rate_spin = QDoubleSpinBox()
        self.dummy_rate_spin.setRange(0.00, 999999.00)
        self.dummy_rate_spin.setDecimals(2)
        self.dummy_rate_spin.setValue(0.00)
        self.dummy_rate_spin.setFixedWidth(85)
        self.dummy_rate_spin.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        self.dummy_rate_spin.valueChanged.connect(self._save_pboq_state)
        
        dummy_rate_row.addWidget(dummy_rate_label)
        dummy_rate_row.addWidget(self.dummy_rate_spin)
        dummy_rate_row.addStretch()
        extend_layout.addLayout(dummy_rate_row)
        
        extend_btns_layout = QHBoxLayout()
        self.clear_bill_btn = QPushButton("Clear")
        self.clear_bill_btn.clicked.connect(self._clear_bill_rates)
        
        self.extend_btn = QPushButton("Extend")
        self.extend_btn.clicked.connect(self._run_extend_logic)
        
        extend_btns_layout.addWidget(self.extend_btn)
        extend_btns_layout.addWidget(self.clear_bill_btn)
        extend_layout.addLayout(extend_btns_layout)
        
        right_layout.addWidget(extend_group)
        
        # Collect Group
        collect_group = QGroupBox("Collect")
        collect_layout = QVBoxLayout(collect_group)
        collect_layout.setContentsMargins(5, 5, 5, 5)
        collect_layout.setSpacing(2)
        
        # Keywords search
        keywords_layout = QHBoxLayout()
        keywords_label = QLabel("Keywords :")
        keywords_label.setStyleSheet("font-size: 8pt; color: #555;")
        self.collect_search_bar = QLineEdit()
        self.collect_search_bar.setPlaceholderText("Search terms...")
        self.collect_search_bar.textChanged.connect(self._save_pboq_state)
        keywords_layout.addWidget(keywords_label)
        keywords_layout.addWidget(self.collect_search_bar)
        collect_layout.addLayout(keywords_layout)
        
        self.collect_desc_cb = QCheckBox("Description")
        self.collect_amount_cb = QCheckBox("Bill Amount")
        self.collect_desc_cb.setChecked(True)
        self.collect_amount_cb.setChecked(True)

        
        self.collect_desc_cb.toggled.connect(self._save_pboq_state)
        self.collect_amount_cb.toggled.connect(self._save_pboq_state)
        
        collect_layout.addWidget(self.collect_desc_cb)
        collect_layout.addWidget(self.collect_amount_cb)
        
        self.collect_btn = QPushButton("Collect")
        self.collect_btn.clicked.connect(self._run_collect_logic)
        collect_layout.addWidget(self.collect_btn)

        # Collection Populator (New Section)
        pop_layout = QVBoxLayout()
        pop_layout.setContentsMargins(0, 5, 0, 0)
        pop_layout.setSpacing(2)
        
        target_label = QLabel("Collection Target (Case Sensitive) : ")
        target_label.setStyleSheet("font-size: 8pt; color: #555; margin-top: 5px;")

        self.collection_target_bar = QLineEdit()
        self.collection_target_bar.setPlaceholderText("e.g. COLLECTION")
        self.collection_target_bar.textChanged.connect(self._save_pboq_state)
        
        self.populate_btn = QPushButton("Populate")
        self.populate_btn.clicked.connect(self._run_populate_collection)
        
        pop_layout.addWidget(target_label)
        pop_layout.addWidget(self.collection_target_bar)
        pop_layout.addWidget(self.populate_btn)
        collect_layout.addLayout(pop_layout)
        
        right_layout.addWidget(collect_group)

        # Summary Group
        summary_group = QGroupBox("Summary")
        summary_layout = QVBoxLayout(summary_group)
        summary_layout.setContentsMargins(5, 5, 5, 5)
        summary_layout.setSpacing(2)
        
        summary_label = QLabel("Summarize Collections (Case Sensitive) :")
        summary_label.setStyleSheet("font-size: 8pt; color: #555;")
        summary_layout.addWidget(summary_label)
        
        summary_checks_layout = QHBoxLayout()
        self.summary_desc_cb = QCheckBox("Description")
        self.summary_amount_cb = QCheckBox("Bill Amount")
        self.summary_desc_cb.setChecked(True)
        summary_checks_layout.addWidget(self.summary_desc_cb)
        summary_checks_layout.addWidget(self.summary_amount_cb)
        summary_layout.addLayout(summary_checks_layout)
        
        self.summary_target_bar = QLineEdit()
        self.summary_target_bar.setPlaceholderText("CARRIED TO SUMMARY OF BILL")
        self.summary_target_bar.textChanged.connect(self._save_pboq_state)
        self.summary_desc_cb.toggled.connect(self._save_pboq_state)
        self.summary_amount_cb.toggled.connect(self._save_pboq_state)
        
        summary_layout.addWidget(self.summary_target_bar)
        
        self.summarize_btn = QPushButton("Summarize")
        self.summarize_btn.clicked.connect(self._run_summary_logic)
        summary_layout.addWidget(self.summarize_btn)
        
        right_layout.addWidget(summary_group)

        
        right_layout.addStretch()
        
        scroll_area.setWidget(right_widget)
        self.tools_dock.setWidget(scroll_area)
        
        # Add to main window
        if self.main_window:
            self.main_window.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.tools_dock)
            # Make sure it appears below the Project dock by tabifying or just adding it
            try:
                self.main_window.splitDockWidget(self.main_window.project_dock, self.tools_dock, Qt.Orientation.Vertical)
                # Resize the docks to give Project pane ~15% height and Tools pane ~85% height of the main window
                h = self.main_window.height()
                self.main_window.resizeDocks([self.main_window.project_dock, self.tools_dock], [int(h * 0.15), int(h * 0.85)], Qt.Orientation.Vertical)
            except AttributeError:
                pass
            
            # Connect to context switching
            self.main_window.mdi_area.subWindowActivated.connect(self._on_mdi_subwindow_activated)
        
        # The main layout is just the Excel table now
        main_layout.addWidget(left_widget)

    def closeEvent(self, event):
        try:
            if self.main_window:
                self.main_window.mdi_area.subWindowActivated.disconnect(self._on_mdi_subwindow_activated)
        except (TypeError, AttributeError):
            pass
        if hasattr(self, 'tools_dock') and self.tools_dock:
            if self.main_window:
                self.main_window.removeDockWidget(self.tools_dock)
            self.tools_dock.deleteLater()
            self.tools_dock = None
        super().closeEvent(event)

    def _on_mdi_subwindow_activated(self, subwindow):
        if not hasattr(self, 'tools_dock') or not self.tools_dock:
            return
        if subwindow and subwindow.widget() is self:
            self.tools_dock.show()
        else:
            self.tools_dock.hide()

    def _load_pboq_db(self, index):
        """Loads a PBOQ .db file and renders it in Excel-style tabs."""
        if index < 0 or index >= self.pboq_file_selector.count():
            return
            
        file_path = self.pboq_file_selector.itemData(index)
        if not file_path or not os.path.exists(file_path):
            return
            
        # Block all signals that could trigger _save_pboq_state during load
        self.tabs.blockSignals(True)
        for cb in [self.cb_ref, self.cb_desc, self.cb_qty, self.cb_unit, self.cb_bill_rate, self.cb_bill_amount, self.cb_rate, self.cb_rate_code]:
            cb.blockSignals(True)
        self.wrap_text_btn.blockSignals(True)
        self.search_this_sheet.blockSignals(True)
        self.search_all_sheets.blockSignals(True)
        self.extend_cb0.blockSignals(True)
        self.extend_cb1.blockSignals(True)
        self.extend_cb2.blockSignals(True)
        self.extend_cb3.blockSignals(True)
        self.collect_desc_cb.blockSignals(True)
        self.collect_amount_cb.blockSignals(True)
        
        try:
            # Set default states for buttons before loading state
            self.extend_btn.setText("Extend")
            self.collect_btn.setText("Collect")
            self.populate_btn.setText("Populate")

            
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
                
                # Fetch all data including rowid for precise updates
                quoted_cols = [f'"{c}"' for c in db_columns]
                query = f"SELECT rowid, {', '.join(quoted_cols)} FROM pboq_items"
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
                
                # Setup Live Links Table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS pboq_links (
                        source_rowid INTEGER,
                        dest_rowid INTEGER,
                        UNIQUE(source_rowid, dest_rowid)
                    )
                """)
                conn.commit()
                
                # Load Links into memory
                self.active_links = {}
                cursor.execute("SELECT source_rowid, dest_rowid FROM pboq_links")
                for src, dst in cursor.fetchall():
                    if src not in self.active_links:
                        self.active_links[src] = []
                    self.active_links[src].append(dst)
                
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
            # Only show up to 8 columns (Column 0 to Column 7)
            num_display_cols = min(8, len(display_col_names))
            
            # Group rows by Sheet name (index 1 after rowid), preserving global row index
            sheet_groups = {}
            for g_idx, row in enumerate(rows):
                row_id = row[0]
                sheet_data = row[1:]
                sheet_name = str(sheet_data[0]) if sheet_data[0] else "Sheet 1"
                if sheet_name not in sheet_groups:
                    sheet_groups[sheet_name] = []
                # Store (global_index, row_id, data_columns[excluding Sheet])
                sheet_groups[sheet_name].append((g_idx, row_id, sheet_data[1:]))
            
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
                table.setWordWrap(False)
                table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
                table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                table.customContextMenuRequested.connect(self._show_amount_context_menu)
                table.cellClicked.connect(self._handle_table_cell_click)

                
                for r_idx, (global_row_idx, row_id, row_data) in enumerate(sheet_entries):
                    for c_idx in range(num_display_cols):
                        col_val = row_data[c_idx] if c_idx < len(row_data) else ""
                        t_item = QTableWidgetItem(str(col_val) if col_val is not None else "")
                        
                        # Store rowid and global_row_idx for later reference and DB persistence
                        if c_idx == 0:
                            t_item.setData(Qt.ItemDataRole.UserRole, row_id)
                        t_item.setData(Qt.ItemDataRole.UserRole + 1, global_row_idx)
                        
                        # Apply column-based identification color as base layer
                        if c_idx < 4:
                            t_item.setBackground(self.COL_COLOR_BLUE)
                        elif c_idx < 6:
                            t_item.setBackground(self.COL_COLOR_YELLOW)
                        elif c_idx < 8:
                            t_item.setBackground(self.COL_COLOR_RED)
                        
                        # Apply specific formatting (overrides column color if present)
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
                        
                        # Special Case: Extended dummy rates (0.00) show as gray text by default
                        if t_item.text() == "0.00":
                            t_item.setForeground(QColor("#777777"))
                            t_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

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
                
                # Fixed 24px row height (matching Excel default)
                table.verticalHeader().setMinimumSectionSize(24)
                table.verticalHeader().setDefaultSectionSize(24)
                table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
                
                self.tabs.addTab(table, sheet_name)
            
            progress.setValue(total_rows)
            
            # Update stats
            outstanding = total_items - priced_items
            self.total_items_label.setText(f"Total Items : {total_items}")
            self.priced_items_label.setText(f"Priced Items : {priced_items}")
            self.outstanding_items_label.setText(f"Outstanding : {outstanding}")
            
            # Restore saved state (column mapping, format, search scope, active tab)
            self._load_pboq_state(index)
            
            # Update column headers based on mapping
            self._update_column_headers()
            
            # Save this bill as the last active one
            self._save_viewer_state()
            
        finally:
            self.tabs.blockSignals(False)
            for cb in [self.cb_ref, self.cb_desc, self.cb_qty, self.cb_unit, self.cb_bill_rate, self.cb_bill_amount, self.cb_rate, self.cb_rate_code]:
                cb.blockSignals(False)
            self.wrap_text_btn.blockSignals(False)
            self.search_this_sheet.blockSignals(False)
            self.search_all_sheets.blockSignals(False)
            self.extend_cb0.blockSignals(False)
            self.extend_cb1.blockSignals(False)
            self.extend_cb2.blockSignals(False)
            self.extend_cb3.blockSignals(False)
            self.collect_desc_cb.blockSignals(False)
            self.collect_amount_cb.blockSignals(False)
            self.collect_search_bar.blockSignals(False)


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

    def _filter_tables(self, text):
        """Filters rows based on search scope (This Sheet or All Sheets)."""
        search_text = text.lower() if isinstance(text, str) else self.search_bar.text().lower()
        
        all_tables = [self.tabs.widget(i) for i in range(self.tabs.count())]
        
        if self.search_all_sheets.isChecked():
            # Filter across all tabs
            tables = all_tables
        else:
            # Filter only the current tab; unhide all rows on other tabs
            current = self.tabs.currentWidget()
            tables = [current] if current else []
            for t in all_tables:
                if t != current and isinstance(t, QTableWidget):
                    for row in range(t.rowCount()):
                        t.setRowHidden(row, False)
        
        for table in tables:
            if not isinstance(table, QTableWidget):
                continue
            for row in range(table.rowCount()):
                row_texts = []
                for col in range(table.columnCount()):
                    item = table.item(row, col)
                    if item:
                        row_texts.append(item.text().lower())
                
                full_row_text = " ".join(row_texts)
                table.setRowHidden(row, search_text not in full_row_text if search_text else False)

    def _toggle_wrap_text(self):
        """Toggles word wrap on the description column across all tabs."""
        self.wrap_text_enabled = self.wrap_text_btn.isChecked()
        self.wrap_text_btn.setText("Unwrap Text" if self.wrap_text_enabled else "Wrap Text")
        desc_col = self.cb_desc.currentIndex() - 1
        
        for tab_idx in range(self.tabs.count()):
            table = self.tabs.widget(tab_idx)
            if not isinstance(table, QTableWidget):
                continue
            
            table.setWordWrap(self.wrap_text_enabled)
            
            if self.wrap_text_enabled:
                # Allow rows to expand for wrapped text, but never shrink below 24px
                table.verticalHeader().setMinimumSectionSize(24)
                table.verticalHeader().setDefaultSectionSize(24)
                table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
            else:
                # Revert to fixed 24px row height
                table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
                table.verticalHeader().setDefaultSectionSize(24)
                table.verticalHeader().setMinimumSectionSize(24)
        
        # Immediately recalculate the visible tab
        self._on_tab_changed(self.tabs.currentIndex())

    def _clear_bill_rates(self):
        """Clears all values matching the current Dummy Rate in Bill Rate/Amount columns."""
        qty_idx = self.cb_qty.currentIndex() - 1
        rate_idx = self.cb_bill_rate.currentIndex() - 1
        amount_idx = self.cb_bill_amount.currentIndex() - 1
        
        if rate_idx < 0 and amount_idx < 0:
            QMessageBox.warning(self, "Mapping Required", "Please map at least 'Bill Rate' or 'Bill Amount' column.")
            return

        d_rate = self.dummy_rate_spin.value()
        d_rate_str = "{:,.2f}".format(d_rate)


        reply = QMessageBox.question(self, "Confirm Clear", 
                                   f"This will clear values matching the Dummy Rate ({d_rate_str}) in mapped Bill Rate/Amount columns across all sheets.\n\nContinue?",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.No:
            return

        total_cleared = 0
        total_sheets = self.tabs.count()
        rate_updates = [] # (rowid, val)
        amount_updates = [] # (rowid, val)

        for tab_idx in range(total_sheets):
            table = self.tabs.widget(tab_idx)
            if not isinstance(table, QTableWidget): continue
            
            for row in range(table.rowCount()):
                rowid = table.item(row, 0).data(Qt.ItemDataRole.UserRole)
                if rowid is None: continue

                # 1. Identify Row Quantity for Amount calculation
                q_val = 0.0
                if qty_idx >= 0:
                    q_item = table.item(row, qty_idx)
                    if q_item:
                        try:
                            clean_q = q_item.text().strip().replace(',', '').replace(' ', '')
                            if clean_q: q_val = float(clean_q)
                        except ValueError: pass

                # 2. Clear Bill Rate if it matches Dummy Rate
                if rate_idx >= 0:
                    item = table.item(row, rate_idx)
                    if item and item.text().strip() == d_rate_str:
                        item.setText("")
                        rate_updates.append((rowid, None))
                        total_cleared += 1

                # 3. Clear Bill Amount if it matches (Qty * Dummy Rate)
                if amount_idx >= 0:
                    item = table.item(row, amount_idx)
                    if item:
                        # Calculate what the dummy amount would have been
                        expected_amt_str = "{:,.2f}".format(q_val * d_rate)

                        if item.text().strip() == expected_amt_str:
                            item.setText("")
                            amount_updates.append((rowid, None))

        if total_cleared > 0 or rate_updates or amount_updates:
            if rate_updates:
                self._persist_batch_updates(rate_idx, rate_updates)
            if amount_updates:
                self._persist_batch_updates(amount_idx, amount_updates)
            
            QMessageBox.information(self, "Clear Complete", f"Successfully cleared dummy values matching {d_rate_str} from {total_cleared} rows.")
        else:
            QMessageBox.information(self, "Nothing Found", f"No values matching {d_rate_str} were found in the mapped columns.")

    def _run_collect_logic(self):
        """Searches description for keywords and highlights intersecting bill amount cells Orange."""
        desc_idx = self.cb_desc.currentIndex() - 1
        amount_idx = self.cb_bill_amount.currentIndex() - 1
        
        if not self.collect_desc_cb.isChecked():
            QMessageBox.warning(self, "Selection Required", "Please check the 'Description' box.")
            return
        if not self.collect_amount_cb.isChecked():
            QMessageBox.warning(self, "Selection Required", "Please check the 'Bill Amount' box.")
            return
        if desc_idx < 0:
            QMessageBox.warning(self, "Mapping Required", "Please map the 'Description' column first.")
            return
        if amount_idx < 0:
            QMessageBox.warning(self, "Mapping Required", "Please map the 'Bill Amount' column first.")
            return

        is_revert = self.collect_btn.text() == "Revert"
        total_sheets = self.tabs.count()
        keyword = self.collect_search_bar.text().lower().strip()
        
        if is_revert:
            # --- REVERT LOGIC ---
            updated_count = 0
            updates_to_db = []
            for tab_idx in range(total_sheets):
                table = self.tabs.widget(tab_idx)
                if not isinstance(table, QTableWidget): continue
                
                for row in range(table.rowCount()):
                    # Find Orange cells in the bill amount column and revert to base background
                    amount_item = table.item(row, amount_idx)
                    if amount_item and amount_item.background().color().name().lower() in ("#ffa500", "orange"):  # Orange
                        # Revert background to column color (Blue: <4, Yellow: <6, Red: <8)
                        base_bg = QColor("#ffffff")
                        if amount_idx < 4: base_bg = self.COL_COLOR_BLUE
                        elif amount_idx < 6: base_bg = self.COL_COLOR_YELLOW
                        elif amount_idx < 8: base_bg = self.COL_COLOR_RED
                        
                        amount_item.setBackground(base_bg)
                        
                        # Clear text
                        amount_item.setText("")
                        
                        # Prepare DB update
                        rowid = table.item(row, 0).data(Qt.ItemDataRole.UserRole)
                        global_idx = amount_item.data(Qt.ItemDataRole.UserRole + 1)
                        if rowid is not None:
                            updates_to_db.append((rowid, None))
                        if global_idx is not None:
                            self._clear_cell_formatting(global_idx, amount_idx)
                            
                        updated_count += 1
            
            if updated_count > 0:
                if updates_to_db:
                    self._persist_batch_updates(amount_idx, updates_to_db)
                self.collect_btn.setText("Collect")
                self._save_pboq_state()
                QMessageBox.information(self, "Revert Complete", f"Successfully reverted {updated_count} collected cells.")
            else:
                self.collect_btn.setText("Collect")
                QMessageBox.information(self, "Nothing to Revert", "No highlighted items found to clear.")
        else:
            # --- COLLECT LOGIC ---
            if not keyword:
                QMessageBox.warning(self, "Keyword Required", "Please enter a keyword to search.")
                return

            updated_count = 0
            updates_to_db = []
            for tab_idx in range(total_sheets):
                table = self.tabs.widget(tab_idx)
                if not isinstance(table, QTableWidget): continue
                
                current_sum = 0.0
                for row in range(table.rowCount()):
                    desc_item = table.item(row, desc_idx)
                    amount_item = table.item(row, amount_idx)
                    
                    if desc_item and keyword in desc_item.text().lower():
                        # Highlight the intersecting bill amount cell
                        if amount_item:
                            amount_item.setBackground(QColor("orange"))
                            # Store and display sum
                            formatted_sum = "{:,.2f}".format(current_sum)
                            amount_item.setText(formatted_sum)
                            amount_item.setForeground(QColor("#777777")) # Gray out color
                            
                            # Prepare DB update
                            rowid = table.item(row, 0).data(Qt.ItemDataRole.UserRole)
                            global_idx = amount_item.data(Qt.ItemDataRole.UserRole + 1)
                            if rowid is not None:
                                updates_to_db.append((rowid, formatted_sum))
                            if global_idx is not None:
                                self._persist_cell_formatting(global_idx, amount_idx, bg_color="orange", fg_color="#777777")
                                
                            updated_count += 1
                        
                        # Reset the sum accumulator for the next collection area
                        current_sum = 0.0

                    else:
                        # Accumulate the sum from existing valid figures
                        if amount_item and amount_item.text().strip():
                            try:
                                val_str = amount_item.text().strip().replace(',', '').replace(' ', '')
                                if val_str:
                                    current_sum += float(val_str)
                            except ValueError:
                                pass
            
            if updated_count > 0:
                if updates_to_db:
                    self._persist_batch_updates(amount_idx, updates_to_db)
                self.collect_btn.setText("Revert")
                self._save_pboq_state()
                QMessageBox.information(self, "Collect Complete", f"Found, highlighted, and summed {updated_count} cells.")
            else:
                QMessageBox.information(self, "Nothing Found", f"No descriptions matched the keyword '{keyword}'.")

    def _apply_collect_highlights(self):
        """Silently applies the collect highlights from saved state without dialogs."""
        desc_idx = self.cb_desc.currentIndex() - 1
        amount_idx = self.cb_bill_amount.currentIndex() - 1
        
        if not self.collect_desc_cb.isChecked() or not self.collect_amount_cb.isChecked() or desc_idx < 0 or amount_idx < 0:
            return

        keyword = self.collect_search_bar.text().lower().strip()
        if not keyword:
            return

        for tab_idx in range(self.tabs.count()):
            table = self.tabs.widget(tab_idx)
            if not isinstance(table, QTableWidget): continue
            
            for row in range(table.rowCount()):
                desc_item = table.item(row, desc_idx)
                if not desc_item: continue
                
                if keyword in desc_item.text().lower():
                    amount_item = table.item(row, amount_idx)
                    if amount_item:
                        amount_item.setBackground(QColor("orange"))
                        amount_item.setForeground(QColor("#777777"))
                        amount_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                        # Persist for consistency if not already there
                        global_idx = amount_item.data(Qt.ItemDataRole.UserRole + 1)
                        if global_idx is not None:
                            self._persist_cell_formatting(global_idx, amount_idx, bg_color="orange", fg_color="#777777")
        
        self.collect_btn.setText("Revert")
    
    def _apply_populate_highlights(self):
        """Re-applies yellow highlights to populated collection cells from saved state."""
        desc_idx = self.cb_desc.currentIndex() - 1
        amount_idx = self.cb_bill_amount.currentIndex() - 1
        qty_idx = self.cb_qty.currentIndex() - 1
        
        target_input = self.collection_target_bar.text().strip()
        if not target_input or desc_idx < 0 or amount_idx < 0:
            return

        target_keywords = [k.strip() for k in target_input.split(',') if k.strip()]
        
        for tab_idx in range(self.tabs.count()):
            table = self.tabs.widget(tab_idx)
            if not isinstance(table, QTableWidget): continue

            found_target = False
            for row in range(table.rowCount()):
                desc_item = table.item(row, desc_idx)
                if not desc_item: continue
                
                desc_text = desc_item.text()
                
                if not found_target:
                    if any(kw in desc_text for kw in target_keywords):
                        found_target = True
                    continue 
                
                # Detect populated rows: Description present, No Quantity, Gray Text
                has_qty = False
                if qty_idx >= 0:
                    qty_item = table.item(row, qty_idx)
                    if qty_item and qty_item.text().strip():
                        has_qty = True
                
                amount_item = table.item(row, amount_idx)
                if desc_text.strip() and not has_qty and amount_item and amount_item.text().strip():
                    if amount_item.foreground().color().name().lower() == "#777777":
                        amount_item.setBackground(QColor("yellow"))


    def _run_populate_collection(self):
        """Sequential filling of collection summaries or clearing them (Un-Populate)."""
        desc_idx = self.cb_desc.currentIndex() - 1
        amount_idx = self.cb_bill_amount.currentIndex() - 1
        qty_idx = self.cb_qty.currentIndex() - 1
        
        target_input = self.collection_target_bar.text().strip()
        is_revert = self.populate_btn.text() == "Un-Populate"
        
        if not target_input and not is_revert:
            QMessageBox.warning(self, "Input Required", "Please enter target keyword(s) (e.g. COLLECTION, SUMMARY).")
            return
        if desc_idx < 0 or amount_idx < 0:
            QMessageBox.warning(self, "Mapping Required", "Please map 'Description' and 'Bill Amount' columns.")
            return

        # Split multiple keywords by comma and strip whitespace
        target_keywords = [k.strip() for k in target_input.split(',') if k.strip()]
        
        total_affected = 0
        total_sheets = self.tabs.count()
        
        for tab_idx in range(total_sheets):
            table = self.tabs.widget(tab_idx)
            if not isinstance(table, QTableWidget): continue

            # For Populate: Need the bucket. For Un-Populate: We clear based on target zone logic.
            bucket = []
            if not is_revert:
                for row in range(table.rowCount()):
                    item = table.item(row, amount_idx)
                    # We identify collected values by their Orange background
                    if item and item.background().color().name().lower() == "#ffa500": # Orange
                        val_str = item.text().strip()
                        rowid = table.item(row, 0).data(Qt.ItemDataRole.UserRole)
                        if val_str and rowid is not None:
                            bucket.append((rowid, val_str))
                if not bucket:
                    continue


            # Target Zone Detection
            found_target = False
            bucket_idx = 0
            updates_to_db = [] # (rowid, value)
            
            for row in range(table.rowCount()):
                desc_item = table.item(row, desc_idx)
                if not desc_item: continue
                
                desc_text = desc_item.text() # Case-sensitive
                
                if not found_target:
                    # Case-sensitive check against any of the keywords
                    if any(kw in desc_text for kw in target_keywords):
                        found_target = True
                    continue 
                
                # Check Quantity
                has_qty = False
                if qty_idx >= 0:
                    qty_item = table.item(row, qty_idx)
                    if qty_item and qty_item.text().strip():
                        has_qty = True
                
                amount_item = table.item(row, amount_idx)
                
                if is_revert:
                    # REVERT MODE: Clear values that were likely populated (Gray text, no qty)
                    if desc_text.strip() and not has_qty and amount_item:
                        # Check if it has gray text (our signature)
                        if amount_item.foreground().color().name().lower() == "#777777":
                            amount_item.setText("")
                            amount_item.setBackground(QBrush()) # Clear yellow
                            rowid = table.item(row, 0).data(Qt.ItemDataRole.UserRole)

                            if rowid is not None:
                                self._remove_link_from_db(rowid) # Break link on Un-Populate
                                updates_to_db.append((rowid, ""))
                            total_affected += 1

                else:
                    # POPULATE MODE
                    has_amount = amount_item and amount_item.text().strip()
                    if desc_text.strip() and not has_qty and not has_amount:
                        if bucket_idx < len(bucket):
                            source_rowid, val_to_fill = bucket[bucket_idx]
                            dest_rowid = table.item(row, 0).data(Qt.ItemDataRole.UserRole)
                            
                            if not amount_item:
                                amount_item = QTableWidgetItem()
                                table.setItem(row, amount_idx, amount_item)
                            
                            if dest_rowid is not None:
                                self._remove_link_from_db(dest_rowid) # Break any existing links
                                self._save_link_to_db(source_rowid, dest_rowid) # Establish live link
                                updates_to_db.append((dest_rowid, val_to_fill))
                            
                            amount_item.setText(val_to_fill)
                            amount_item.setForeground(QColor("#777777")) 
                            amount_item.setBackground(QColor("yellow"))
                            amount_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                            
                            bucket_idx += 1
                            total_affected += 1
                        
                        if bucket_idx >= len(bucket):
                            break 
 

            if updates_to_db:
                self._persist_batch_updates(amount_idx, updates_to_db)

        if total_affected > 0:
            if is_revert:
                self.populate_btn.setText("Populate")
                QMessageBox.information(self, "Un-Populate Complete", f"Cleared {total_affected} populated rows.")
            else:
                self.populate_btn.setText("Un-Populate")
                QMessageBox.information(self, "Populate Complete", f"Successfully populated {total_affected} collection rows.")
            self._save_pboq_state()
        else:
            msg = "Could not find any target zones to clear." if is_revert else "Could not find any empty rows below the keywords to fill."
            QMessageBox.information(self, "No Action Taken", msg)

    def _run_summary_logic(self):
        """Sums all 'collected' (Orange) cells and outputs the total to 'Summary' (Lime) rows."""
        desc_idx = self.cb_desc.currentIndex() - 1
        amount_idx = self.cb_bill_amount.currentIndex() - 1
        
        if not self.summary_desc_cb.isChecked() and not self.summary_amount_cb.isChecked():
            QMessageBox.warning(self, "Selection Required", "Please check 'Description' or 'Bill Amount' box.")
            return
        if desc_idx < 0 and self.summary_desc_cb.isChecked():
            QMessageBox.warning(self, "Mapping Required", "Please map the 'Description' column.")
            return
        if amount_idx < 0:
            QMessageBox.warning(self, "Mapping Required", "Please map the 'Bill Amount' column.")
            return

        target_text = self.summary_target_bar.text().strip()
        if not target_text:
            QMessageBox.warning(self, "Target Required", "Please enter a target text for summary rows.")
            return

        total_sheets = self.tabs.count()
        overall_updated = 0
        overall_sum = 0.0
        
        qty_idx = self.cb_qty.currentIndex() - 1
        
        for tab_idx in range(total_sheets):
            table = self.tabs.widget(tab_idx)
            if not isinstance(table, QTableWidget): continue
            
            # Step 1: Collect values from Orange cells
            orange_values = []
            for row in range(table.rowCount()):
                amount_item = table.item(row, amount_idx)
                # Robust color check (hex match or explicit Orange)
                if amount_item and amount_item.background().color().name().lower() in ("#ffa500", "orange"): # Orange
                    val_str = amount_item.text().strip().replace(',', '').replace(' ', '')
                    try:
                        if val_str:
                            orange_values.append(float(val_str))
                    except ValueError:
                        pass
            
            sheet_sum = 0.0
            if orange_values:
                # Use Orange collections if they exist
                sheet_sum = sum(orange_values)
            else:
                # SMART FALLBACK: Sum all numeric items in the Bill Amount column
                for row in range(table.rowCount()):
                    # Skip the target matching row itself if it already has a value to avoid circular accumulation
                    is_target = False
                    row_desc = ""
                    row_amt_txt = ""
                    
                    if desc_idx >= 0:
                        desc_item = table.item(row, desc_idx)
                        if desc_item: row_desc = desc_item.text()
                    
                    amt_item = table.item(row, amount_idx)
                    if amt_item: row_amt_txt = amt_item.text()
                    
                    # Case-insensitive target matching for robustness
                    if self.summary_desc_cb.isChecked() and target_text.lower() in row_desc.lower():
                        is_target = True
                    if not is_target and self.summary_amount_cb.isChecked() and target_text.lower() in row_amt_txt.lower():
                        is_target = True
                    
                    if not is_target:
                        amount_item = table.item(row, amount_idx)
                        if amount_item:
                            # Skip Orange cells here as they are intermediate sums
                            if amount_item.background().color().name().lower() not in ("#ffa500", "orange"):
                                val_str = amount_item.text().strip().replace(',', '').replace(' ', '')
                                try:
                                    if val_str:
                                        sheet_sum += float(val_str)
                                except ValueError:
                                    pass
            
            # Step 2: Find target rows and update
            updates_to_db = []
            for row in range(table.rowCount()):
                match = False
                row_desc = ""
                row_amt_txt = ""
                
                if desc_idx >= 0:
                    desc_item = table.item(row, desc_idx)
                    if desc_item: row_desc = desc_item.text()
                
                amt_item = table.item(row, amount_idx)
                if amt_item: row_amt_txt = amt_item.text()

                if self.summary_desc_cb.isChecked() and target_text.lower() in row_desc.lower():
                    match = True
                if not match and self.summary_amount_cb.isChecked() and target_text.lower() in row_amt_txt.lower():
                    match = True
                
                if match:
                    amount_item = table.item(row, amount_idx)
                    if not amount_item:
                        amount_item = QTableWidgetItem()
                        table.setItem(row, amount_idx, amount_item)
                    
                    formatted_sum = "{:,.2f}".format(sheet_sum)
                    amount_item.setText(formatted_sum)
                    amount_item.setBackground(QColor("lime"))
                    amount_item.setForeground(QColor("#777777")) 
                    amount_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    
                    rowid = table.item(row, 0).data(Qt.ItemDataRole.UserRole)
                    global_idx = amount_item.data(Qt.ItemDataRole.UserRole + 1)
                    
                    if rowid is not None:
                        updates_to_db.append((rowid, formatted_sum))
                    if global_idx is not None:
                        self._persist_cell_formatting(global_idx, amount_idx, bg_color="lime", fg_color="#777777")
                        
                    overall_updated += 1
                    overall_sum = sheet_sum # Store the last sheet sum for the message
            
            if updates_to_db:
                self._persist_batch_updates(amount_idx, updates_to_db)

        if overall_updated > 0:
            self._save_pboq_state()
            QMessageBox.information(self, "Summary Complete", f"Successfully updated {overall_updated} summary cells matching '{target_text}'.")
        else:
            QMessageBox.information(self, "Nothing Found", f"Target text '{target_text}' not found in the ticked columns.")

    def _apply_summary_highlights(self):
        """Silently re-applies Lime highlights to summary cells from saved state."""
        desc_idx = self.cb_desc.currentIndex() - 1
        amount_idx = self.cb_bill_amount.currentIndex() - 1
        target_text = self.summary_target_bar.text().strip()
        
        if not target_text or (desc_idx < 0 and amount_idx < 0):
            return

        for tab_idx in range(self.tabs.count()):
            table = self.tabs.widget(tab_idx)
            if not isinstance(table, QTableWidget): continue
            
            for row in range(table.rowCount()):
                match = False
                row_desc = ""
                row_amt_txt = ""
                
                if desc_idx >= 0:
                    desc_item = table.item(row, desc_idx)
                    if desc_item: row_desc = desc_item.text()
                
                amt_item = table.item(row, amount_idx)
                if amt_item: row_amt_txt = amt_item.text()

                if self.summary_desc_cb.isChecked() and target_text.lower() in row_desc.lower():
                    match = True
                if not match and self.summary_amount_cb.isChecked() and target_text.lower() in row_amt_txt.lower():
                    match = True
                
                if match:
                    amount_item = table.item(row, amount_idx)
                    if amount_item:
                        amount_item.setBackground(QColor("lime"))
                        amount_item.setForeground(QColor("#777777"))
                        amount_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                        # Persist for consistency if not already there
                        global_idx = amount_item.data(Qt.ItemDataRole.UserRole + 1)
                        if global_idx is not None:
                            self._persist_cell_formatting(global_idx, amount_idx, bg_color="lime", fg_color="#777777")



    def _show_amount_context_menu(self, pos):
        """Shows a context menu for the Bill Amount column with Clear and Link options."""
        table = self.sender()
        if not isinstance(table, QTableWidget): return
        
        index = table.indexAt(pos)
        if not index.isValid(): return
        
        row = index.row()
        col = index.column()
        
        amount_idx = self.cb_bill_amount.currentIndex() - 1
        if col != amount_idx: return # Only for Bill Amount column
        
        menu = QMenu(self)
        clear_act = menu.addAction("Clear")
        link_act = menu.addAction("Link to Collection")
        
        # Determine global position for showing the menu
        global_pos = table.viewport().mapToGlobal(pos)
        action = menu.exec(global_pos)
        if not action: return
        
        item = table.item(row, col)
        rowid = table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        
        # If clearing and no item exists, nothing to do. If linking, we need value.
        if action == clear_act:
            if item:
                item.setText("")
                if rowid is not None:
                    # Remove any links where this row is a destination
                    self._remove_link_from_db(dest_rowid=rowid)
                    self._persist_batch_updates(amount_idx, [(rowid, "")])
                self._update_stats()
        
        elif action == link_act:
            if not item or not item.text().strip():
                QMessageBox.warning(self, "No Value", "The source cell is empty and cannot be used for linking.")
                return

            if rowid is None:
                QMessageBox.warning(self, "Error", "Could not identify row ID for linking.")
                return

            # End any existing link mode before starting new one
            self._clear_link_mode()
            
            # Start Link Mode
            orig_bg = item.background()
            item.setBackground(QColor("#00FFFF")) # Distinctive Cyan highlight
            self.linking_source = {
                'table': table,
                'row': row,
                'col': col,
                'rowid': rowid,
                'val': item.text(),
                'item': item,
                'orig_bg': orig_bg
            }


    def _handle_table_cell_click(self, row, col):
        """Handles cell clicks for the Link to Collection logic."""
        if not self.linking_source:
            return
            
        table = self.sender()
        if not isinstance(table, QTableWidget): return
        
        amount_idx = self.cb_bill_amount.currentIndex() - 1
        
        # Check if clicked in Bill Amount column and it's NOT the same source cell
        is_dest = (col == amount_idx)
        ls = self.linking_source
        is_source = (table == ls['table'] and row == ls['row'] and col == ls['col'])
        
        if is_dest and not is_source:
            # Perform Link (Copy)
            item = table.item(row, col)
            if not item:
                item = QTableWidgetItem()
                table.setItem(row, col, item)
            
            # Establish the Link
            dest_rowid = table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            source_rowid = ls['rowid']
            val = ls['val']
            
            if dest_rowid is not None:
                self._remove_link_from_db(dest_rowid) # Break any existing links
                self._save_link_to_db(source_rowid, dest_rowid)

                item.setText(val)
                item.setForeground(QColor("#777777"))
                item.setBackground(QColor("yellow"))
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

                
                # Persist value to DB
                self._persist_batch_updates(amount_idx, [(dest_rowid, val)])
                self._update_stats()
            
        # End link mode regardless of where they clicked
        self._clear_link_mode()

    def _save_link_to_db(self, source_rowid, dest_rowid):
        """Persists a live link relationship in the database and updates memory cache."""
        file_path = self.pboq_file_selector.currentData()
        if not file_path or not os.path.exists(file_path): return
        
        try:
            conn = sqlite3.connect(file_path)
            cursor = conn.cursor()
            # Insert or ignore for uniqueness
            cursor.execute("INSERT OR REPLACE INTO pboq_links (source_rowid, dest_rowid) VALUES (?, ?)", 
                         (source_rowid, dest_rowid))
            conn.commit()
            conn.close()
            
            # Update memory cache
            if source_rowid not in self.active_links:
                self.active_links[source_rowid] = []
            if dest_rowid not in self.active_links[source_rowid]:
                self.active_links[source_rowid].append(dest_rowid)
        except Exception as e:
            print(f"Error saving link to DB: {e}")

    def _remove_link_from_db(self, dest_rowid):
        """Removes a link relationship when a destination cell is cleared or re-linked."""
        file_path = self.pboq_file_selector.currentData()
        if not file_path or not os.path.exists(file_path): return
        
        try:
            conn = sqlite3.connect(file_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM pboq_links WHERE dest_rowid = ?", (dest_rowid,))
            conn.commit()
            conn.close()
            
            # Update memory cache
            for src in self.active_links:
                if dest_rowid in self.active_links[src]:
                    self.active_links[src].remove(dest_rowid)
        except Exception as e:
            print(f"Error removing link from DB: {e}")

    def _clear_link_mode(self):

        """Clears the current linking state and restores visual properties."""
        if self.linking_source:
            ls = self.linking_source
            ls['item'].setBackground(ls['orig_bg'])
            self.linking_source = None

    def _run_extend_logic(self):

        """Toggles between inserting dummy rates (Extend) and clearing them (Revert)."""
        qty_idx = self.cb_qty.currentIndex() - 1
        rate_idx = self.cb_bill_rate.currentIndex() - 1
        
        if qty_idx < 0:
            QMessageBox.warning(self, "Column Mapping Required", "Please map the 'Quantity' column first.")
            return
        if rate_idx < 0:
            QMessageBox.warning(self, "Column Mapping Required", "Please map the 'Bill Rate' column first.")
            return

        is_revert = self.extend_btn.text() == "Revert"
        updates_to_db = [] # List of (rowid, new_val)
        updated_count = 0
        total_sheets = self.tabs.count()
        
        if is_revert:
            # --- REVERT LOGIC ---
            amount_idx = self.cb_bill_amount.currentIndex() - 1
            rate_updates = []
            amount_updates = []
            
            d_rate = self.dummy_rate_spin.value()
            d_rate_str = "{:,.2f}".format(d_rate)
        
            for tab_idx in range(total_sheets):
                table = self.tabs.widget(tab_idx)
                if not isinstance(table, QTableWidget): continue
                
                for row in range(table.rowCount()):
                    rate_item = table.item(row, rate_idx)
                    # Identify dummy rates by their gray color AND matching the current dummy rate value
                    if rate_item and rate_item.foreground().color().name().lower() == "#777777" and rate_item.text() == d_rate_str:
                        # Clear Rate
                        rate_item.setText("")
                        
                        # Clear Amount as well if mapped
                        if amount_idx >= 0:
                            amt_item = table.item(row, amount_idx)
                            if amt_item:
                                amt_item.setText("")
                        
                        # Get rowid for DB update
                        rowid = table.item(row, 0).data(Qt.ItemDataRole.UserRole)
                        if rowid is not None:
                            rate_updates.append((rowid, None))
                            if amount_idx >= 0:
                                amount_updates.append((rowid, None))
                        updated_count += 1
            
            if updated_count > 0:
                self._persist_batch_updates(rate_idx, rate_updates)
                if amount_idx >= 0:
                    self._persist_batch_updates(amount_idx, amount_updates)
                self.extend_btn.setText("Extend")
                QMessageBox.information(self, "Revert Complete", f"Successfully cleared {updated_count} extended rows.")
            else:
                self.extend_btn.setText("Extend")
                QMessageBox.information(self, "Nothing to Revert", "No auto-extended rates were found to clear.")

        else:
            # --- EXTEND LOGIC ---
            amount_idx = self.cb_bill_amount.currentIndex() - 1
            rate_updates = []
            amount_updates = []
            
            checked_cols = []
            if self.extend_cb0.isChecked(): checked_cols.append(0)
            if self.extend_cb1.isChecked(): checked_cols.append(1)
            if self.extend_cb2.isChecked(): checked_cols.append(2)
            if self.extend_cb3.isChecked(): checked_cols.append(3)
            
            if not checked_cols:
                QMessageBox.warning(self, "Alignment Required", 
                                    "Please select at least one column (0-3) in the 'Extend' group to align items.")
                return

            for tab_idx in range(total_sheets):
                table = self.tabs.widget(tab_idx)
                if not isinstance(table, QTableWidget): continue
                
                for row in range(table.rowCount()):
                    # 1. Check Alignment
                    is_aligned = True
                    for col_idx in checked_cols:
                        item = table.item(row, col_idx)
                        if not item or not item.text().strip():
                            is_aligned = False
                            break
                    if not is_aligned: continue
                    
                    # 2. Check for Quantity
                    qty_item = table.item(row, qty_idx)
                    qty_str = qty_item.text().strip() if qty_item else ""
                    try:
                        clean_qty = qty_str.replace(',', '').replace(' ', '')
                        if not clean_qty: continue
                        q_val = float(clean_qty)
                        if q_val <= 0: continue
                        
                        # 3. Check / Insert Dummy Rate
                        rate_item = table.item(row, rate_idx)
                        rate_str = rate_item.text().strip() if rate_item else ""
                        try:
                            if rate_str:
                                float(rate_str.replace(',', '').replace(' ', ''))
                                continue # Preserves existing rates
                        except ValueError: pass
                        
                        # Insert Dummy Rate
                        d_rate = self.dummy_rate_spin.value()
                        rate_val_str = "{:,.2f}".format(d_rate)
                        dummy_item = QTableWidgetItem(rate_val_str)
                        dummy_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                        
                        # Apply background color
                        if rate_idx < 4: dummy_item.setBackground(self.COL_COLOR_BLUE)
                        elif rate_idx < 6: dummy_item.setBackground(self.COL_COLOR_YELLOW)
                        elif rate_idx < 8: dummy_item.setBackground(self.COL_COLOR_RED)
                            
                        dummy_item.setForeground(QColor("#777777"))
                        table.setItem(row, rate_idx, dummy_item)
                        
                        # Calculation: Bill Amount = Qty * Custom Dummy Rate
                        if amount_idx >= 0:
                            bill_amount = q_val * d_rate
                            amt_val_str = "{:,.2f}".format(bill_amount)
                            amt_item = QTableWidgetItem(amt_val_str)
                            amt_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                            
                            # Apply background color based on column index (to match theme)
                            if amount_idx < 4: amt_item.setBackground(self.COL_COLOR_BLUE)
                            elif amount_idx < 6: amt_item.setBackground(self.COL_COLOR_YELLOW)
                            elif amount_idx < 8: amt_item.setBackground(self.COL_COLOR_RED)
                            
                            amt_item.setForeground(QColor("#777777")) # Match dummy color
                            table.setItem(row, amount_idx, amt_item)

                        rowid = table.item(row, 0).data(Qt.ItemDataRole.UserRole)
                        if rowid is not None:
                            rate_updates.append((rowid, rate_val_str))
                            if amount_idx >= 0:
                                amount_updates.append((rowid, amt_val_str))
                        updated_count += 1
                        
                    except ValueError: continue

            
            if updated_count > 0:
                self._persist_batch_updates(rate_idx, rate_updates)
                if amount_idx >= 0:
                    self._persist_batch_updates(amount_idx, amount_updates)
                self.extend_btn.setText("Revert")
                QMessageBox.information(self, "Extend Complete", 
                                      f"Successfully inserted and calculated {updated_count} items.")
            else:
                QMessageBox.information(self, "No Items Found", 
                                      "No aligned items without rates were found with valid numeric quantities.")

    def _persist_batch_updates(self, rate_idx, updates):
        """Helper to batch update PBOQ items in the database by rowid."""
        file_path = self.pboq_file_selector.currentData()
        if not file_path or not os.path.exists(file_path): return
        
        try:
            conn = sqlite3.connect(file_path)
            cursor = conn.cursor()
            db_cols = getattr(self, 'db_columns', [])
            db_col_to_update = db_cols[rate_idx + 1] if rate_idx + 1 < len(db_cols) else None
            
            if db_col_to_update:
                for rowid, val in updates:
                    cursor.execute(f'UPDATE pboq_items SET "{db_col_to_update}" = ? WHERE rowid = ?', (val, rowid))
                conn.commit()
            conn.close()
            
            # If this update was on the Bill Amount column, trigger live sync
            amount_idx = self.cb_bill_amount.currentIndex() - 1
            if rate_idx == amount_idx:
                self._sync_live_links(updates)

        except Exception as e:
            print(f"Error persisting batch updates: {e}")

    def _persist_cell_formatting(self, global_row_idx, col_idx, bg_color=None, fg_color=None, bold=None):
        """Persists cell-level formatting (colors, bold) to the pboq_formatting table."""
        file_path = self.pboq_file_selector.currentData()
        if not file_path or not os.path.exists(file_path): return
        
        try:
            conn = sqlite3.connect(file_path)
            cursor = conn.cursor()
            
            # Fetch existing JSON if any
            cursor.execute("SELECT fmt_json FROM pboq_formatting WHERE row_idx=? AND col_idx=?", (global_row_idx, col_idx))
            row = cursor.fetchone()
            fmt = json.loads(row[0]) if row else {}
            
            # Update values
            if bg_color: fmt['bg_color'] = bg_color if isinstance(bg_color, str) else bg_color.name()
            if fg_color: fmt['font_color'] = fg_color if isinstance(fg_color, str) else fg_color.name()
            if bold is not None: fmt['bold'] = bold
            
            # Use REPLACE (UPSERT simulation for older SQLite or simple replacement)
            cursor.execute("DELETE FROM pboq_formatting WHERE row_idx=? AND col_idx=?", (global_row_idx, col_idx))
            cursor.execute("INSERT INTO pboq_formatting (row_idx, col_idx, fmt_json) VALUES (?, ?, ?)", 
                         (global_row_idx, col_idx, json.dumps(fmt)))
            
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error persisting cell formatting: {e}")

    def _clear_cell_formatting(self, global_row_idx, col_idx):
        """Removes formatting for a specific cell from the DB."""
        file_path = self.pboq_file_selector.currentData()
        if not file_path or not os.path.exists(file_path): return
        try:
            conn = sqlite3.connect(file_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM pboq_formatting WHERE row_idx=? AND col_idx=?", (global_row_idx, col_idx))
            conn.commit()
            conn.close()
        except: pass

    def _sync_live_links(self, updates):
        """Propagates changes from source cells to destination cells."""
        if self.is_syncing_links: return
        self.is_syncing_links = True
        
        amount_idx = self.cb_bill_amount.currentIndex() - 1
        if amount_idx < 0: 
            self.is_syncing_links = False
            return

        cascading_updates = [] # (rowid, val)
        
        for source_rowid, new_val in updates:
            if source_rowid in self.active_links:
                for dest_rowid in self.active_links[source_rowid]:
                    # Update the UI
                    self._update_cell_by_rowid(dest_rowid, amount_idx, new_val)
                    cascading_updates.append((dest_rowid, new_val))
        
        if cascading_updates:
            # Recursively persist and sync
            self._persist_batch_updates(amount_idx, cascading_updates)
            
        self.is_syncing_links = False

    def _update_cell_by_rowid(self, rowid, col_idx, val):
        """Finds a cell by rowid across all tabs and updates its value and style."""
        for tab_idx in range(self.tabs.count()):
            table = self.tabs.widget(tab_idx)
            if not isinstance(table, QTableWidget): continue
            
            for row in range(table.rowCount()):
                item0 = table.item(row, 0)
                if item0 and item0.data(Qt.ItemDataRole.UserRole) == rowid:
                    item = table.item(row, col_idx)
                    if not item:
                        item = QTableWidgetItem()
                        table.setItem(row, col_idx, item)
                    
                    item.setText(str(val) if val is not None else "")
                    item.setForeground(QColor("#777777"))
                    item.setBackground(QColor("yellow"))
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

                    return

    def _clear_gross_and_code(self):

        """Globally clears all Gross Rate and Rate Code data from the UI and Database."""
        reply = QMessageBox.question(self, "Confirm Clear", 
                                   "Are you sure you want to clear ALL Gross Rates and Rate Codes from every sheet?\n\nThis action cannot be undone.",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.No:
            return
            
        file_path = self.pboq_file_selector.currentData()
        if not file_path or not os.path.exists(file_path):
            return

        # 1. Update Database
        try:
            conn = sqlite3.connect(file_path)
            cursor = conn.cursor()
            
            # Check if columns exist before updating
            cursor.execute("PRAGMA table_info(pboq_items)")
            cols = [info[1] for info in cursor.fetchall()]
            
            if "GrossRate" in cols or "RateCode" in cols:
                updates = []
                if "GrossRate" in cols: updates.append("GrossRate = ''")
                if "RateCode" in cols: updates.append("RateCode = ''")
                
                sql = f"UPDATE pboq_items SET {', '.join(updates)}"
                cursor.execute(sql)
                conn.commit()
            conn.close()
        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"Failed to clear database data:\n{e}")
            return

        # 2. Update UI (All Tabs)
        rate_idx = self.cb_rate.currentIndex() - 1
        code_idx = self.cb_rate_code.currentIndex() - 1
        
        for tab_idx in range(self.tabs.count()):
            table = self.tabs.widget(tab_idx)
            if not isinstance(table, QTableWidget):
                continue
            
            for row in range(table.rowCount()):
                if rate_idx >= 0:
                    item = table.item(row, rate_idx)
                    if item: item.setText("")
                if code_idx >= 0:
                    item = table.item(row, code_idx)
                    if item: item.setText("")

        self._update_stats()
        QMessageBox.information(self, "Success", "All Gross Rates and Rate Codes have been cleared.")

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

    def _get_state_file_path(self, file_index=None):
        """Returns the state file path for the currently loaded PBOQ."""
        states_folder = os.path.join(self.project_dir, "PBOQ States")
        os.makedirs(states_folder, exist_ok=True)
        
        # Use the PBOQ filename as the state key
        if file_index is None:
            file_index = self.pboq_file_selector.currentIndex()
            
        if file_index < 0:
            return None
            
        pboq_file = self.pboq_file_selector.itemText(file_index)
        if not pboq_file:
            return None
        state_file = os.path.join(states_folder, pboq_file + ".state.json")
        return state_file

    def _save_viewer_state(self):
        """Saves the last selected bill filename to a viewer state file."""
        states_folder = os.path.join(self.project_dir, "PBOQ States")
        os.makedirs(states_folder, exist_ok=True)
        viewer_state_file = os.path.join(states_folder, "viewer_state.json")
        
        state = {
            'last_bill': self.pboq_file_selector.currentText()
        }
        
        try:
            with open(viewer_state_file, 'w') as f:
                json.dump(state, f)
        except Exception:
            pass

    def _load_viewer_state(self):
        """Loads the last selected bill filename from the viewer state file."""
        states_folder = os.path.join(self.project_dir, "PBOQ States")
        viewer_state_file = os.path.join(states_folder, "viewer_state.json")
        
        if not os.path.exists(viewer_state_file):
            return None
            
        try:
            with open(viewer_state_file, 'r') as f:
                state = json.load(f)
                return state.get('last_bill')
        except Exception:
            return None

    def _update_column_headers(self):
        """Updates all table column headers to show mapping labels, blue color, and bold font."""
        mappings = {
            self.cb_ref: "Ref / Item No",
            self.cb_desc: "Description",
            self.cb_qty: "Quantity",
            self.cb_unit: "Unit",
            self.cb_bill_rate: "Bill Rate",
            self.cb_bill_amount: "Bill Amount",
            self.cb_rate: "Gross Rate",
            self.cb_rate_code: "Rate Code"
        }
        
        # Build a map of column_index -> list of labels
        col_to_labels = {}
        for cb, label in mappings.items():
            idx = cb.currentIndex() - 1 # -1 because of "-- Select Column --"
            if idx >= 0:
                if idx not in col_to_labels:
                    col_to_labels[idx] = []
                col_to_labels[idx].append(label)
        
        for tab_idx in range(self.tabs.count()):
            table = self.tabs.widget(tab_idx)
            if isinstance(table, QTableWidget):
                num_cols = table.columnCount()
                for c in range(num_cols):
                    header_item = table.horizontalHeaderItem(c)
                    if not header_item:
                        header_item = QTableWidgetItem(f"Column {c}")
                        table.setHorizontalHeaderItem(c, header_item)
                    
                    if c in col_to_labels:
                        labels = " & ".join(col_to_labels[c])
                        header_item.setText(labels)
                        header_item.setForeground(QColor("#0000FF")) # Solid Blue
                        font = header_item.font()
                        font.setBold(True)
                        header_item.setFont(font)
                    else:
                        header_item.setText(f"Column {c}")
                        header_item.setForeground(QColor("#303133")) # Default Dark Gray
                        font = header_item.font()
                        font.setBold(False)
                        header_item.setFont(font)
                
                # Force refresh of header to be sure
                table.horizontalHeader().viewport().update()
        
        # Update Extend checkboxes labels
        extend_cbs = [self.extend_cb0, self.extend_cb1, self.extend_cb2, self.extend_cb3]
        for i, cb in enumerate(extend_cbs):
            if i in col_to_labels:
                cb.setText(" & ".join(col_to_labels[i]))
            else:
                cb.setText(f"Column {i}")

        # Apply cell-level styling for mapped columns
        self._apply_column_cell_styles()

    def _apply_column_cell_styles(self):
        """Applies gray color and 2-decimal comma-separated formatting to Bill Rate and Bill Amount columns."""
        rate_idx = self.cb_bill_rate.currentIndex() - 1
        amount_idx = self.cb_bill_amount.currentIndex() - 1
        
        target_indices = []
        if rate_idx >= 0: target_indices.append(rate_idx)
        if amount_idx >= 0: target_indices.append(amount_idx)
        
        if not target_indices:
            return
            
        for tab_idx in range(self.tabs.count()):
            table = self.tabs.widget(tab_idx)
            if not isinstance(table, QTableWidget):
                continue
                
            for row in range(table.rowCount()):
                for col_idx in target_indices:
                    item = table.item(row, col_idx)
                    if item:
                        text = item.text().strip()
                        if text:
                            # 1. Format text
                            try:
                                clean_text = text.replace(',', '').replace(' ', '')
                                if clean_text:
                                    val = float(clean_text)
                                    formatted_text = "{:,.2f}".format(val)
                                    if text != formatted_text:
                                        item.setText(formatted_text)
                            except ValueError:
                                pass
                        
                        # 2. Set foreground to gray
                        item.setForeground(QColor("#777777"))
                        item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)


    def _save_pboq_state(self):
        """Persists column mapping, format, and search scope to a JSON file."""
        state_file = self._get_state_file_path()
        if not state_file:
            return
        
        state = {
            'cb_ref': self.cb_ref.currentIndex(),
            'cb_desc': self.cb_desc.currentIndex(),
            'cb_qty': self.cb_qty.currentIndex(),
            'cb_unit': self.cb_unit.currentIndex(),
            'cb_bill_rate': self.cb_bill_rate.currentIndex(),
            'cb_bill_amount': self.cb_bill_amount.currentIndex(),
            'cb_rate': self.cb_rate.currentIndex(),
            'cb_rate_code': self.cb_rate_code.currentIndex(),
            'wrap_text': self.wrap_text_enabled,
            'search_all_sheets': self.search_all_sheets.isChecked(),
            'active_tab': self.tabs.currentIndex(),
            'extend_cb0': self.extend_cb0.isChecked(),
            'extend_cb1': self.extend_cb1.isChecked(),
            'extend_cb2': self.extend_cb2.isChecked(),
            'extend_cb3': self.extend_cb3.isChecked(),
            'collect_desc': self.collect_desc_cb.isChecked(),
            'collect_amount': self.collect_amount_cb.isChecked(),
            'collect_keyword': self.collect_search_bar.text(),
            'collect_active': self.collect_btn.text() == "Revert",
            'extend_active': self.extend_btn.text() == "Revert",
            'dummy_rate': self.dummy_rate_spin.value(),
            'collect_target': self.collection_target_bar.text(),
            'populate_active': self.populate_btn.text() == "Un-Populate",
            'summary_desc': self.summary_desc_cb.isChecked(),
            'summary_amount': self.summary_amount_cb.isChecked(),
            'summary_target': self.summary_target_bar.text(),
        }



        
        try:
            with open(state_file, 'w') as f:
                json.dump(state, f)
        except Exception:
            pass  # Silently fail on save

    def _on_tab_changed(self, index):
        """Handles tab changes: saves state and ensures correct row heights for the visible tab."""
        self._save_pboq_state()
        
        table = self.tabs.widget(index)
        if isinstance(table, QTableWidget):
            if self.wrap_text_enabled:
                # Force row height recalculation based on actual visible width
                table.resizeRowsToContents()
            else:
                table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
                table.verticalHeader().setDefaultSectionSize(24)
                table.verticalHeader().setMinimumSectionSize(24)

    def _load_pboq_state(self, file_index=None):
        """Restores column mapping, format, and search scope from a saved JSON file."""
        state_file = self._get_state_file_path(file_index)
        if not state_file or not os.path.exists(state_file):
            return
        
        try:
            with open(state_file, 'r') as f:
                state = json.load(f)
            
            # 1. Restore column mappings
            combos = {
                'cb_ref': self.cb_ref, 'cb_desc': self.cb_desc,
                'cb_qty': self.cb_qty, 'cb_unit': self.cb_unit,
                'cb_bill_rate': self.cb_bill_rate, 'cb_bill_amount': self.cb_bill_amount,
                'cb_rate': self.cb_rate, 'cb_rate_code': self.cb_rate_code,
            }
            for key, cb in combos.items():
                if key in state:
                    cb.blockSignals(True)
                    cb.setCurrentIndex(state[key])
                    cb.blockSignals(False)
            
            # 2. Restore search scope
            self.search_this_sheet.blockSignals(True)
            self.search_all_sheets.blockSignals(True)
            if state.get('search_all_sheets', False):
                self.search_all_sheets.setChecked(True)
                self.search_this_sheet.setChecked(False)
            else:
                self.search_this_sheet.setChecked(True)
                self.search_all_sheets.setChecked(False)
            self.search_this_sheet.blockSignals(False)
            self.search_all_sheets.blockSignals(False)

            # 3. Restore Extend checkboxes
            extend_cbs = [self.extend_cb0, self.extend_cb1, self.extend_cb2, self.extend_cb3]
            for i, cb in enumerate(extend_cbs):
                key = f'extend_cb{i}'
                if key in state:
                    cb.blockSignals(True)
                    cb.setChecked(state[key])
                    cb.blockSignals(False)

            # Restore Collect checkboxes
            if 'collect_desc' in state:
                self.collect_desc_cb.blockSignals(True)
                self.collect_desc_cb.setChecked(state['collect_desc'])
                self.collect_desc_cb.blockSignals(False)
            if 'collect_amount' in state:
                self.collect_amount_cb.blockSignals(True)
                self.collect_amount_cb.setChecked(state['collect_amount'])
                self.collect_amount_cb.blockSignals(False)
            if 'collect_keyword' in state:
                self.collect_search_bar.blockSignals(True)
                self.collect_search_bar.setText(state['collect_keyword'])
                self.collect_search_bar.blockSignals(False)
            if 'collect_target' in state:
                self.collection_target_bar.blockSignals(True)
                self.collection_target_bar.setText(state['collect_target'])
                self.collection_target_bar.blockSignals(False)

            if 'summary_desc' in state:
                self.summary_desc_cb.blockSignals(True)
                self.summary_desc_cb.setChecked(state['summary_desc'])
                self.summary_desc_cb.blockSignals(False)
            if 'summary_amount' in state:
                self.summary_amount_cb.blockSignals(True)
                self.summary_amount_cb.setChecked(state['summary_amount'])
                self.summary_amount_cb.blockSignals(False)
            if 'summary_target' in state:
                self.summary_target_bar.blockSignals(True)
                self.summary_target_bar.setText(state['summary_target'])
                self.summary_target_bar.blockSignals(False)


            # 4. Restore Dummy Rate
            if 'dummy_rate' in state:
                self.dummy_rate_spin.blockSignals(True)
                self.dummy_rate_spin.setValue(float(state['dummy_rate']))
                self.dummy_rate_spin.blockSignals(False)

            # 4. Restore active tab
            if 'active_tab' in state and state['active_tab'] < self.tabs.count():
                self.tabs.blockSignals(True)
                self.tabs.setCurrentIndex(state['active_tab'])
                self.tabs.blockSignals(False)
            
            # 5. Re-apply UI refinements (Stretching columns affects wrapping)
            desc_mapped = self.cb_desc.currentIndex() - 1
            for tab_idx in range(self.tabs.count()):
                table = self.tabs.widget(tab_idx)
                if isinstance(table, QTableWidget) and desc_mapped >= 0 and desc_mapped < table.columnCount():
                    table.horizontalHeader().setSectionResizeMode(desc_mapped, QHeaderView.ResizeMode.Stretch)
            
            # 5. Restore wrap text state (Must be AFTER column stretching for correct height calculation)
            wrap_val = state.get('wrap_text', False)
            self.wrap_text_enabled = wrap_val
            self.wrap_text_btn.blockSignals(True)
            self.wrap_text_btn.setChecked(wrap_val)
            self.wrap_text_btn.setText("Unwrap Text" if wrap_val else "Wrap Text")
            self.wrap_text_btn.blockSignals(False)
            
            for tab_idx in range(self.tabs.count()):
                table = self.tabs.widget(tab_idx)
                if isinstance(table, QTableWidget):
                    table.setWordWrap(wrap_val)
                    if wrap_val:
                        table.verticalHeader().setMinimumSectionSize(24)
                        table.verticalHeader().setDefaultSectionSize(24)
                        table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
                    else:
                        table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
                        table.verticalHeader().setDefaultSectionSize(24)
                        table.verticalHeader().setMinimumSectionSize(24)
            
            # Update column headers and apply base styling
            self._update_column_headers()

            # Recalculate the active tab immediately
            self._on_tab_changed(self.tabs.currentIndex())
            
            # Re-apply highlights AFTER base styling to ensure they stay visible
            if state.get('collect_active', False):
                self._apply_collect_highlights()
            
            if state.get('populate_active', False):
                self._apply_populate_highlights()
            
            self._apply_summary_highlights()
            
            # Restore button states
            if state.get('extend_active', False):
                self.extend_btn.setText("Revert")
            else:
                self.extend_btn.setText("Extend")
            
            if state.get('populate_active', False):
                self.populate_btn.setText("Un-Populate")
            else:
                self.populate_btn.setText("Populate")



            
            self._update_stats()
            
        except Exception as e:
            print(f"Error loading PBOQ state: {e}")
            pass
