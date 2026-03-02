import os
import pandas as pd
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QTableWidget, QTableWidgetItem,
    QLabel, QComboBox, QPushButton, QTreeWidget, QTreeWidgetItem, QHeaderView,
    QMessageBox, QInputDialog, QMenu, QFormLayout
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont

class BOQSetupWindow(QWidget):
    """Parses Excel BOQs, allows mapping, and formats them into an Estimate struct."""
    def __init__(self, boq_file_path, active_est_window, parent=None):
        super().__init__(parent)
        self.boq_file_path = boq_file_path
        self.active_est_window = active_est_window
        self.df = None
        
        # Color codes for visual feedback
        self.COLOR_HEADING = QColor("#e8f5e9") # Light green
        self.COLOR_ITEM = QColor("#ffffff")    # White
        self.COLOR_IGNORE = QColor("#ffebee")  # Light red

        # Core logic state
        self.columns = []
        self.row_types = [] # List of 'heading', 'item', or 'ignore' parallel to dataframe
        
        self.setWindowTitle(f"BOQ Setup - {os.path.basename(boq_file_path)}")
        self._init_ui()
        self._load_excel()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # LEFT PANE: Raw Excel View
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.addWidget(QLabel("Raw BOQ Data (from Excel):"))
        
        self.table = QTableWidget()
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        left_layout.addWidget(self.table)
        
        # RIGHT PANE: Mapping and Preview
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        mapping_form = QFormLayout()
        
        self.cb_ref = QComboBox()
        self.cb_desc = QComboBox()
        self.cb_qty = QComboBox()
        self.cb_unit = QComboBox()
        self.cb_rate = QComboBox()
        
        mapping_form.addRow("Ref / Item No Column:", self.cb_ref)
        mapping_form.addRow("Description Column:", self.cb_desc)
        mapping_form.addRow("Quantity Column:", self.cb_qty)
        mapping_form.addRow("Unit Column:", self.cb_unit)
        mapping_form.addRow("Rate Column (Optional):", self.cb_rate)
        
        apply_map_btn = QPushButton("Apply Mapping & Auto-Format")
        apply_map_btn.clicked.connect(self._apply_mapping)
        
        right_layout.addLayout(mapping_form)
        right_layout.addWidget(apply_map_btn)
        
        right_layout.addWidget(QLabel("Formatted Preview:"))
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Ref", "Description", "Quantity", "Unit", "Type"])
        self.tree.header().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.tree.header().setStretchLastSection(True)
        right_layout.addWidget(self.tree)
        
        import_btn = QPushButton("Import to Estimate Tasks")
        import_btn.setMinimumHeight(50)
        import_btn.setStyleSheet("background-color: #1976D2; color: white; font-weight: bold;")
        import_btn.clicked.connect(self._import_to_estimate)
        right_layout.addWidget(import_btn)
        
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        
        # Ratios (Left gets more space usually for the excel view)
        splitter.setStretchFactor(0, 6)
        splitter.setStretchFactor(1, 4)
        
        main_layout.addWidget(splitter)

    def _load_excel(self):
        try:
            # We skip the first few rows sometimes, but let's just read header=None to display everything raw
            self.df = pd.read_excel(self.boq_file_path, header=None)
            self.df.fillna("", inplace=True)
            self.row_types = ['ignore'] * len(self.df) # Initialize all as ignore
            
            # Populate Table
            self.table.setRowCount(len(self.df))
            self.table.setColumnCount(len(self.df.columns))
            
            self.columns = [f"Column {i}" for i in range(len(self.df.columns))]
            self.table.setHorizontalHeaderLabels(self.columns)
            
            for r in range(len(self.df)):
                for c in range(len(self.df.columns)):
                    val = str(self.df.iloc[r, c])
                    item = QTableWidgetItem(val)
                    item.setBackground(self.COLOR_IGNORE)
                    self.table.setItem(r, c, item)
            
            # Populate ComboBoxes
            for cb in [self.cb_ref, self.cb_desc, self.cb_qty, self.cb_unit, self.cb_rate]:
                cb.clear()
                cb.addItem("-- Select Column --")
                cb.addItems(self.columns)
            
            # Attempt a basic auto-guess
            if len(self.columns) > 1: self.cb_ref.setCurrentIndex(1)
            if len(self.columns) > 2: self.cb_desc.setCurrentIndex(2)
            if len(self.columns) > 3: self.cb_qty.setCurrentIndex(3)
            if len(self.columns) > 4: self.cb_unit.setCurrentIndex(4)

        except Exception as e:
            QMessageBox.critical(self, "Excel Error", f"Failed to load BOQ Excel file.\nError: {e}")

    def _show_context_menu(self, pos):
        menu = QMenu()
        set_heading_action = menu.addAction("Set row(s) as Heading")
        set_item_action = menu.addAction("Set row(s) as Item")
        set_ignore_action = menu.addAction("Set row(s) to Ignore")
        
        action = menu.exec(self.table.mapToGlobal(pos))
        
        if not action: return
        
        rows = list(set([idx.row() for idx in self.table.selectedIndexes()]))
        
        for r in rows:
            if action == set_heading_action:
                self.row_types[r] = 'heading'
                self._update_row_color(r, self.COLOR_HEADING)
            elif action == set_item_action:
                self.row_types[r] = 'item'
                self._update_row_color(r, self.COLOR_ITEM)
            elif action == set_ignore_action:
                self.row_types[r] = 'ignore'
                self._update_row_color(r, self.COLOR_IGNORE)
        
        self._build_tree_preview()

    def _update_row_color(self, row, color):
        for c in range(self.table.columnCount()):
            item = self.table.item(row, c)
            if item:
                item.setBackground(color)

    def _apply_mapping(self):
        """Auto detects Headings vs Items based on columns"""
        desc_col = self.cb_desc.currentIndex() - 1
        qty_col = self.cb_qty.currentIndex() - 1
        
        if desc_col < 0:
            QMessageBox.warning(self, "Mapping Error", "You must at least select a Description column.")
            return

        for r in range(len(self.df)):
            desc_val = str(self.df.iloc[r, desc_col]).strip()
            qty_val = str(self.df.iloc[r, qty_col]).strip() if qty_col >= 0 else ""
            
            if not desc_val:
                self.row_types[r] = 'ignore'
                self._update_row_color(r, self.COLOR_IGNORE)
                continue
                
            # If it has a description but no quantity, assume Heading
            if desc_val and not qty_val:
                self.row_types[r] = 'heading'
                self._update_row_color(r, self.COLOR_HEADING)
            # If it has both, assume Item
            elif desc_val and qty_val:
                self.row_types[r] = 'item'
                self._update_row_color(r, self.COLOR_ITEM)

        self._build_tree_preview()

    def _build_tree_preview(self):
        self.tree.clear()
        
        ref_col = self.cb_ref.currentIndex() - 1
        desc_col = self.cb_desc.currentIndex() - 1
        qty_col = self.cb_qty.currentIndex() - 1
        unit_col = self.cb_unit.currentIndex() - 1
        
        current_heading_item = None
        
        bold_font = QFont()
        bold_font.setBold(True)
        
        for r in range(len(self.df)):
            rtype = self.row_types[r]
            if rtype == 'ignore': continue
            
            ref_val = str(self.df.iloc[r, ref_col]) if ref_col >= 0 else ""
            desc_val = str(self.df.iloc[r, desc_col]) if desc_col >= 0 else ""
            qty_val = str(self.df.iloc[r, qty_col]) if qty_col >= 0 else ""
            unit_val = str(self.df.iloc[r, unit_col]) if unit_col >= 0 else ""
            
            if rtype == 'heading':
                current_heading_item = QTreeWidgetItem(self.tree, [ref_val, desc_val, "", "", "Heading"])
                for i in range(5): current_heading_item.setFont(i, bold_font)
                current_heading_item.setBackground(1, self.COLOR_HEADING)
            
            elif rtype == 'item':
                parent = current_heading_item if current_heading_item else self.tree
                item_node = QTreeWidgetItem(parent, [ref_val, desc_val, qty_val, unit_val, "Item"])
                
        self.tree.expandAll()

    def _import_to_estimate(self):
        """Creates Tasks in the active estimate based on the mapped items."""
        if not self.active_est_window:
            QMessageBox.warning(self, "Error", "No active estimate window found to import into.")
            return
            
        ref_col = self.cb_ref.currentIndex() - 1
        desc_col = self.cb_desc.currentIndex() - 1
        qty_col = self.cb_qty.currentIndex() - 1
        unit_col = self.cb_unit.currentIndex() - 1

        if desc_col < 0:
            QMessageBox.warning(self, "Error", "Description column must be mapped.")
            return

        self.active_est_window.save_state()
        from models import Task
        
        current_category = ""
        imported_count = 0
        
        for r in range(len(self.df)):
            rtype = self.row_types[r]
            
            desc_val = str(self.df.iloc[r, desc_col]).strip() if desc_col >= 0 else ""
            if not desc_val: continue
            
            if rtype == 'heading':
                current_category = desc_val
            elif rtype == 'item':
                ref_val = str(self.df.iloc[r, ref_col]).strip() if ref_col >= 0 else ""
                qty_str = str(self.df.iloc[r, qty_col]).strip() if qty_col >= 0 else "0"
                unit_val = str(self.df.iloc[r, unit_col]).strip() if unit_col >= 0 else ""
                
                try:
                    qty = float(qty_str.replace(',', ''))
                except ValueError:
                    qty = 1.0 # fallback
                    
                full_desc = f"[{ref_val}] {desc_val}" if ref_val else desc_val
                if current_category:
                    full_desc = f"{current_category} - {full_desc}"
                    
                new_task = Task(description=full_desc, quantity=qty, unit=unit_val)
                self.active_est_window.estimate.add_task(new_task)
                imported_count += 1
                
        self.active_est_window.db_manager.save_estimate(self.active_est_window.estimate)
        self.active_est_window.refresh_view()
        QMessageBox.information(self, "Success", f"Successfully imported {imported_count} items into the estimate.")
        self.close()
