import sqlite3
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem, 
                             QPushButton, QHBoxLayout, QMessageBox, QHeaderView)
from PyQt6.QtCore import Qt, pyqtSignal

class PackageSummaryDialog(QDialog):
    dataChanged = pyqtSignal()

    def __init__(self, db_path, parent=None):
        super().__init__(parent)
        self.db_path = db_path
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

    def _load_data(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            # Group by package name and find the most common markup (or max)
            # This handles cases where items in a package might have drifted during manual edits
            cursor.execute("""
                SELECT SubbeePackage, MAX(SubbeeMarkup) 
                FROM pboq_items 
                WHERE SubbeePackage IS NOT NULL AND SubbeePackage != ''
                GROUP BY SubbeePackage
                ORDER BY SubbeePackage
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
                
                markup_item = QTableWidgetItem("{:,.2f}".format(m_val))
                markup_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(i, 1, markup_item)
        except sqlite3.Error as e:
            print(f"Error loading packages summary: {e}")
        finally:
            conn.close()

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
                cursor.execute("UPDATE pboq_items SET SubbeeMarkup = ? WHERE SubbeePackage = ?", (str(markup_val), pkg))
            
            conn.commit()
            self.dataChanged.emit()
            QMessageBox.information(self, "Saved", "Package markups updated successfully.")
            self.accept()
        except sqlite3.Error as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save changes: {e}")
        finally:
            conn.close()
