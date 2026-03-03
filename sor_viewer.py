import os
import sqlite3
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QSplitter, 
                             QListWidget, QTableWidget, QTableWidgetItem, 
                             QLabel, QMessageBox, QHeaderView)
from PyQt6.QtCore import Qt

class SORDialog(QDialog):
    def __init__(self, project_dir, parent=None):
        super().__init__(parent)
        self.project_dir = project_dir
        self.sor_folder = os.path.join(self.project_dir, "SOR")
        
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
        self.list_widget.itemSelectionChanged.connect(self._load_selected_sor)
        self.splitter.addWidget(self.list_widget)
        
        # Right Panel (Table view of SOR)
        self.table_widget = QTableWidget()
        self.table_widget.setColumnCount(5)
        self.table_widget.setHorizontalHeaderLabels(["Sheet", "Ref", "Description", "Quantity", "Unit"])
        self.table_widget.verticalHeader().setVisible(False)
        self.table_widget.setAlternatingRowColors(True)
        self.table_widget.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table_widget.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        
        header = self.table_widget.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        
        self.splitter.addWidget(self.table_widget)
        
        # Set initial splitter sizes
        self.splitter.setSizes([200, 700])
        
        layout.addWidget(self.splitter)
        
        self._populate_list()

    def _populate_list(self):
        self.list_widget.clear()
        if not os.path.exists(self.sor_folder):
            return
            
        for f in os.listdir(self.sor_folder):
            if f.lower().endswith('.db'):
                self.list_widget.addItem(f)

    def _load_selected_sor(self):
        items = self.list_widget.selectedItems()
        self.table_widget.setRowCount(0)
        
        if not items:
            return
            
        filename = items[0].text()
        file_path = os.path.join(self.sor_folder, filename)
        
        if not os.path.exists(file_path):
            QMessageBox.warning(self, "Error", "Selected file no longer exists.")
            return
            
        try:
            conn = sqlite3.connect(file_path)
            cursor = conn.cursor()
            
            # Check if table 'sor_items' exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sor_items';")
            if not cursor.fetchone():
                QMessageBox.warning(self, "Format Error", "The selected database does not contain valid SOR data.")
                conn.close()
                return
                
            cursor.execute("SELECT Sheet, Ref, Description, Quantity, Unit FROM sor_items")
            rows = cursor.fetchall()
            
            self.table_widget.setRowCount(len(rows))
            for row_idx, row_data in enumerate(rows):
                for col_idx, col_val in enumerate(row_data):
                    item = QTableWidgetItem(str(col_val) if col_val is not None else "")
                    self.table_widget.setItem(row_idx, col_idx, item)
                    
            conn.close()
            
        except sqlite3.DatabaseError as e:
            QMessageBox.warning(self, "Database Error", f"Failed to read data from SOR database:\n{e}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load SOR data:\n{e}")
