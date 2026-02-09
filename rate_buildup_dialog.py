from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTreeWidget, 
                             QTreeWidgetItem, QHeaderView, QLabel, QFrame, QPushButton)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from database import DatabaseManager
from edit_item_dialog import EditItemDialog
import re

class RateBuildUpDialog(QDialog):
    """
    Shows a detailed breakdown of a specific Rate Build-up.
    (Read-only view of an archived estimate)
    """
    def __init__(self, estimate_object, parent=None):
        super().__init__(parent)
        self.estimate = estimate_object
        self.db_manager = DatabaseManager("construction_rates.db")
        self.setWindowTitle(f"Edit Rate Build-up: {self.estimate.rate_id}")
        self.setMinimumSize(1000, 750)
        
        # Extract currency symbol
        match = re.search(r'\((.*?)\)', self.estimate.currency)
        self.currency_symbol = match.group(1) if match else "$"
        
        self._init_ui()
        self.refresh_view()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        # Header Section
        header = QFrame()
        header.setStyleSheet("background-color: #f8f9fa; border-radius: 8px; border: 1px solid #e0e0e0;")
        h_layout = QVBoxLayout(header)
        
        title_label = QLabel(f"Build-up Details for {self.estimate.rate_id}")
        title_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #2e7d32; border: none;")
        
        desc_label = QLabel(f"{self.estimate.project_name} (Unit: {self.estimate.unit or 'N/A'})")
        desc_label.setStyleSheet("font-size: 14px; color: #606266; border: none;")
        
        h_layout.addWidget(title_label)
        h_layout.addWidget(desc_label)
        layout.addWidget(header)

        # Build-up Tree
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Ref", "Tasks", "Calculations", "Cost", "Net Rate"])
        header_view = self.tree.header()
        header_view.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header_view.setStretchLastSection(True)
        self.tree.itemDoubleClicked.connect(self.edit_item)
        
        layout.addWidget(self.tree)

        # Summary Row (Grand Total)
        totals = self.estimate.calculate_totals()
        summary_layout = QHBoxLayout()
        summary_layout.addStretch()
        
        total_label = QLabel(f"TOTAL RATE: {self.currency_symbol}{totals['grand_total']:,.2f}")
        total_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #2e7d32; padding: 10px;")
        summary_layout.addWidget(total_label)
        layout.addLayout(summary_layout)

        # Footer
        footer_layout = QHBoxLayout()
        footer_layout.addStretch()
        
        save_btn = QPushButton("Save Changes")
        save_btn.setMinimumHeight(45)
        save_btn.setFixedWidth(200)
        save_btn.setStyleSheet("background-color: #2e7d32; color: white; font-weight: bold;")
        save_btn.clicked.connect(self.save_changes)
        
        close_btn = QPushButton("Cancel")
        close_btn.setMinimumHeight(45)
        close_btn.setFixedWidth(120)
        close_btn.clicked.connect(self.close)
        
        footer_layout.addWidget(close_btn)
        footer_layout.addWidget(save_btn)
        layout.addLayout(footer_layout)

    def edit_item(self, item, column):
        """Opens the formula-based edit dialog for the double-clicked resource."""
        if hasattr(item, 'item_type') and hasattr(item, 'item_data'):
            if EditItemDialog(item.item_data, item.item_type, self.estimate.currency, self).exec():
                self.refresh_view()

    def save_changes(self):
        """Saves the modified rate build-up back to the rates database."""
        if self.db_manager.save_estimate(self.estimate):
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(self, "Success", "Rate build-up updated successfully.")
            self.accept()
        else:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Error", "Failed to save changes.")

    def refresh_view(self):
        self.tree.clear()
        base_sym = self.currency_symbol

        bold_font = self.tree.font()
        bold_font.setBold(True)

        for i, task in enumerate(self.estimate.tasks, 1):
            # Calculate total for display
            task_total = sum([
                sum(self.estimate._get_item_total_in_base_currency(m) for m in task.materials),
                sum(self.estimate._get_item_total_in_base_currency(l) for l in task.labor),
                sum(self.estimate._get_item_total_in_base_currency(e) for e in task.equipment)
            ])
            
            task_item = QTreeWidgetItem(self.tree, [str(i), task.description, "", "", f"{base_sym}{task_total:,.2f}"])
            for col in range(self.tree.columnCount()):
                task_item.setFont(col, bold_font)

            # Define configurations for each type of resource
            resources = [
                ('materials', 'Material', 'name', lambda x: x['unit'], 'qty', 'unit_cost', 'material'),
                ('labor', 'Labor', 'trade', lambda x: 'hrs', 'hours', 'rate', 'labor'),
                ('equipment', 'Equipment', 'name', lambda x: 'hrs', 'hours', 'rate', 'equipment')
            ]
            
            sub_idx = 1
            for list_attr, label_prefix, name_key, unit_func, qty_key, rate_key, type_code in resources:
                items = getattr(task, list_attr)
                for item in items:
                    uc_conv = self.estimate.convert_to_base_currency(item[rate_key], item.get('currency'))
                    total_conv = self.estimate.convert_to_base_currency(item['total'], item.get('currency'))
                    
                    unit_str = unit_func(item)
                    qty_val = item[qty_key]
                    
                    child = QTreeWidgetItem(task_item, [
                        f"{i}.{sub_idx}",
                        f"{label_prefix}: {item[name_key]}",
                        f"{qty_val:.2f} {unit_str} @ {base_sym}{uc_conv:,.2f}",
                        f"{base_sym}{total_conv:,.2f}",
                        ""
                    ])
                    # Attach data for editing
                    child.item_type = type_code
                    child.item_data = item
                    child.task_object = task

                    # Color coding for easier reading
                    if label_prefix == 'Material': child.setForeground(1, Qt.GlobalColor.darkBlue)
                    if label_prefix == 'Labor': child.setForeground(1, Qt.GlobalColor.darkGreen)
                    if label_prefix == 'Equipment': child.setForeground(1, Qt.GlobalColor.darkRed)
                    sub_idx += 1

        self.tree.expandAll()
        for i in range(self.tree.columnCount()):
            self.tree.resizeColumnToContents(i)
        
        self.tree.header().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.tree.header().setStretchLastSection(True)
