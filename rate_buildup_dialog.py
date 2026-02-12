from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTreeWidget, 
                             QTreeWidgetItem, QHeaderView, QLabel, QFrame, QPushButton,
                             QInputDialog, QMessageBox, QLineEdit, QTableWidget, QTableWidgetItem,
                             QComboBox, QMenu, QFormLayout)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from database import DatabaseManager
from edit_item_dialog import EditItemDialog
from currency_conversion_dialog import CurrencyConversionDialog
import re
import copy
from datetime import datetime

class RateBuildUpDialog(QDialog):
    """
    Shows a detailed breakdown of a specific Rate Build-up and allows editing.
    (Archived estimate editor)
    """
    stateChanged = pyqtSignal()
    dataCommitted = pyqtSignal()
    
    def __init__(self, estimate_object, main_window=None, parent=None):
        super().__init__(parent)
        self.estimate = estimate_object
        self.main_window = main_window
        self.db_manager = DatabaseManager("construction_rates.db")
        self.setWindowTitle(f"Edit Rate Build-up: {self.estimate.rate_id}")
        self.setMinimumSize(650, 500)
        
        # Undo/Redo Stacks
        self.undo_stack = []
        self.redo_stack = []
        
        # Extract currency symbol
        match = re.search(r'\((.*?)\)', self.estimate.currency)
        self.currency_symbol = match.group(1) if match else "$"
        
        self._init_ui()
        self.refresh_view()

    def _save_state(self):
        """Saves current estimate state to undo stack."""
        self.undo_stack.append(copy.deepcopy(self.estimate))
        self.redo_stack.clear() # Clear redo when a new action is performed
        self.stateChanged.emit()

    def undo(self):
        if self.undo_stack:
            self.redo_stack.append(copy.deepcopy(self.estimate))
            self.estimate = self.undo_stack.pop()
            self.refresh_view()
            self.stateChanged.emit()

    def redo(self):
        if self.redo_stack:
            self.undo_stack.append(copy.deepcopy(self.estimate))
            self.estimate = self.redo_stack.pop()
            self.refresh_view()
            self.stateChanged.emit()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)

        # Header Section
        header = QFrame()
        header.setStyleSheet("background-color: #f8f9fa; border-radius: 4px; border: 1px solid #e0e0e0;")
        h_layout = QVBoxLayout(header)
        h_layout.setContentsMargins(10, 5, 10, 5)
        h_layout.setSpacing(0)
        
        title_label = QLabel(f"Build-up Details for {self.estimate.rate_id}")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #2e7d32; border: none;")
        
        desc_label = QLabel(f"{self.estimate.project_name} (Unit: {self.estimate.unit or 'N/A'})")
        desc_label.setStyleSheet("font-size: 12px; color: #606266; border: none;")
        
        h_layout.addWidget(title_label)
        h_layout.addWidget(desc_label)
        layout.addWidget(header)

        # Toolbar Section
        toolbar = QHBoxLayout()
        
        # Base Currency Selector
        toolbar.addWidget(QLabel("Base Currency:"))
        self.currency_combo = QComboBox()
        self.currencies = ["USD ($)", "EUR (€)", "GBP (£)", "JPY (¥)", "CAD ($)", "GHS (₵)", "CNY (¥)", "INR (₹)"]
        self.currency_combo.addItems(self.currencies)
        self.currency_combo.setCurrentText(self.estimate.currency)
        self.currency_combo.currentTextChanged.connect(self.change_base_currency)
        toolbar.addWidget(self.currency_combo)

        ex_rate_btn = QPushButton("Exchange Rates")
        ex_rate_btn.clicked.connect(self.open_exchange_rates)
        toolbar.addWidget(ex_rate_btn)
        
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Build-up Tree
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Ref", "Tasks", "Calculations", "Cost", "Net Rate"])
        header_view = self.tree.header()
        header_view.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header_view.setStretchLastSection(True)
        self.tree.setIndentation(15)
        self.tree.itemDoubleClicked.connect(self.edit_item)
        
        # Context Menu
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.show_context_menu)
        
        layout.addWidget(self.tree)

        # Summary Row (Build-up Totals)
        summary_layout = QHBoxLayout()
        summary_layout.addStretch()
        
        totals_panel = QFrame()
        totals_panel.setStyleSheet("background-color: #f1f8e9; border-radius: 4px; border: 1px solid #c8e6c9;")
        totals_layout = QFormLayout(totals_panel)
        totals_layout.setContentsMargins(10, 5, 10, 5)
        totals_layout.setSpacing(5)
        
        self.subtotal_label = QLabel("0.00")
        self.overhead_label = QLabel("0.00")
        self.profit_label = QLabel("0.00")
        self.total_label = QLabel("0.00")
        
        for lbl in [self.subtotal_label, self.overhead_label, self.profit_label, self.total_label]:
            lbl.setStyleSheet("font-family: 'Consolas', monospace; font-size: 12px; font-weight: bold; border: none;")
            lbl.setAlignment(Qt.AlignmentFlag.AlignRight)

        self.total_label.setStyleSheet("font-family: 'Consolas', monospace; font-size: 14px; font-weight: bold; color: #2e7d32; border: none;")
        
        totals_layout.addRow("Build-up Subtotal (Sum of Net Rates):", self.subtotal_label)
        totals_layout.addRow(f"Overhead ({self.estimate.overhead_percent}%):", self.overhead_label)
        totals_layout.addRow(f"Profit ({self.estimate.profit_margin_percent}%):", self.profit_label)
        totals_layout.addRow("TOTAL RATE:", self.total_label)
        
        summary_layout.addWidget(totals_panel)
        layout.addLayout(summary_layout)

    def show_context_menu(self, pos):
        menu = QMenu(self)
        
        add_task_action = menu.addAction("Add Task")
        add_task_action.triggered.connect(self.add_task)
        
        menu.addSeparator()
        
        add_mat_action = menu.addAction("Add Material")
        add_mat_action.triggered.connect(lambda: self.add_resource("materials"))
        
        add_lab_action = menu.addAction("Add Labor")
        add_lab_action.triggered.connect(lambda: self.add_resource("labor"))
        
        add_eqp_action = menu.addAction("Add Equipment")
        add_eqp_action.triggered.connect(lambda: self.add_resource("equipment"))
        
        add_plt_action = menu.addAction("Add Plant")
        add_plt_action.triggered.connect(lambda: self.add_resource("plant"))
        
        add_ind_action = menu.addAction("Add Indirect Cost")
        add_ind_action.triggered.connect(lambda: self.add_resource("indirect_costs"))
        
        menu.addSeparator()
        
        remove_action = menu.addAction("Remove Selected")
        remove_action.triggered.connect(self.remove_selected)
        
        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def open_exchange_rates(self):
        self._save_state()
        if CurrencyConversionDialog(self.estimate, self).exec():
            self.refresh_view()
        else:
            self.undo_stack.pop()
            self.stateChanged.emit()

    def change_base_currency(self, new_currency):
        if new_currency == self.estimate.currency:
            return
        self._save_state()
        self.estimate.currency = new_currency
        self.refresh_view()

    def add_task(self):
        desc, ok = QInputDialog.getText(self, "Add Task", "Task Description:")
        if ok and desc:
            self._save_state()
            from models import Task
            self.estimate.add_task(Task(desc))
            self.refresh_view()

    def add_resource(self, table_name):
        # We need a selected task in the tree
        selected = self.tree.currentItem()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select a Task in the tree first.")
            return
            
        # If a child is selected, find its parent task
        task_item = selected if not selected.parent() else selected.parent()
        if task_item.parent(): # Should not happen with current tree structure
             task_item = task_item.parent()
             
        task_idx = self.tree.indexOfTopLevelItem(task_item)
        if task_idx < 0:
            QMessageBox.warning(self, "Selection Error", "Please select a valid Task.")
            return
            
        task_obj = self.estimate.tasks[task_idx]
        
        dialog = CostSelectionDialog(table_name, self)
        if dialog.exec():
            selected_data = dialog.selected_item
            if selected_data:
                self._save_state()
                if table_name == "materials":
                    task_obj.add_material(
                        selected_data['name'], 1.0, selected_data['unit'], 
                        selected_data['price'], selected_data['currency']
                    )
                elif table_name == "labor":
                    task_obj.add_labor(
                        selected_data['trade'], 1.0, selected_data['rate'], 
                        selected_data['currency'], unit=selected_data.get('unit')
                    )
                elif table_name == "equipment":
                    task_obj.add_equipment(
                        selected_data['name'], 1.0, selected_data['rate'], 
                        selected_data['currency'], unit=selected_data.get('unit')
                    )
                elif table_name == "plant":
                    task_obj.add_plant(
                        selected_data['name'], 1.0, selected_data['rate'], 
                        selected_data['currency'], unit=selected_data.get('unit')
                    )
                elif table_name == "indirect_costs":
                    task_obj.add_indirect_cost(
                        selected_data['description'], selected_data['amount'], 
                        unit=selected_data.get('unit'), currency=selected_data['currency']
                    )
                self.refresh_view()

    def remove_selected(self):
        item = self.tree.currentItem()
        if not item:
            return

        self._save_state()
        parent = item.parent()
        if not parent:
            # It's a task
            idx = self.tree.indexOfTopLevelItem(item)
            if 0 <= idx < len(self.estimate.tasks):
                self.estimate.tasks.pop(idx)
        else:
            # It's a resource
            task_idx = self.tree.indexOfTopLevelItem(parent)
            task_obj = self.estimate.tasks[task_idx]
            
            # Identify which list it belongs to
            # In refresh_view, we store item_data and item_type on the child
            if hasattr(item, 'item_type') and hasattr(item, 'item_data'):
                rtype = item.item_type
                rdata = item.item_data
                
                if rtype == 'material':
                    task_obj.materials.remove(rdata)
                elif rtype == 'labor':
                    task_obj.labor.remove(rdata)
                elif rtype == 'equipment':
                    task_obj.equipment.remove(rdata)
                elif rtype == 'plant':
                    task_obj.plant.remove(rdata)
                elif rtype == 'indirect_costs':
                    task_obj.indirect_costs.remove(rdata)
        
        self.refresh_view()

    def edit_item(self, item, column):
        """Opens the formula-based edit dialog for the double-clicked resource."""
        if hasattr(item, 'item_type') and hasattr(item, 'item_data'):
            if self.main_window and hasattr(self.main_window, 'open_edit_item_window'):
                self.main_window.open_edit_item_window(item.item_data, item.item_type, self.estimate.currency, self)
            else:
                 # Fallback for dialog mode
                 dialog = EditItemDialog(item.item_data, item.item_type, self.estimate.currency, self)
                 if dialog.exec():
                     self.refresh_view()
                     self.stateChanged.emit()

    def save_changes(self):
        """Saves the modified rate build-up back to the rates database."""
        # Update timestamp to the current time of archiving/saving
        self.estimate.date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        if self.db_manager.save_estimate(self.estimate):
            self.dataCommitted.emit()
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(self, "Success", "Rate build-up updated successfully.")
        else:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Error", "Failed to save changes.")

    def refresh_view(self):
        self.tree.clear()
        
        # Update currency symbol
        match = re.search(r'\((.*?)\)', self.estimate.currency)
        self.currency_symbol = match.group(1) if match else "$"
        
        base_sym = self.currency_symbol
        
        # Update Combo if needed (for undo/redo)
        if hasattr(self, 'currency_combo'):
            self.currency_combo.blockSignals(True)
            self.currency_combo.setCurrentText(self.estimate.currency)
            self.currency_combo.blockSignals(False)
            
        # Update Summary Labels
        totals = self.estimate.calculate_totals()
        self.subtotal_label.setText(f"{base_sym}{totals['subtotal']:,.2f}")
        self.overhead_label.setText(f"{base_sym}{totals['overhead']:,.2f}")
        self.profit_label.setText(f"{base_sym}{totals['profit']:,.2f}")
        self.total_label.setText(f"{base_sym}{totals['grand_total']:,.2f}")

        bold_font = self.tree.font()
        bold_font.setBold(True)

        for i, task in enumerate(self.estimate.tasks, 1):
            # Calculate total for display
            task_total = sum([
                sum(self.estimate._get_item_total_in_base_currency(m) for m in task.materials),
                sum(self.estimate._get_item_total_in_base_currency(l) for l in task.labor),
                sum(self.estimate._get_item_total_in_base_currency(e) for e in task.equipment),
                sum(self.estimate._get_item_total_in_base_currency(p) for p in task.plant),
                sum(self.estimate._get_item_total_in_base_currency(ind) for ind in task.indirect_costs)
            ])
            
            task_item = QTreeWidgetItem(self.tree, [str(i), task.description, "", "", f"{base_sym}{task_total:,.2f}"])
            for col in range(self.tree.columnCount()):
                task_item.setFont(col, bold_font)

            # Define configurations for each type of resource
            resources = [
                ('materials', 'Material', 'name', lambda x: x['unit'], 'qty', 'unit_cost', 'material'),
                ('labor', 'Labor', 'trade', lambda x: x.get('unit') or 'hrs', 'hours', 'rate', 'labor'),
                ('equipment', 'Equipment', 'name', lambda x: x.get('unit') or 'hrs', 'hours', 'rate', 'equipment'),
                ('plant', 'Plant', 'name', lambda x: x.get('unit') or 'hrs', 'hours', 'rate', 'plant'),
                ('indirect_costs', 'Indirect', 'description', lambda x: x.get('unit') or '', 'amount', 'amount', 'indirect_costs')
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
        
        # self._update_undo_redo_buttons()




class CostSelectionDialog(QDialog):
    """Simplified dialog to select a cost from the global database."""
    def __init__(self, table_name, parent=None):
        super().__init__(parent)
        self.table_name = table_name
        self.selected_item = None
        
        singular = table_name[:-1] if table_name.endswith('s') else table_name
        self.setWindowTitle(f"Select {singular.capitalize()} from Database")
        self.setMinimumSize(600, 400)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Search
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Type to filter...")
        self.search_input.textChanged.connect(self.filter_table)
        search_layout.addWidget(self.search_input)
        layout.addLayout(search_layout)
        
        # Table
        self.table = QTableWidget()
        self.db_manager = DatabaseManager("construction_costs.db")
        self.load_data()
        
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setDefaultSectionSize(22)
        self.table.doubleClicked.connect(self.accept)
        
        layout.addWidget(self.table)
        
        # Buttons
        btns = QHBoxLayout()
        btns.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        select_btn = QPushButton("Select")
        select_btn.clicked.connect(self.accept)
        select_btn.setStyleSheet("background-color: #2e7d32; color: white; font-weight: bold;")
        
        btns.addWidget(cancel_btn)
        btns.addWidget(select_btn)
        layout.addLayout(btns)

    def load_data(self):
        items = self.db_manager.get_items(self.table_name)
        if not items:
            return
            
        # Headers based on table
        if self.table_name == "materials":
            headers = ["Name", "Unit", "Currency", "Price"]
            keys = ["name", "unit", "currency", "price"]
        elif self.table_name == "labor":
            headers = ["Trade", "Unit", "Currency", "Rate"]
            keys = ["trade", "unit", "currency", "rate"]
        else: # equipment
            headers = ["Name", "Unit", "Currency", "Rate"]
            keys = ["name", "unit", "currency", "rate"]
            
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setRowCount(len(items))
        
        self.full_data = []
        for r, row in enumerate(items):
            item_dict = dict(row)
            self.full_data.append(item_dict)
            for c, key in enumerate(keys):
                val = item_dict.get(key, "")
                if isinstance(val, float):
                    val = f"{val:,.2f}"
                self.table.setItem(r, c, QTableWidgetItem(str(val)))
                
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

    def filter_table(self, text):
        query = text.lower()
        for row in range(self.table.rowCount()):
            match = False
            for col in range(self.table.columnCount()):
                if query in self.table.item(row, col).text().lower():
                    match = True
                    break
            self.table.setRowHidden(row, not match)

    def accept(self):
        row = self.table.currentRow()
        if row >= 0:
            # Need to find the correct index in full_data if filtered
            # Actually, better to just store data in the item
            self.selected_item = self.full_data[row]
            super().accept()
        else:
            QMessageBox.warning(self, "Selection Error", "Please select an item.")
