import os
import sqlite3
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QSplitter, 
                             QListWidget, QTableWidget, QTableWidgetItem, 
                             QLabel, QMessageBox, QHeaderView, QListWidgetItem,
                             QLineEdit, QWidget)
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
        self.list_widget.itemChanged.connect(self._load_selected_sor)
        self.splitter.addWidget(self.list_widget)
        
        # Right Panel (Layout containing Search Bar and Table)
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search...")
        self.search_bar.textChanged.connect(self._filter_table)
        right_layout.addWidget(self.search_bar)
        
        self.table_widget = QTableWidget()
        self.table_widget.setColumnCount(6)
        self.table_widget.setHorizontalHeaderLabels(["SOR", "Sheet", "Ref", "Description", "Quantity", "Unit"])
        self.table_widget.verticalHeader().setVisible(False)
        self.table_widget.setAlternatingRowColors(True)
        self.table_widget.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table_widget.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        
        header = self.table_widget.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        
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
                    
                cursor.execute("SELECT Sheet, Ref, Description, Quantity, Unit FROM sor_items")
                rows = cursor.fetchall()
                
                sor_name = filename[:-3] if filename.lower().endswith('.db') else filename
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

        if self.search_bar.text():
            self._filter_table(self.search_bar.text())

    def _filter_table(self, text):
        search_text = text.lower()
        for row in range(self.table_widget.rowCount()):
            row_visible = False
            for col in range(self.table_widget.columnCount()):
                item = self.table_widget.item(row, col)
                if item and search_text in item.text().lower():
                    row_visible = True
                    break
            self.table_widget.setRowHidden(row, not row_visible)
