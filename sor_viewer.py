import os
import sqlite3
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QSplitter, 
                             QListWidget, QTableWidget, QTableWidgetItem, 
                             QLabel, QMessageBox, QHeaderView, QListWidgetItem,
                             QLineEdit, QWidget, QCheckBox, QDockWidget, QScrollArea,
                             QFrame)
import pboq_constants as const

class SORToolsPane(QWidget):
    """Encapsulates the search, list, and stats for SOR into a dockable pane."""
    def __init__(self, owner):
        super().__init__()
        self.owner = owner
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        
        container = QWidget()
        container.setStyleSheet("font-size: 8pt;") # Smaller font for compact look
        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(5, 5, 5, 5)
        c_layout.setSpacing(8)

        # 1. Search Box
        search_group = QFrame()
        search_group.setFrameShape(QFrame.Shape.StyledPanel)
        s_layout = QVBoxLayout(search_group)
        s_layout.setContentsMargins(5, 5, 5, 5)
        s_layout.setSpacing(2)
        s_layout.addWidget(QLabel("<b>Universal Search:</b>"))
        self.owner.search_bar.setMaximumHeight(20)
        s_layout.addWidget(self.owner.search_bar)
        self.owner.similar_checkbox.setStyleSheet("margin-bottom: -4px;")
        s_layout.addWidget(self.owner.similar_checkbox)
        s_layout.addWidget(QLabel("<b>Keywords (csv):</b>"))
        self.owner.keywords_input.setMaximumHeight(20)
        s_layout.addWidget(self.owner.keywords_input)
        c_layout.addWidget(search_group)

        # 2. Stats
        stats_group = QFrame()
        stats_group.setFrameShape(QFrame.Shape.StyledPanel)
        st_layout = QVBoxLayout(stats_group)
        st_layout.setContentsMargins(5, 5, 5, 5)
        st_layout.setSpacing(2)
        st_layout.addWidget(QLabel("<b>Price Statistics:</b>"))
        st_layout.addWidget(self.owner.total_rates_label)
        st_layout.addWidget(self.owner.found_rates_label)
        st_layout.addWidget(self.owner.priced_rates_label)
        st_layout.addWidget(self.owner.outstanding_rates_label)
        c_layout.addWidget(stats_group)

        # 3. SOR Files
        list_group = QFrame()
        list_group.setFrameShape(QFrame.Shape.StyledPanel)
        l_layout = QVBoxLayout(list_group)
        l_layout.setContentsMargins(5, 5, 5, 5)
        l_layout.setSpacing(2)
        l_layout.addWidget(QLabel("<b>Available SORs:</b>"))
        self.owner.list_widget.setMinimumHeight(150)
        l_layout.addWidget(self.owner.list_widget)
        c_layout.addWidget(list_group)
        
        c_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll)

class SORDialog(QDialog):
    def __init__(self, project_dir, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self.project_dir = project_dir
        self.sor_folder = os.path.join(self.project_dir, "SOR")
        self.clipboard_data = None  # Store copied rate data
        
        self.setWindowTitle("Schedules of Rate (SOR)")
        self.setMinimumSize(950, 400)
        
    def _init_ui(self):
        # Create all tools first
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search all columns...")
        self.search_bar.textChanged.connect(self._filter_table)
        
        self.keywords_input = QLineEdit()
        self.keywords_input.setPlaceholderText("e.g. wall, brick")
        self.keywords_input.textChanged.connect(self._filter_table)
        
        self.similar_checkbox = QCheckBox("Similar rates (OR logic)")
        self.similar_checkbox.stateChanged.connect(self._filter_table)
        
        label_style = "font-weight: bold; font-size: 9pt;"
        self.total_rates_label = QLabel("Total: 0")
        self.found_rates_label = QLabel("Found: 0")
        self.priced_rates_label = QLabel("Priced: 0")
        self.outstanding_rates_label = QLabel("Outstanding: 0")
        
        self.total_rates_label.setStyleSheet(f"{label_style} color: #1565C0;")
        self.found_rates_label.setStyleSheet(f"{label_style} color: #2E7D32;")
        self.priced_rates_label.setStyleSheet(f"{label_style} color: #EF6C00;")
        self.outstanding_rates_label.setStyleSheet(f"{label_style} color: #C62828;")

        self.list_widget = QListWidget()
        self.list_widget.itemChanged.connect(self._load_selected_sor)
        
        # Main Table
        self.table_widget = QTableWidget()
        self.table_widget.setColumnCount(8)
        self.table_widget.setHorizontalHeaderLabels(["SOR", "Sheet", "Ref", "Description", "Quantity", "Unit", "Gross Rate", "Rate Code"])
        self.table_widget.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table_widget.setAlternatingRowColors(True)
        self.table_widget.verticalHeader().setVisible(False)
        self.table_widget.setShowGrid(False)
        
        header = self.table_widget.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft)
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        
        # Apply heading color and blue text using Palette
        header.setAutoFillBackground(True)
        palette = header.palette()
        palette.setColor(header.backgroundRole(), const.COLOR_HEADING)
        palette.setColor(header.foregroundRole(), Qt.GlobalColor.blue)
        palette.setColor(palette.ColorRole.Button, const.COLOR_HEADING)
        palette.setColor(palette.ColorRole.ButtonText, Qt.GlobalColor.blue)
        header.setPalette(palette)
        
        self.table_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_widget.customContextMenuRequested.connect(self._show_context_menu)

        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 10)
        layout.addWidget(self.table_widget)

        # Tools Pane in Dock
        self.tools_pane = SORToolsPane(self)
        if self.main_window:
            self.tools_dock = QDockWidget("SOR Tools", self.main_window)
            self.tools_dock.setWidget(self.tools_pane)
            self.main_window.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.tools_dock)
            self.main_window.mdi_area.subWindowActivated.connect(self._on_mdi_subwindow_activated)
            self.destroyed.connect(self._cleanup_tools_dock)
        
        self._populate_list()

    def _populate_list(self):
        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        if not os.path.exists(self.sor_folder):
            self.list_widget.blockSignals(False)
            return
            
        for f in os.listdir(self.sor_folder):
            if f.lower().endswith('.db'):
                item = QListWidgetItem(f)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Unchecked)
                self.list_widget.addItem(item)
        self.list_widget.blockSignals(False)

    def _load_selected_sor(self):
        self.table_widget.setRowCount(0)
        
        checked_items = []
        for index in range(self.list_widget.count()):
            item = self.list_widget.item(index)
            if item.checkState() == Qt.CheckState.Checked:
                checked_items.append(item)
        
        if not checked_items:
            self.total_rates_label.setText("Total Rates : 0")
            self.found_rates_label.setText("Found Rates : 0")
            return
            
        all_rows = []
        for item in checked_items:
            filename = item.text()
            file_path = os.path.join(self.sor_folder, filename)
            
            if not os.path.exists(file_path):
                QMessageBox.warning(self, "Error", f"Selected file {filename} no longer exists.")
                continue
                
            try:
                conn = sqlite3.connect(file_path)
                cursor = conn.cursor()
                
                # Check if table 'sor_items' exists
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sor_items';")
                if not cursor.fetchone():
                    QMessageBox.warning(self, "Format Error", f"The database {filename} does not contain valid SOR data.")
                    conn.close()
                    continue
                    
                sor_name = filename[:-3] if filename.lower().endswith('.db') else filename
                # Fetch including Gross Rate and Rate Code if they exist
                cursor.execute("PRAGMA table_info(sor_items)")
                columns = [info[1] for info in cursor.fetchall()]
                
                query = "SELECT Sheet, Ref, Description, Quantity, Unit"
                if "GrossRate" in columns: query += ", GrossRate"
                else: query += ", NULL"
                if "RateCode" in columns: query += ", RateCode"
                else: query += ", NULL"
                query += " FROM sor_items"
                
                cursor.execute(query)
                rows = cursor.fetchall()
                
                for r in rows:
                    all_rows.append((sor_name,) + r)
                    
                conn.close()
                
            except sqlite3.DatabaseError as e:
                QMessageBox.warning(self, "Database Error", f"Failed to read data from {filename}:\n{e}")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to load data from {filename}:\n{e}")

        self.table_widget.setRowCount(len(all_rows))
        for row_idx, row_data in enumerate(all_rows):
            for col_idx, col_val in enumerate(row_data):
                t_item = QTableWidgetItem(str(col_val) if col_val is not None else "")
                if col_idx == 6: # Gross Rate
                    t_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                self.table_widget.setItem(row_idx, col_idx, t_item)
                
        self.total_rates_label.setText(f"Total Rates : {len(all_rows)}")
        
        for i in range(self.table_widget.columnCount()):
            if i != 3:
                self.table_widget.resizeColumnToContents(i)
        
        total_w = self.table_widget.viewport().width()
        used_w = sum(self.table_widget.columnWidth(i) for i in range(self.table_widget.columnCount()) if i != 3)
        self.table_widget.setColumnWidth(3, max(250, total_w - used_w))

        self._filter_table()

    def _filter_table(self, *args):
        search_text = self.search_bar.text().lower()
        keywords_text = self.keywords_input.text().lower()
        similar_checked = self.similar_checkbox.isChecked()
        
        keywords = [k.strip() for k in keywords_text.split(',') if k.strip()]

        found_count = 0

        for row in range(self.table_widget.rowCount()):
            row_visible = True
            
            row_texts = []
            for col in range(self.table_widget.columnCount()):
                item = self.table_widget.item(row, col)
                if item:
                    row_texts.append(item.text().lower())
            
            full_row_text = " ".join(row_texts)
            
            if search_text and search_text not in full_row_text:
                row_visible = False
                
            if row_visible and keywords:
                if similar_checked:
                    # OR logic: at least one keyword must be present
                    if not any(kw in full_row_text for kw in keywords):
                        row_visible = False
                else:
                    # AND logic: all keywords must be present
                    if not all(kw in full_row_text for kw in keywords):
                        row_visible = False
                        
            self.table_widget.setRowHidden(row, not row_visible)
            if row_visible:
                found_count += 1
                
        if not search_text and not keywords:
            self.found_rates_label.setText("Found Rates : 0")
        else:
            self.found_rates_label.setText(f"Found Rates : {found_count}")
        
        self._update_priced_stats()

    def _update_priced_stats(self):
        """Calculates and updates labels for priced vs outstanding rates."""
        total = self.table_widget.rowCount()
        priced = 0
        for row in range(total):
            item = self.table_widget.item(row, 6) # Gross Rate column
            if item and item.text().strip():
                priced += 1
        
        outstanding = total - priced
        self.priced_rates_label.setText(f"Priced Rates : {priced}")
        self.outstanding_rates_label.setText(f"Outstanding Rates : {outstanding}")

    def _show_context_menu(self, pos):
        from PyQt6.QtWidgets import QMenu
        from PyQt6.QtGui import QAction
        
        selected_indexes = self.table_widget.selectionModel().selectedRows()
        if not selected_indexes:
            return
            
        index = selected_indexes[0]
        row = index.row()
        
        menu = QMenu(self)
        
        # Build/Edit Rate
        rate_code = self.table_widget.item(row, 7).text().strip()
        action_text = "Edit Rate" if rate_code else "Build Rate"
        build_rate_action = QAction(action_text, self)
        build_rate_action.triggered.connect(lambda: self._build_rate(index))
        menu.addAction(build_rate_action)
        
        # Clear Rate
        clear_rate_action = QAction("Clear Rate", self)
        clear_rate_action.triggered.connect(lambda: self._clear_rate(index))
        menu.addAction(clear_rate_action)
        
        menu.addSeparator()
        
        # Copy Rate
        copy_action = QAction("Copy Rate", self)
        copy_action.triggered.connect(lambda: self._copy_rate(index))
        menu.addAction(copy_action)
        
        # Multi-Copy Rates
        if len(selected_indexes) > 1:
            multi_copy_action = QAction(f"Multi-Copy Rates ({len(selected_indexes)})", self)
            multi_copy_action.triggered.connect(self._multi_copy_rates)
            menu.addAction(multi_copy_action)
            
        # Paste Rate
        paste_action = QAction("Paste Rate", self)
        # Check if clipboard has data and unit matches
        if self.clipboard_data:
            paste_action.setEnabled(True)
        else:
            paste_action.setEnabled(False)
        paste_action.triggered.connect(lambda: self._paste_rate(index))
        menu.addAction(paste_action)
        
        menu.addSeparator()
        
        # Go-To Rate
        goto_rate_action = QAction("Go-To Rate", self)
        goto_rate_action.setEnabled(bool(rate_code))
        goto_rate_action.triggered.connect(lambda: self._goto_project_rates(rate_code))
        menu.addAction(goto_rate_action)
        
        menu.exec(self.table_widget.viewport().mapToGlobal(pos))

    def _copy_rate(self, index):
        row = index.row()
        self.clipboard_data = {
            'gross_rate': self.table_widget.item(row, 6).text(),
            'rate_code': self.table_widget.item(row, 7).text(),
            'unit': self.table_widget.item(row, 5).text()
        }
        if self.main_window:
            self.main_window.statusBar().showMessage(f"Rate {self.clipboard_data['rate_code']} copied to clipboard.", 3000)

    def _multi_copy_rates(self):
        # Implementation for multiple rates could be a list in clipboard_data
        selected_indexes = self.table_widget.selectionModel().selectedRows()
        self.clipboard_data = []
        for idx in selected_indexes:
            row = idx.row()
            self.clipboard_data.append({
                'gross_rate': self.table_widget.item(row, 6).text(),
                'rate_code': self.table_widget.item(row, 7).text(),
                'unit': self.table_widget.item(row, 5).text()
            })
        if self.main_window:
            self.main_window.statusBar().showMessage(f"{len(self.clipboard_data)} rates copied to clipboard.", 3000)

    def _paste_rate(self, index):
        if not self.clipboard_data:
            return
            
        row = index.row()
        target_unit = self.table_widget.item(row, 5).text().strip()
        
        # Support both single and multi paste (using first item for simplicity if single paste triggered)
        data = self.clipboard_data if isinstance(self.clipboard_data, dict) else self.clipboard_data[0]
        
        if data['unit'].strip().lower() != target_unit.lower():
            QMessageBox.warning(self, "Unit Mismatch", 
                                f"Cannot paste rate. Units do not match!\n\n"
                                f"Source: {data['unit']}\nTarget: {target_unit}")
            return
            
        # Update Table UI
        gross_item = QTableWidgetItem(data['gross_rate'])
        gross_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        rate_code_item = QTableWidgetItem(data['rate_code'])
        
        self.table_widget.setItem(row, 6, gross_item)
        self.table_widget.setItem(row, 7, rate_code_item)
        
        # Persist to SOR DB
        self._persist_to_sor_db(row, data['gross_rate'], data['rate_code'])
        
        if self.main_window:
            self.main_window.statusBar().showMessage("Rate pasted and persisted to SOR database.", 3000)

    def _clear_rate(self, index):
        row = index.row()
        desc = self.table_widget.item(row, 3).text()
        
        reply = QMessageBox.question(self, "Clear Rate", 
                                   f"Are you sure you want to clear the Gross Rate and Rate Code for:\n\n{desc}?",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                   QMessageBox.StandardButton.No)
                                   
        if reply == QMessageBox.StandardButton.Yes:
            # Update Table UI
            self.table_widget.setItem(row, 6, QTableWidgetItem("")) # Gross Rate
            self.table_widget.setItem(row, 7, QTableWidgetItem("")) # Rate Code
            
            # Persist to SOR DB
            self._persist_to_sor_db(row, "", "")
            
            if self.main_window:
                self.main_window.statusBar().showMessage("Rate cleared and persisted to SOR database.", 3000)

    def _goto_project_rates(self, rate_code):
        if self.main_window and rate_code:
            self.main_window.show_rate_in_database(rate_code)

    def _persist_to_sor_db(self, row, gross_rate, rate_code):
        """Persists the Gross Rate and Rate Code back to the original SOR SQLite database."""
        sor_name = self.table_widget.item(row, 0).text()
        sheet = self.table_widget.item(row, 1).text()
        ref = self.table_widget.item(row, 2).text()
        desc = self.table_widget.item(row, 3).text()
        
        file_path = os.path.join(self.sor_folder, f"{sor_name}.db")
        if not os.path.exists(file_path):
            return
            
        try:
            conn = sqlite3.connect(file_path)
            cursor = conn.cursor()
            
            # Ensure columns exist
            cursor.execute("PRAGMA table_info(sor_items)")
            cols = [info[1] for info in cursor.fetchall()]
            
            if "GrossRate" not in cols:
                cursor.execute("ALTER TABLE sor_items ADD COLUMN GrossRate TEXT")
            if "RateCode" not in cols:
                cursor.execute("ALTER TABLE sor_items ADD COLUMN RateCode TEXT")
                
            # Update the specific row. We use Sheet, Ref, and Description as unique identifiers
            cursor.execute("""
                UPDATE sor_items 
                SET GrossRate = ?, RateCode = ? 
                WHERE Sheet = ? AND Ref = ? AND Description = ?
            """, (gross_rate, rate_code, sheet, ref, desc))
            
            conn.commit()
            conn.close()
        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"Failed to persist SOR data:\n{e}")
        
    def _build_rate(self, index):
        row = index.row()
        item = self.table_widget.item(row, 3) # Description column
        unit_item = self.table_widget.item(row, 5) # Unit column
        rate_code_item = self.table_widget.item(row, 7) # Rate Code column
        
        desc = item.text().strip() if item and item.text().strip() else "New Rate"
        unit = unit_item.text().strip() if unit_item and unit_item.text().strip() else "m"
        rate_code = rate_code_item.text().strip() if rate_code_item else ""
        
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
            
            gross_item = QTableWidgetItem(formatted_gross)
            gross_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            
            rate_code_item = QTableWidgetItem(str(dialog.estimate.rate_code))
            
            self.table_widget.setItem(row, 6, gross_item)
            self.table_widget.setItem(row, 7, rate_code_item)
            
            # Persist to SOR DB
            self._persist_to_sor_db(row, formatted_gross, str(dialog.estimate.rate_code))
            
            self.table_widget.resizeColumnToContents(6)
            self.table_widget.resizeColumnToContents(7)

    def _price_sor_with_rate(self, rate_desc, gross_rate, rate_code):
        """Searches the SOR table for a matching description and updates it."""
        found_count = 0
        for row in range(self.table_widget.rowCount()):
            sor_desc_item = self.table_widget.item(row, 3)
            if sor_desc_item and sor_desc_item.text().strip().lower() == rate_desc.strip().lower():
                # Update UI
                gross_item = QTableWidgetItem(f"{gross_rate:,.2f}")
                gross_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                self.table_widget.setItem(row, 6, gross_item)
                self.table_widget.setItem(row, 7, QTableWidgetItem(rate_code))
                
                # Persist to DB
                self._persist_to_sor_db(row, f"{gross_rate:,.2f}", rate_code)
                found_count += 1
        
        if found_count > 0:
            self.table_widget.resizeColumnToContents(6)
            self.table_widget.resizeColumnToContents(7)
        return found_count

    def _get_active_keywords(self):
        """Returns the list of keywords currently entered in the SOR search bar."""
        keywords_text = self.keywords_input.text().lower()
        return [k.strip() for k in keywords_text.split(',') if k.strip()]

    def _price_sor_with_keywords(self, gross_rate, rate_code):
        """Prices items in the SOR that match the currently entered keywords."""
        keywords = self._get_active_keywords()
        if not keywords:
            return -1 # Special code for missing keywords
            
        found_count = 0
        similar_checked = self.similar_checkbox.isChecked()
        
        for row in range(self.table_widget.rowCount()):
            # We match against the full row text just like the filter does
            row_texts = []
            for col in range(self.table_widget.columnCount()):
                item = self.table_widget.item(row, col)
                if item:
                    row_texts.append(item.text().lower())
            
            full_row_text = " ".join(row_texts)
            
            match = False
            if similar_checked:
                if any(kw in full_row_text for kw in keywords):
                    match = True
            else:
                if all(kw in full_row_text for kw in keywords):
                    match = True
                    
            if match:
                # Update UI
                gross_item = QTableWidgetItem(f"{gross_rate:,.2f}")
                gross_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                self.table_widget.setItem(row, 6, gross_item)
                self.table_widget.setItem(row, 7, QTableWidgetItem(rate_code))
                
                # Persist to DB
                self._persist_to_sor_db(row, f"{gross_rate:,.2f}", rate_code)
                found_count += 1
                
        if found_count > 0:
            self.table_widget.resizeColumnToContents(6)
            self.table_widget.resizeColumnToContents(7)
        return found_count

    def _on_mdi_subwindow_activated(self, sub):
        """Toggle dock visibility based on whether THIS window is active."""
        if not hasattr(self, 'tools_dock') or not self.tools_dock:
            return
        
        if sub and sub.widget() == self:
            self.tools_dock.show()
            self.tools_dock.raise_()
        else:
            self.tools_dock.hide()

    def closeEvent(self, event):
        """Ensure the dock is hidden when closing."""
        try:
            if hasattr(self, 'tools_dock') and self.tools_dock:
                self.tools_dock.hide()
        except RuntimeError:
            pass
        super().closeEvent(event)

    def _cleanup_tools_dock(self):
        """Cleanup dock widget when viewer is destroyed."""
        if self.main_window:
            try:
                if hasattr(self, 'tools_dock') and self.tools_dock:
                    self.main_window.removeDockWidget(self.tools_dock)
                    self.tools_dock.deleteLater()
                    self.tools_dock = None
            except RuntimeError:
                pass
