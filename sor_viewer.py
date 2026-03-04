import os
import sqlite3
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QSplitter, 
                             QListWidget, QTableWidget, QTableWidgetItem, 
                             QLabel, QMessageBox, QHeaderView, QListWidgetItem,
                             QLineEdit, QWidget, QCheckBox)
from PyQt6.QtCore import Qt

class SORDialog(QDialog):
    def __init__(self, project_dir, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self.project_dir = project_dir
        self.sor_folder = os.path.join(self.project_dir, "SOR")
        self.clipboard_data = None  # Store copied rate data
        
        self.setWindowTitle("Schedules of Rate (SOR)")
        self.setMinimumSize(900, 600)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Splitter to hold Left (List) and Right (Table)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setHandleWidth(4)
        self.splitter.setStyleSheet("QSplitter::handle { background-color: #cccccc; border-radius: 2px; }")
        
        # Left Panel (List of SORs)
        self.list_widget = QListWidget()
        self.list_widget.itemChanged.connect(self._load_selected_sor)
        self.splitter.addWidget(self.list_widget)
        
        # Right Panel (Layout containing Search Bar and Table)
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # Search controls layout
        search_layout = QHBoxLayout()
        
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search...")
        self.search_bar.textChanged.connect(self._filter_table)
        search_layout.addWidget(self.search_bar)
        
        self.similar_checkbox = QCheckBox("Similar rates")
        self.similar_checkbox.stateChanged.connect(self._filter_table)
        search_layout.addWidget(self.similar_checkbox)
        
        self.keywords_label = QLabel("Keywords:")
        search_layout.addWidget(self.keywords_label)
        
        self.keywords_input = QLineEdit()
        self.keywords_input.setPlaceholderText("e.g. wall, brick, 150mm")
        self.keywords_input.textChanged.connect(self._filter_table)
        search_layout.addWidget(self.keywords_input)
        
        right_layout.addLayout(search_layout)
        
        # Stats layout
        stats_layout = QVBoxLayout()
        stats_layout.setSpacing(2)
        self.total_rates_label = QLabel("Total Rates : 0")
        self.found_rates_label = QLabel("Found Rates : 0")
        
        # Style labels with specific colors
        self.total_rates_label.setStyleSheet("font-weight: bold; color: blue;")
        self.found_rates_label.setStyleSheet("font-weight: bold; color: green;")
        
        stats_layout.addWidget(self.total_rates_label)
        stats_layout.addWidget(self.found_rates_label)
        right_layout.addLayout(stats_layout)
        
        self.table_widget = QTableWidget()
        self.table_widget.setColumnCount(8)
        self.table_widget.setHorizontalHeaderLabels(["SOR", "Sheet", "Ref", "Description", "Quantity", "Unit", "Gross Rate", "Rate Code"])
        self.table_widget.verticalHeader().setVisible(False)
        self.table_widget.setAlternatingRowColors(True)
        self.table_widget.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table_widget.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        
        header = self.table_widget.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        
        self.table_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_widget.customContextMenuRequested.connect(self._show_context_menu)
        
        right_layout.addWidget(self.table_widget)
        self.splitter.addWidget(right_widget)
        
        # Set initial splitter sizes
        self.splitter.setSizes([200, 700])
        
        layout.addWidget(self.splitter)
        
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
        
        # Go-to Project Rates
        goto_project_action = QAction("Go-to Project Rates", self)
        goto_project_action.triggered.connect(self._goto_project_rates)
        menu.addAction(goto_project_action)
        
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
        gross_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
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

    def _goto_project_rates(self):
        if self.main_window:
            self.main_window.manage_rate_database()

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
        
        desc = item.text().strip() if item and item.text().strip() else "New Rate"
        unit = unit_item.text().strip() if unit_item and unit_item.text().strip() else "m"
        
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
            gross_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            
            rate_code_item = QTableWidgetItem(str(dialog.estimate.rate_code))
            
            self.table_widget.setItem(row, 6, gross_item)
            self.table_widget.setItem(row, 7, rate_code_item)
            
            # Persist to SOR DB
            self._persist_to_sor_db(row, formatted_gross, str(dialog.estimate.rate_code))
            
            self.table_widget.resizeColumnToContents(6)
            self.table_widget.resizeColumnToContents(7)
