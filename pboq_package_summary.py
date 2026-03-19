import os
import sqlite3
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem, 
                             QPushButton, QHBoxLayout, QMessageBox, QHeaderView)
from PyQt6.QtCore import Qt, pyqtSignal

class PackageSummaryDialog(QDialog):
    dataChanged = pyqtSignal()

    def __init__(self, db_path, project_dir, pkg_col, markup_col, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.project_dir = project_dir
        self.pkg_col = pkg_col
        self.markup_col = markup_col
        self.sor_db = os.path.join(self.project_dir, "SOR", "Packages_SOR.db")
        self.setWindowTitle("Work Packages Management")
        self.setMinimumWidth(450)
        self.setMinimumHeight(400)
        self._ensure_sor_db()
        self._init_ui()
        self._load_data()

    def _ensure_sor_db(self):
        os.makedirs(os.path.join(self.project_dir, "SOR"), exist_ok=True)
        conn = sqlite3.connect(self.sor_db)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS packages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                PackageName TEXT UNIQUE,
                Markup REAL,
                Category TEXT,
                Subcontractor TEXT,
                LastUpdated DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        
        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Package Name", "Markup (%)"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(True)
        # Force column 1 to be slightly smaller
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setColumnWidth(1, 100)
        
        layout.addWidget(self.table)
        
        btn_layout = QHBoxLayout()
        self.sync_all_btn = QPushButton("Sync All PBOQs")
        self.sync_all_btn.setToolTip("Apply these markups to ALL PBOQ files in the project folder")
        self.sync_all_btn.clicked.connect(self._sync_to_all_pboqs)
        
        self.save_btn = QPushButton("Save Changes")
        self.save_btn.clicked.connect(self._save_changes)
        
        btn_layout.addWidget(self.sync_all_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.save_btn)
        layout.addLayout(btn_layout)
        
        self.table.itemChanged.connect(self._handle_item_changed)

    def _handle_item_changed(self, item):
        if item.column() == 1: # Markup column
            self.table.blockSignals(True)
            txt = item.text().replace(',', '').replace('%', '')
            try:
                f_val = float(txt) if txt else 0.0
                item.setText("{:,.2f}%".format(f_val))
            except:
                pass # Keep what user typed if invalid
            self.table.blockSignals(False)

    def _load_data(self):
        self.table.blockSignals(True)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            # Group by package name and find the most common markup (or max)
            # This handles cases where items in a package might have drifted during manual edits
            cursor.execute(f"""
                SELECT "{self.pkg_col}", MAX("{self.markup_col}") 
                FROM pboq_items 
                WHERE "{self.pkg_col}" IS NOT NULL AND "{self.pkg_col}" != ''
                GROUP BY "{self.pkg_col}"
                ORDER BY "{self.pkg_col}"
            """)
            rows = cursor.fetchall()
            self.table.setRowCount(len(rows))
            for i, (pkg, markup) in enumerate(rows):
                name_item = QTableWidgetItem(pkg)
                name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(i, 0, name_item)
                
                # Format markup as 2-decimal string
                try:
                    m_val = float(markup) if markup else 10.0
                except:
                    m_val = 10.0
                
                markup_item = QTableWidgetItem("{:,.2f}%".format(m_val))
                markup_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(i, 1, markup_item)
        except sqlite3.Error as e:
            print(f"Error loading packages summary: {e}")
        finally:
            conn.close()
            self.table.blockSignals(False)

    def _save_changes(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            for i in range(self.table.rowCount()):
                pkg = self.table.item(i, 0).text()
                raw_m = self.table.item(i, 1).text().replace(',', '').replace('%', '')
                try:
                    markup_val = float(raw_m)
                except ValueError:
                    markup_val = 10.0 # fallback
                
                # Apply this markup to all items in this package
                cursor.execute(f'UPDATE pboq_items SET "{self.markup_col}" = ? WHERE "{self.pkg_col}" = ?', (str(markup_val), pkg))
            
            conn.commit()
            
            # Sync to central SOR
            self._sync_to_sor()
            
            self.dataChanged.emit()
        except sqlite3.Error as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save changes: {e}")
        finally:
            conn.close()

    def _sync_to_sor(self):
        """Syncs all currently listed packages to the central Project SOR."""
        try:
            conn = sqlite3.connect(self.sor_db)
            cursor = conn.cursor()
            
            for i in range(self.table.rowCount()):
                pkg = self.table.item(i, 0).text()
                raw_m = self.table.item(i, 1).text().replace(',', '').replace('%', '')
                try:
                    markup_val = float(raw_m)
                except: markup_val = 0.0
                
                cursor.execute("""
                    INSERT INTO packages (PackageName, Markup, LastUpdated)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(PackageName) DO UPDATE SET
                        Markup = excluded.Markup,
                        LastUpdated = excluded.LastUpdated
                """, (pkg, markup_val))
            
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error syncing to Packages SOR: {e}")

    def _sync_to_all_pboqs(self):
        """Applies current table markups to every PBOQ database in the project's Priced BOQs folder."""
        pboq_folder = os.path.join(self.project_dir, "Priced BOQs")
        if not os.path.exists(pboq_folder):
             QMessageBox.warning(self, "Sync Error", f"Priced BOQs folder not found at:\n{pboq_folder}")
             return
        
        # Gather markups from table
        markups = {}
        for i in range(self.table.rowCount()):
            pkg = self.table.item(i, 0).text()
            raw_m = self.table.item(i, 1).text().replace(',', '').replace('%', '')
            try:
                markups[pkg] = float(raw_m)
            except: pass
        
        if not markups: return
        
        db_files = [f for f in os.listdir(pboq_folder) if f.lower().endswith('.db')]
        updated_count = 0
        
        # Mapping state folder
        state_dir = os.path.join(self.project_dir, "PBOQ States")
        
        # Step 4: Apply updates based on Standardized Schema (Col 10 = Pkg, Col 13 = Markup)
        from pboq_logic import PBOQLogic
        
        for db_name in db_files:
            target_path = os.path.join(pboq_folder, db_name)
            try:
                conn = sqlite3.connect(target_path)
                
                # IMPORTANT: Ensure this file has the standard columns 10 and 13
                # before we try to use them.
                success, db_cols = PBOQLogic.ensure_schema(conn)
                if not success:
                    conn.close()
                    continue
                
                cursor = conn.cursor()
                
                # Standardized Columns (indices)
                pkg_col = "Column 10"
                markup_col = "Column 13"
                
                for pkg, markup in markups.items():
                    # Update both the logical named column and the physical standardized column
                    # This ensures the data is visible regardless of which access method is used.
                    cursor.execute(f"""
                        UPDATE pboq_items 
                        SET \"{markup_col}\" = ?, SubbeeMarkup = ?
                        WHERE UPPER(TRIM(\"{pkg_col}\")) = UPPER(TRIM(?))
                           OR UPPER(TRIM(SubbeePackage)) = UPPER(TRIM(?))
                    """, (str(markup), str(markup), pkg, pkg))
                    
                conn.commit()
                conn.close()
                updated_count += 1
            except Exception as e:
                print(f"Failed to sync {db_name}: {e}")
                
        self._sync_to_sor() # Also update Master SOR
        QMessageBox.information(self, "Project Sync Complete", f"Successfully updated markups in {updated_count} PBOQ file(s).\n\nLayouts are now standardized (Col 10: Packaging, Col 13: Markup).")
        self.dataChanged.emit() # Refresh current view too
