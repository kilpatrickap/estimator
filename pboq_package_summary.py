import sqlite3
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem, 
                             QPushButton, QHBoxLayout, QMessageBox, QHeaderView)
from PyQt6.QtCore import Qt, pyqtSignal

class PackageSummaryDialog(QDialog):
    dataChanged = pyqtSignal()

    def __init__(self, project_dir, current_db, pkg_col, markup_col, parent=None):
        super().__init__(parent)
        self.project_dir = project_dir
        self.db_path = current_db
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
        self.save_btn = QPushButton("Save Changes")
        self.save_btn.clicked.connect(self._save_changes)
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
            
            # --- Project-wide Sync Logic ---
            if self.project_dir and os.path.isdir(self.project_dir):
                other_pboqs = []
                try:
                    other_pboqs = [os.path.join(self.project_dir, f) for f in os.listdir(self.project_dir) 
                                  if f.endswith(('.pboq', '.db')) and os.path.abspath(os.path.join(self.project_dir, f)) != os.path.abspath(self.db_path)]
                except:
                    pass
                
                for p_path in other_pboqs:
                    try:
                        other_conn = sqlite3.connect(p_path)
                        other_curs = other_conn.cursor()
                        
                        # 1. Verify it's a PBOQ
                        other_curs.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pboq_items'")
                        if not other_curs.fetchone(): 
                            other_conn.close()
                            continue
                            
                        # 2. Identify potential Package & Markup columns in this file
                        other_curs.execute("PRAGMA table_info(pboq_items)")
                        other_cols = [c[1] for c in other_curs.fetchall()]
                        
                        target_pkg_col = "SubbeePackage" if "SubbeePackage" in other_cols else (self.pkg_col if self.pkg_col in other_cols else None)
                        target_markup_col = "SubbeeMarkup" if "SubbeeMarkup" in other_cols else (self.markup_col if self.markup_col in other_cols else None)
                        
                        if target_pkg_col and target_markup_col:
                            for i in range(self.table.rowCount()):
                                pkg = self.table.item(i, 0).text()
                                raw_m = self.table.item(i, 1).text().replace(',', '').replace('%', '')
                                try:
                                    markup_val = float(raw_m)
                                    other_curs.execute(f'UPDATE pboq_items SET "{target_markup_col}" = ? WHERE "{target_pkg_col}" = ?', 
                                                     (str(markup_val), pkg))
                                except: continue
                                
                            other_conn.commit()
                        other_conn.close()
                    except: pass
            
            self.dataChanged.emit()
            # self.accept() # Removed per previous request
        except sqlite3.Error as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save changes: {e}")
        finally:
            if 'conn' in locals() and conn: conn.close()
            self.table.blockSignals(False)
