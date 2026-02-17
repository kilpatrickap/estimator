from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTreeWidget, 
                             QTreeWidgetItem, QHeaderView, QLabel, QFrame, QPushButton,
                             QInputDialog, QMessageBox, QLineEdit, QTableWidget, QTableWidgetItem,
                             QComboBox, QMenu, QFormLayout, QTextEdit, QSplitter, QWidget)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QDoubleValidator
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
        self.setWindowTitle(f"Edit Rate Build-up: {self.estimate.rate_code}")
        self.setMinimumSize(726, 533)
        
        # Undo/Redo Stacks
        self.undo_stack = []
        self.redo_stack = []
        
        # Extract currency symbol
        match = re.search(r'\((.*?)\)', self.estimate.currency)
        self.currency_symbol = match.group(1) if match else "$"
        
        self._init_ui()
        self.refresh_view()
        
    def resizeEvent(self, event):
        """Dynamic resizing logic for the notes section."""
        super().resizeEvent(event)
        # We allow full dynamic adjustment now via splitters, 
        # but keep a reasonable base width to prevent accidental collapse
        if hasattr(self, 'notes_widget'):
            self.notes_widget.setMinimumWidth(int(self.rect().width() * 0.4))

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
        
        self.title_label = QLabel(f"{self.estimate.rate_code}")
        self.title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #2e7d32; border: none;")
        
        h_layout.addWidget(self.title_label)

        desc_status_layout = QHBoxLayout()
        self.desc_label = QLabel(f"{self.estimate.project_name} (Unit: {self.estimate.unit or 'N/A'})")
        self.desc_label.setStyleSheet("font-size: 12px; color: blue; border: none;")
        desc_status_layout.addWidget(self.desc_label)
        desc_status_layout.addStretch()
        
        self.status_badge = QLabel("BASE RATE")
        self.status_badge.setFixedSize(110, 24)
        self.status_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_badge.setStyleSheet("""
            QLabel {
                border-radius: 12px;
                font-size: 10px;
                font-weight: bold;
                color: #333;
                background-color: #fbc02d;
                border: none;
            }
        """)
        desc_status_layout.addWidget(self.status_badge)
        h_layout.addLayout(desc_status_layout)
        layout.addWidget(header)

        # Toolbar Section
        toolbar = QHBoxLayout()

        # Category Selector (Far Left)
        toolbar.addWidget(QLabel("Category:"))
        self.category_combo = QComboBox()
        self.categories = [
            "Preliminaries", "Earthworks", "Concrete", "Formwork", "Reinforcement", 
            "Structural Steelwork", "Blockwork", "Flooring", "Doors & Windows", 
            "Plastering", "Painting", "Roadwork & Fencing", "Miscellaneous", 
            "External Works", "Mechanical Works", "Electrical Works", 
            "Plumbing Works", "Heating/Ventilation & AirConditioning"
        ]
        self.category_combo.addItems(self.categories)
        self.category_combo.currentTextChanged.connect(self.change_category)
        toolbar.addWidget(self.category_combo)
        
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

        # Adjustment Factor to Cost
        toolbar.addWidget(QLabel("Adjustment Factor:"))

        self.adjstmt_factor_input = QLineEdit()
        self.adjstmt_factor_input.setFixedWidth(60)

        # Validator for 2 decimal places
        factor_validator = QDoubleValidator(0.00, 99.99, 2)
        factor_validator.setNotation(QDoubleValidator.Notation.StandardNotation)
        self.adjstmt_factor_input.setValidator(factor_validator)
        
        # Initial Value
        self.adjstmt_factor_input.setText("N/A")
        self.adjstmt_factor_input.editingFinished.connect(self._handle_factor_formatting)
        toolbar.addWidget(self.adjstmt_factor_input)
        
        # Unit Selection (Far Right, beneath capsule)
        toolbar.addWidget(QLabel("Unit:"))
        self.unit_combo = QComboBox()
        self.units = ["m", "m2", "m3", "kg", "t", "Item"]
        self.unit_combo.addItems(self.units)
        self.unit_combo.setEditable(True) # Allow custom units too
        self.unit_combo.setFixedWidth(80)
        
        # Set initial value if it exists in list, otherwise add and set
        curr_unit = self.estimate.unit or "Item"
        idx = self.unit_combo.findText(curr_unit)
        if idx >= 0:
            self.unit_combo.setCurrentIndex(idx)
        else:
            self.unit_combo.setEditText(curr_unit)
            
        self.unit_combo.currentTextChanged.connect(self.change_unit)
        toolbar.addWidget(self.unit_combo)
        
        layout.addLayout(toolbar)

        # Main Vertical Splitter for dynamic height management
        self.main_v_splitter = QSplitter(Qt.Orientation.Vertical)
        self.main_v_splitter.setHandleWidth(8)
        
        # Build-up Tree
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Ref", "Tasks", "Calculations", "Cost", "Net Rate", "Adjusted Net Rate"])
        header_view = self.tree.header()
        header_view.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header_view.setStretchLastSection(True)
        self.tree.setIndentation(15)
        self.tree.itemDoubleClicked.connect(self.edit_item)
        
        # Context Menu
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.show_context_menu)
        
        self.main_v_splitter.addWidget(self.tree)

        # Summary Row (Build-up Totals & Notes)
        self.summary_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.summary_splitter.setHandleWidth(10) # Subtle handle
        
        # Notes Section (Bottom Left)
        self.notes_widget = QWidget()
        notes_container = QVBoxLayout(self.notes_widget)
        notes_container.setContentsMargins(0, 0, 0, 0)
        
        self.notes_input = QTextEdit()
        self.notes_input.setPlaceholderText("Enter Rate's notes here...")
        self.notes_input.setAcceptRichText(False)
        self.notes_input.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        # Premium Light Yellow background for paper-like note taking
        # Font size and family now inherit from window for consistency
        self.notes_input.setStyleSheet("""
            QTextEdit { 
                border: 1px solid #c8e6c9; 
                border-radius: 6px; 
                background-color: #fffde7; 
                color: #6a1b9a; 
                padding: 10px;
            }
        """)
        notes_container.addWidget(self.notes_input)
        
        # Collaborative constraints: Initial min width allows flexibility
        self.notes_widget.setMinimumWidth(200) 
        
        totals_panel = QFrame()
        totals_panel.setStyleSheet("background-color: #f1f8e9; border-radius: 6px; border: 1px solid #c8e6c9;")
        totals_layout = QFormLayout(totals_panel)
        totals_layout.setContentsMargins(15, 10, 15, 10)
        totals_layout.setSpacing(8)
        
        self.summary_splitter.addWidget(self.notes_widget)
        self.summary_splitter.addWidget(totals_panel)
        self.summary_splitter.setStretchFactor(0, 1)
        self.summary_splitter.setStretchFactor(1, 1)

        # Container for the bottom part to ensure proper layout in the horizontal splitter
        bottom_container = QWidget()
        bottom_layout = QVBoxLayout(bottom_container)
        bottom_layout.setContentsMargins(0, 5, 0, 0)
        
        notes_lbl = QLabel("Notes :")
        notes_lbl.setStyleSheet("font-weight: bold; color: #444;")
        bottom_layout.addWidget(notes_lbl)
        
        bottom_layout.addWidget(self.summary_splitter)
        
        self.main_v_splitter.addWidget(bottom_container)
        self.main_v_splitter.setStretchFactor(0, 4) # Tree takes more height by default
        self.main_v_splitter.setStretchFactor(1, 1) # Summary takes less but is adjustable
        
        layout.addWidget(self.main_v_splitter)
        
        self.subtotal_label = QLabel("0.00")
        self.overhead_label = QLabel("0.00")
        self.profit_label = QLabel("0.00")
        self.total_label = QLabel("0.00")
        
        for lbl in [self.subtotal_label, self.overhead_label, self.profit_label, self.total_label]:
            lbl.setStyleSheet("font-family: 'Consolas', monospace; font-weight: bold; border: none;")
            lbl.setAlignment(Qt.AlignmentFlag.AlignRight)

        self.total_label.setStyleSheet("font-family: 'Consolas', monospace; font-weight: bold; color: #2e7d32; border: none;")
        
        self.subtotal_header_label = QLabel("Build-up Sub-Total (Sum of Net Rates):")
        totals_layout.addRow(self.subtotal_header_label, self.subtotal_label)
        totals_layout.addRow(f"Overhead ({self.estimate.overhead_percent}%):", self.overhead_label)
        totals_layout.addRow(f"Profit ({self.estimate.profit_margin_percent}%):", self.profit_label)
        gross_rate_header = QLabel("Gross Rate:")
        gross_rate_header.setStyleSheet("font-weight: bold;")
        totals_layout.addRow(gross_rate_header, self.total_label)
        

    def _handle_factor_formatting(self):
        """Formats input to 2 decimal places and handles N/A placeholder logic."""
        text = self.adjstmt_factor_input.text().strip()
        try:
            if not text or text.upper() == "N/A":
                self.adjstmt_factor_input.setText("N/A")
                self.estimate.adjustment_factor = 1.0
            else:
                val = float(text)
                if val == 0.0:
                    self.adjstmt_factor_input.setText("N/A")
                    self.estimate.adjustment_factor = 1.0
                else:
                    self.adjstmt_factor_input.setText(f"{val:.2f}")
                    self.estimate.adjustment_factor = val
        except ValueError:
            self.adjstmt_factor_input.setText("N/A")
            self.estimate.adjustment_factor = 1.0
        
        self.refresh_view()
        self.stateChanged.emit()

    def show_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        menu = QMenu(self)
        
        if item and hasattr(item, 'item_type'):
            go_to_action = menu.addAction("Go to Resource")
            go_to_action.triggered.connect(lambda: self.go_to_resource(item))
            menu.addSeparator()
        
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
        """Opens exchange rate settings in MDI."""
        for sub in self.main_window.mdi_area.subWindowList():
            if isinstance(sub.widget(), CurrencyConversionDialog):
                self.main_window.mdi_area.setActiveSubWindow(sub)
                return
                
        dialog = CurrencyConversionDialog(self.estimate, self)
        sub = self.main_window.mdi_area.addSubWindow(dialog)
        sub.resize(500, 350)
        if hasattr(self.main_window, '_apply_zoom_to_subwindow'):
            self.main_window._apply_zoom_to_subwindow(sub)
        sub.show()

    def change_base_currency(self, new_currency):
        if new_currency == self.estimate.currency:
            return
        self._save_state()
        self.estimate.currency = new_currency
        self.refresh_view()

    def change_unit(self, new_unit):
        """Updates the estimate's unit and refreshes the display."""
        if new_unit == self.estimate.unit:
            return
        self._save_state()
        self.estimate.unit = new_unit
        self.refresh_view()
        self.stateChanged.emit()

    def change_category(self, new_category):
        """Updates the estimate's category and refreshes the Rate Code."""
        if new_category == getattr(self.estimate, 'category', ""):
            return
        self._save_state()
        self.estimate.category = new_category
        
        # Generate new Rate Code based on the new category
        new_code = self.db_manager.generate_next_rate_code(new_category)
        self.estimate.rate_code = new_code
        
        self.refresh_view()
        self.stateChanged.emit()

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

    def go_to_resource(self, item):
        """Navigates to the master resource in the main database."""
        if hasattr(item, 'item_type') and hasattr(item, 'item_data'):
            rtype = item.item_type
            rdata = item.item_data
            
            # Map type to database table name
            table_map = {
                'material': 'materials',
                'labor': 'labor',
                'equipment': 'equipment',
                'plant': 'plant',
                'indirect_costs': 'indirect_costs'
            }
            table_name = table_map.get(rtype)
            
            # Get resource name using appropriate key for each type
            name_key_map = {
                'materials': 'name',
                'labor': 'trade',
                'equipment': 'name',
                'plant': 'name',
                'indirect_costs': 'description'
            }
            name_key = name_key_map.get(table_name)
            resource_name = rdata.get(name_key)
            
            if self.main_window and table_name and resource_name:
                self.main_window.show_resource_in_database(table_name, resource_name)

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
        # Sync latest notes from UI FIRST (before any potential refresh_view() calls)
        self.estimate.notes = self.notes_input.toPlainText().strip()
        
        # Ensure we sync the latest adjustment factor and refresh other totals
        self._handle_factor_formatting()
        
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
            
        if hasattr(self, 'unit_combo'):
            self.unit_combo.blockSignals(True)
            curr_unit = self.estimate.unit or "Item"
            idx = self.unit_combo.findText(curr_unit)
            if idx >= 0:
                self.unit_combo.setCurrentIndex(idx)
            else:
                self.unit_combo.setEditText(curr_unit)
            self.unit_combo.blockSignals(False)
            
        if hasattr(self, 'category_combo'):
            self.category_combo.blockSignals(True)
            curr_cat = getattr(self.estimate, 'category', "")
            idx = self.category_combo.findText(curr_cat)
            if idx >= 0:
                self.category_combo.setCurrentIndex(idx)
            else:
                self.category_combo.setCurrentIndex(-1) # Or keep first if new
            self.category_combo.blockSignals(False)
            
        # Update Summary Labels
        totals = self.estimate.calculate_totals()
        
        # Get adjustment factor
        adj_factor = getattr(self.estimate, 'adjustment_factor', 1.0)
        is_adjusted = (adj_factor != 1.0)
        
        # Update Input if not focused
        if not self.adjstmt_factor_input.hasFocus():
             self.adjstmt_factor_input.setText(f"{adj_factor:.2f}" if is_adjusted else "N/A")

        # Load Notes if not focused
        if not self.notes_input.hasFocus():
            self.notes_input.setPlainText(self.estimate.notes or "")

        # Update Dynamic Status Badge and Window Title
        factor_text = self.adjstmt_factor_input.text().strip().upper()
        if factor_text != "N/A" and factor_text != "" and factor_text != "0.00":
            self.status_badge.setText("ADJUSTED RATE")
            self.status_badge.setStyleSheet("QLabel { border-radius: 12px; font-size: 10px; font-weight: bold; color: white; background-color: #673ab7; border: none; }")
            self.setWindowTitle(f"Edit Rate Build-up: {self.estimate.rate_code} (ADJUSTED)")
            self.subtotal_header_label.setText("Build-up Sub-Total (Sum of Adjusted Net Rates):")
        else:
            self.status_badge.setText("BASE RATE")
            self.status_badge.setStyleSheet("QLabel { border-radius: 12px; font-size: 10px; font-weight: bold; color: #333; background-color: #fbc02d; border: none; }")
            self.setWindowTitle(f"Edit Rate Build-up: {self.estimate.rate_code}")
            self.subtotal_header_label.setText("Build-up Sub-Total (Sum of Net Rates):")

        self.subtotal_label.setText(f"{base_sym}{totals['subtotal']:,.2f}")
        self.overhead_label.setText(f"{base_sym}{totals['overhead']:,.2f}")
        self.profit_label.setText(f"{base_sym}{totals['profit']:,.2f}")
        self.total_label.setText(f"{base_sym}{totals['grand_total']:,.2f}")

        # Update dynamic labels
        if hasattr(self, 'desc_label'):
            self.desc_label.setText(f"{self.estimate.project_name} (Unit: {self.estimate.unit or 'N/A'})")
        if hasattr(self, 'title_label'):
            self.title_label.setText(f"{self.estimate.rate_code}")

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
            
            adj_task_total = task_total * adj_factor
            task_item = QTreeWidgetItem(self.tree, [
                str(i), 
                task.description, 
                "", 
                "", 
                f"{base_sym}{task_total:,.2f}",
                f"{base_sym}{adj_task_total:,.2f}" if is_adjusted else ""
            ])
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
                        "",
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
                    if label_prefix == 'Plant': child.setForeground(1, Qt.GlobalColor.darkYellow)
                    if label_prefix == 'Indirect': child.setForeground(1, Qt.GlobalColor.darkCyan)
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
        self.setMinimumSize(420, 400)
        
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
                
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setStretchLastSection(True)

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
