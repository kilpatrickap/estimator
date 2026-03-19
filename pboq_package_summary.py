import os
import sqlite3
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem, 
                             QPushButton, QHBoxLayout, QMessageBox, QHeaderView)
from PyQt6.QtCore import Qt, pyqtSignal
from pboq_logic import PBOQLogic


class PackageSummaryDialog(QDialog):
    dataChanged = pyqtSignal()

    def __init__(self, db_path, project_dir, pkg_col, markup_col, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.project_dir = project_dir
        self.pkg_col = pkg_col
        self.markup_col = markup_col
        self.setWindowTitle("Work Packages Management")
        self.setMinimumWidth(450)
        self.setMinimumHeight(400)
        self._init_ui()
        self._load_data()




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
            

            
            self.dataChanged.emit()
        except sqlite3.Error as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save changes: {e}")
        finally:
            conn.close()



    def _sync_to_all_pboqs(self):
        """Applies current table markups to every PBOQ database in the project's Priced BOQs folder."""
        # Robust folder detection: handle cases where project_dir points to subfolders
        pboq_folder = ""
        current = self.project_dir
        for _ in range(4): # Check up to 4 levels up
            candidate = os.path.join(current, "Priced BOQs")
            if os.path.exists(candidate):
                pboq_folder = candidate
                break
            parent = os.path.dirname(current)
            if parent == current: break # reached root
            current = parent
            
        if not pboq_folder:
            QMessageBox.warning(self, "Sync Error", f"Could not find 'Priced BOQs' folder starting from:\n{self.project_dir}")
            return
        
        # Gather markups from table
        markups = {}
        for i in range(self.table.rowCount()):
            pkg = self.table.item(i, 0).text().strip()
            if not pkg: continue
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
        total_rows_updated = 0
        
        for db_name in db_files:
            target_path = os.path.join(pboq_folder, db_name)
            try:
                conn = sqlite3.connect(target_path)
                
                # IMPORTANT: Resolve schema to handle varying column counts/orders
                success, db_cols = PBOQLogic.ensure_schema(conn)
                if not success:
                    conn.close()
                    continue
                
                cursor = conn.cursor()
                
                # Target the column currently mapped to UI index 13 (Markup)
                # and fallback to 'Column 13' if for some reason schema is small.
                target_markup_col = db_cols[14] if len(db_cols) > 14 else "Column 13"
                
                rows_in_file = 0
                for pkg, markup in markups.items():
                    # Search across ALL physical columns and logical SubbeePackage
                    # Using LIKE with wildcards and COLLATE NOCASE for maximum robustness
                    cols_to_search = [f'"{c}"' for c in db_cols if c != 'Sheet']
                    where_clause = " OR ".join([f"{c} LIKE ? COLLATE NOCASE" for c in cols_to_search])
                    
                    # Update both the mapped physical column and the named logical column
                    sql = f'UPDATE pboq_items SET "{target_markup_col}" = ?, SubbeeMarkup = ? WHERE {where_clause}'
                    params = [str(markup), str(markup)] + [pkg] * len(cols_to_search)
                    
                    cursor.execute(sql, tuple(params))
                    rows_in_file += cursor.rowcount
                    
                conn.commit()
                conn.close()
                if rows_in_file > 0:
                    updated_count += 1
                    total_rows_updated += rows_in_file
            except Exception as e:
                print(f"Failed to sync {db_name}: {e}")
                
        self.dataChanged.emit() # Refresh current view too

        
        # Ensure UI repaints before we show the blocking popup
        from PyQt6.QtWidgets import QApplication
        QApplication.processEvents()
        
        msg = (f"Successfully synced markups in {updated_count} PBOQ file(s).\n"
               f"Total rows updated: {total_rows_updated}\n\n"
               f"Layouts are standardized based on the target file schema.")
        QMessageBox.information(self, "Project Sync Complete", msg)


