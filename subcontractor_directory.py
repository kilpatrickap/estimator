import os
import sqlite3
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                             QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
                             QMessageBox, QAbstractItemView)
from PyQt6.QtCore import Qt
from pboq_logic import PBOQLogic

class SubcontractorDirectoryDialog(QDialog):
    def __init__(self, pboq_db_path, project_dir, parent=None):
        super().__init__(parent)
        self.pboq_db_path = pboq_db_path
        self.project_dir = project_dir
        self.setWindowTitle("Subcontractor Directory")
        self.resize(850, 500)
        self._init_ui()
        self._load_data()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        
        # Top Bar
        top_bar = QHBoxLayout()
        top_bar.addWidget(QLabel("Search Directory:"))
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Type a name or email...")
        self.search_input.textChanged.connect(self._filter_table)
        top_bar.addWidget(self.search_input)
        
        top_bar.addStretch()
        
        self.delete_btn = QPushButton("Delete Selected")
        self.delete_btn.setStyleSheet("color: #d32f2f;")  # Optional: Make it red
        self.delete_btn.clicked.connect(self._delete_selected)
        top_bar.addWidget(self.delete_btn)
        
        layout.addLayout(top_bar)
        
        # Main Table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Name", "Phone", "Email", "Assigned Packages (Project-Wide)"])
        
        # Styling for Excel-like view
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setDefaultSectionSize(28)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        
        self.table.setColumnWidth(0, 200)
        self.table.setColumnWidth(1, 150)
        self.table.setColumnWidth(2, 200)
        
        layout.addWidget(self.table)
        
        # Bottom Bar
        bottom_bar = QHBoxLayout()
        bottom_bar.addStretch()
        
        self.save_btn = QPushButton("Save Changes")
        self.save_btn.clicked.connect(self._save_changes)
        bottom_bar.addWidget(self.save_btn)
        
        layout.addLayout(bottom_bar)

    def _get_all_pboq_dbs(self):
        """Find all PBOQ SQLite databases in the project's Priced BOQs folder."""
        pboq_folder = ""
        current = self.project_dir
        for _ in range(4):
            candidate = os.path.join(current, "Priced BOQs")
            if os.path.exists(candidate):
                pboq_folder = candidate
                break
            parent = os.path.dirname(current)
            if parent == current: break
            current = parent
            
        if not pboq_folder:
            return [self.pboq_db_path] if os.path.exists(self.pboq_db_path) else []
            
        return [os.path.join(pboq_folder, f) for f in os.listdir(pboq_folder) if f.lower().endswith('.db')]

    def _load_data(self):
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        
        # 1. Gather all Contact Details from current DB (assume it's the primary working file)
        directories = {} # name -> {phone, email}
        try:
            conn = sqlite3.connect(self.pboq_db_path)
            PBOQLogic.ensure_schema(conn)
            cursor = conn.cursor()
            cursor.execute("SELECT name, phone, email FROM subcontractor_details")
            for name, phone, email in cursor.fetchall():
                directories[name] = {"phone": phone or "", "email": email or ""}
            conn.close()
        except sqlite3.Error as e:
            print(f"Error loading details: {e}")
            
        # 2. Iterate through ALL project PBOQs to find assignments
        all_dbs = self._get_all_pboq_dbs()
        assignments = {} # name -> list of formal strings e.g. ["Waterproofing (2 items)"]
        
        # Dictionary to aggregate: name -> package -> integer count
        agg_counts = {}
        
        for db_file in all_dbs:
            try:
                conn = sqlite3.connect(db_file)
                cursor = conn.cursor()
                # Check if SubbeeName column exists first
                cursor.execute("PRAGMA table_info(pboq_items)")
                cols = [info[1] for info in cursor.fetchall()]
                
                if "SubbeeName" in cols and "SubbeePackage" in cols:
                    cursor.execute('''
                        SELECT "SubbeeName", "SubbeePackage", COUNT(*) 
                        FROM pboq_items 
                        WHERE "SubbeeName" IS NOT NULL AND "SubbeeName" != ''
                        GROUP BY "SubbeeName", "SubbeePackage"
                    ''')
                    for sub_name, pkg, count in cursor.fetchall():
                        # Make sure subcontractor is in directory even if missing contact info
                        if sub_name not in directories:
                            directories[sub_name] = {"phone": "", "email": ""}
                            
                        if sub_name not in agg_counts:
                            agg_counts[sub_name] = {}
                        if pkg not in agg_counts[sub_name]:
                            agg_counts[sub_name][pkg] = 0
                        agg_counts[sub_name][pkg] += count
                conn.close()
            except sqlite3.Error:
                pass
                
        # Format the assignment strings
        for sub_name, pkgs in agg_counts.items():
            formatted = []
            for pkg, count in pkgs.items():
                pkg_disp = pkg if pkg else "Unknown Package"
                item_str = "item" if count == 1 else "items"
                formatted.append(f"{pkg_disp} ({count} {item_str})")
            assignments[sub_name] = ", ".join(formatted)

        # 3. Populate Table
        self.table.setRowCount(len(directories))
        for row, (name, contact) in enumerate(sorted(directories.items())):
            # Name
            name_item = QTableWidgetItem(name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable) # Name acts as primary key
            self.table.setItem(row, 0, name_item)
            
            # Phone
            self.table.setItem(row, 1, QTableWidgetItem(contact["phone"]))
            
            # Email
            self.table.setItem(row, 2, QTableWidgetItem(contact["email"]))
            
            # Status / Assigned Packages
            status_str = assignments.get(name, "Unassigned")
            status_item = QTableWidgetItem(status_str)
            status_item.setFlags(status_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            
            # Visualize "Unassigned" slightly differently
            if status_str == "Unassigned":
                status_item.setForeground(Qt.GlobalColor.darkGray)
            
            self.table.setItem(row, 3, status_item)
            
        self.table.blockSignals(False)

    def _filter_table(self, text):
        search_text = text.lower()
        for row in range(self.table.rowCount()):
            name = self.table.item(row, 0).text().lower()
            email = self.table.item(row, 2).text().lower()
            if search_text in name or search_text in email:
                self.table.setRowHidden(row, False)
            else:
                self.table.setRowHidden(row, True)

    def _save_changes(self):
        all_dbs = self._get_all_pboq_dbs()
        updates = []
        for row in range(self.table.rowCount()):
            name = self.table.item(row, 0).text()
            phone = self.table.item(row, 1).text()
            email = self.table.item(row, 2).text()
            updates.append((name, phone, email))
            
        updated_count = 0
        for db_file in all_dbs:
            try:
                conn = sqlite3.connect(db_file)
                PBOQLogic.ensure_schema(conn)
                cursor = conn.cursor()
                for name, phone, email in updates:
                    cursor.execute("""
                        INSERT OR REPLACE INTO subcontractor_details (name, phone, email) 
                        VALUES (?, ?, ?)
                    """, (name, phone, email))
                conn.commit()
                conn.close()
                updated_count += 1
            except sqlite3.Error as e:
                print(f"Failed to save details to {db_file}: {e}")
                
        QMessageBox.information(self, "Saved", f"Contact details successfully synced across {updated_count} project files.")
        self.accept()

    def _delete_selected(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Please select a subcontractor to delete.")
            return
            
        name = self.table.item(row, 0).text()
        status = self.table.item(row, 3).text()
        
        if status != "Unassigned":
            QMessageBox.critical(self, "Cannot Delete", 
                               f"'{name}' is currently assigned to active work packages.\\n\\n"
                               "You must remove them from all packages before deleting their contact.")
            return
            
        reply = QMessageBox.question(self, "Confirm Delete", 
                                   f"Are you sure you want to completely delete '{name}' from the directory?",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                                   
        if reply == QMessageBox.StandardButton.Yes:
            all_dbs = self._get_all_pboq_dbs()
            for db_file in all_dbs:
                try:
                    conn = sqlite3.connect(db_file)
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM subcontractor_details WHERE name=?", (name,))
                    conn.commit()
                    conn.close()
                except sqlite3.Error:
                    pass
            self.table.removeRow(row)
