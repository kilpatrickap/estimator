from datetime import datetime
import re
import copy

from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                             QTreeWidget, QTreeWidgetItem, QLabel, QFormLayout, QMessageBox,
                             QInputDialog, QDialog, QTableWidget, QTableWidgetItem, QHeaderView,
                             QFileDialog, QDialogButtonBox, QLineEdit,
                             QSplitter, QFrame)
from PyQt6.QtGui import QFont, QKeySequence
from PyQt6.QtCore import Qt, QDate, QTimer, pyqtSignal

from database import DatabaseManager
from models import Estimate, Task
from report_generator import ReportGenerator
from currency_conversion_dialog import CurrencyConversionDialog
from profit_overhead_dialog import ProfitOverheadDialog
from edit_item_dialog import EditItemDialog


class EstimateWindow(QMainWindow):
    """
    Main window for editing a specific Estimate.
    """
    stateChanged = pyqtSignal()

    def __init__(self, estimate_data=None, estimate_object=None, main_window=None, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.db_manager = DatabaseManager()

        if estimate_object:
            self.estimate = estimate_object
        elif estimate_data:
            self.estimate = Estimate(
                project_name=estimate_data['name'],
                client_name=estimate_data['client'],
                overhead=estimate_data['overhead'],
                profit=estimate_data['profit'],
                currency=estimate_data.get('currency', "GHS (₵)"),
                date=estimate_data.get('date')
            )
        else:
            self.estimate = Estimate("Error", "Error", 0, 0)

        # Undo/Redo Stacks
        self.undo_stack = []
        self.redo_stack = []

        # Setup Auto-Save
        self.autosave_timer = QTimer(self)
        self.autosave_timer.timeout.connect(self.auto_save)
        self.autosave_timer.start(60000)  # Auto-save every 60 seconds

        self.setWindowTitle(f"Estimate: {self.estimate.project_name}")
        self.setMinimumSize(900, 600)

        # Extract currency symbol
        match = re.search(r'\((.*?)\)', self.estimate.currency)
        self.currency_symbol = match.group(1) if match else "$"

        self._init_ui()

    def _init_ui(self):
        """Initializes the UI components."""
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)

        # --- Toolbar / Action Bar for Undo/Redo ---
        # REMOVED: Undo/Redo/Save buttons are now in the main window toolbar.


        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        
        self.splitter.addWidget(self._create_tree_panel())
        self.splitter.addWidget(self._create_summary_panel())
        
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 1)
        
        self.main_layout.addWidget(self.splitter)
        self.refresh_view()

    def _create_tree_panel(self):
        """Creates the left panel with TreeWidget and buttons."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Ref", "Tasks", "Calculations", "Cost", "Net Rate"])
        header = self.tree.header()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)
        self.tree.setIndentation(15)
        layout.addWidget(self.tree)

        # Action Buttons
        btn_layout = QHBoxLayout()
        buttons = [
            ("Add Task", self.add_task),
            ("Add Material", lambda _: self._add_resource("materials")),
            ("Add Labor", lambda _: self._add_resource("labor")),
            ("Add Equipment", lambda _: self._add_resource("equipment")),
            ("Add Plant", lambda _: self._add_resource("plant")),
            ("Add Indirect Cost", lambda _: self._add_resource("indirect_costs")),
            ("Remove Selected", self.remove_item)
        ]

        for text, slot in buttons:
            btn = QPushButton(text)
            btn.setMinimumHeight(40)
            btn.clicked.connect(slot)
            if text == "Remove Selected":
                btn.setStyleSheet("""
                    QPushButton { background-color: #d32f2f; color: white; }
                    QPushButton:hover { background-color: #ef5350; }
                """)
            btn_layout.addWidget(btn)

        layout.addLayout(btn_layout)
        
        self.tree.itemDoubleClicked.connect(self.edit_item)
        return panel

    def _create_summary_panel(self):
        """Creates the right panel with summary and main actions."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 0, 0, 0)

        # Summary Box
        summary_group = QFrame()
        summary_group.setFrameShape(QFrame.Shape.StyledPanel)
        summary_group.setStyleSheet("QFrame { background-color: #ffffff; border: 1px solid #dcdfe6; border-radius: 8px; } QLabel { border: none; }")
        
        form_layout = QFormLayout(summary_group)
        form_layout.setContentsMargins(10, 10, 10, 10)
        form_layout.setSpacing(5)

        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(13)
        summary_title = QLabel("Project Summary")
        summary_title.setFont(title_font)
        summary_title.setStyleSheet("color: #2e7d32; margin-bottom: 10px;")
        form_layout.addRow(summary_title)

        value_font = QFont()
        value_font.setPointSize(10)

        self.subtotal_label = QLabel(f"{self.currency_symbol}0.00")
        self.overhead_label = QLabel(f"{self.currency_symbol}0.00")
        self.profit_label = QLabel(f"{self.currency_symbol}0.00")
        self.grand_total_label = QLabel(f"{self.currency_symbol}0.00")
        
        for lbl in [self.subtotal_label, self.overhead_label, self.profit_label]:
            lbl.setFont(value_font)
            lbl.setAlignment(Qt.AlignmentFlag.AlignRight)

        grand_font = QFont()
        grand_font.setBold(True)
        grand_font.setPointSize(18)
        self.grand_total_label.setFont(grand_font)
        self.grand_total_label.setStyleSheet("color: #2e7d32;")
        self.grand_total_label.setAlignment(Qt.AlignmentFlag.AlignRight)

        form_layout.addRow("Subtotal:", self.subtotal_label)
        self.overhead_pct_label = QLabel(f"Overhead ({self.estimate.overhead_percent}%):")
        form_layout.addRow(self.overhead_pct_label, self.overhead_label)
        self.profit_pct_label = QLabel(f"Profit ({self.estimate.profit_margin_percent}%):")
        form_layout.addRow(self.profit_pct_label, self.profit_label)
        
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("background-color: #dcdfe6; max-height: 1px;")
        form_layout.addRow(line)
        
        grand_total_desc = QLabel("GRAND TOTAL:")
        grand_total_desc.setFont(grand_font)
        form_layout.addRow(grand_total_desc, self.grand_total_label)
        
        layout.addWidget(summary_group)

        # Main Actions
        action_layout = QVBoxLayout()
        action_layout.setSpacing(10)
        action_layout.setContentsMargins(0, 20, 0, 0)
        
        actions = [
            ("Exchange Rates", self.open_exchange_rates),
            ("Profit & Overheads", self.open_profit_overheads),
            ("Generate Report", self.generate_report),
            ("Convert to Rate", self.convert_to_rate)
        ]
        
        for text, slot in actions:
            btn = QPushButton(text)
            btn.setMinimumHeight(45)
            btn.clicked.connect(slot)
            action_layout.addWidget(btn)

        layout.addLayout(action_layout)
        layout.addStretch()
        return panel

    def convert_to_rate(self):
        """Copies the existing estimate into construction_rates.db with a Rate Code."""
        unit, ok1 = QInputDialog.getText(self, "Rate Unit", "Enter unit for this rate (e.g., m2, kg) [Optional]:")
        notes, ok2 = QInputDialog.getText(self, "Rate Notes", "Enter notes for this rate [Optional]:")

        self.estimate.unit = unit if ok1 else ""
        self.estimate.notes = notes if ok2 else ""
        
        rate_code = self.db_manager.convert_to_rate_db(self.estimate)
        if rate_code:
            QMessageBox.information(self, "Success", f"Estimate successfully converted to rate.\nRate Code: {rate_code}\nSaved in construction_rates.db")
        else:
            QMessageBox.critical(self, "Error", "Failed to convert estimate to rate.")

    # --- UNDO / REDO LOGIC ---
    def save_state(self):
        """Takes a snapshot of the current estimate and pushes it to the undo stack."""
        snapshot = copy.deepcopy(self.estimate)
        self.undo_stack.append(snapshot)
        self.redo_stack.clear() # New action invalidates redo history
        self.stateChanged.emit()

    def undo(self):
        if not self.undo_stack: return
        
        # Save current state to redo stack
        current_state = copy.deepcopy(self.estimate)
        self.redo_stack.append(current_state)
        
        # Restore previous state
        previous_state = self.undo_stack.pop()
        self.estimate = previous_state
        
        self.refresh_view()
        self.stateChanged.emit()
        
        # Ensure currency symbol updates if changed
        match = re.search(r'\((.*?)\)', self.estimate.currency)
        self.currency_symbol = match.group(1) if match else "$"

    def redo(self):
        if not self.redo_stack: return
        
        # Save current state to undo stack
        current_state = copy.deepcopy(self.estimate)
        self.undo_stack.append(current_state)
        
        # Restore next state
        next_state = self.redo_stack.pop()
        self.estimate = next_state
        
        self.refresh_view()
        self.stateChanged.emit()
        
        # Ensure currency symbol updates if changed
        match = re.search(r'\((.*?)\)', self.estimate.currency)
        self.currency_symbol = match.group(1) if match else "$"



    # -------------------------

    def _get_selected_task_object(self):
        """Helper to find the parent task object from any selection in the tree."""
        selected = self.tree.currentItem()
        if not selected:
            QMessageBox.warning(self, "Selection Error", "Please select an item in a task.")
            return None

        # Traverse up to find the task item (which has task_object)
        candidate = selected
        while candidate:
            if hasattr(candidate, 'task_object'):
                return candidate.task_object
            candidate = candidate.parent()
        
        QMessageBox.warning(self, "Selection Error", "Invalid item selected. Please select a task.")
        return None

    def save_estimate(self):
        """Saves the estimate to DB."""
        if not self._confirm_action("Confirm Save", "Do you want to save this estimate?"):
            return

        if self.db_manager.save_estimate(self.estimate):
            QMessageBox.information(self, "Success", "Estimate has been saved successfully.")
        else:
            QMessageBox.critical(self, "Error", "Failed to save the estimate.")

    def auto_save(self):
        """Silently saves the estimate if it has an ID."""
        if self.estimate.id:
            self.db_manager.save_estimate(self.estimate)
            self.statusBar().showMessage(f"Auto-saved at {datetime.now().strftime('%H:%M')}", 3000)

    def _confirm_action(self, title, message):
        reply = QMessageBox.question(self, title, message, 
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        return reply == QMessageBox.StandardButton.Yes

    def open_exchange_rates(self):
        """Opens exchange rate settings in MDI."""
        if not self.main_window:
            return
            
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

    def open_profit_overheads(self):
        self.save_state()
        if ProfitOverheadDialog(self.estimate, self).exec():
            self.refresh_view()
        else:
            self.undo_stack.pop()
            self.stateChanged.emit()

    def edit_item(self, item, column):
        """Opens the edit dialog for the double-clicked item."""
        if hasattr(item, 'item_type') and hasattr(item, 'item_data'):
            if self.main_window and hasattr(self.main_window, 'open_edit_item_window'):
                self.main_window.open_edit_item_window(item.item_data, item.item_type, self.estimate.currency, self)
            else:
                # Fallback
                self.save_state()
                if EditItemDialog(item.item_data, item.item_type, self.estimate.currency, self).exec():
                    self.refresh_view()
                else:
                    self.undo_stack.pop()
                    self.stateChanged.emit()

    def add_task(self):
        text, ok = QInputDialog.getText(self, "Add Task", "Enter task description:")
        if ok and text:
            self.save_state()
            self.estimate.add_task(Task(text))
            self.refresh_view()

    def _add_resource(self, resource_type):
        """Generic method to add material, labor, or equipment."""
        task_obj = self._get_selected_task_object()
        if not task_obj: return

        dialog = SelectItemDialog(resource_type, self)
        if dialog.exec():
            item, quantity, formula = dialog.get_selection()
            if item and quantity > 0:
                self.save_state() # Save before modification
                if resource_type == 'materials':
                    task_obj.add_material(item['name'], quantity, item['unit'], item['price'], currency=item['currency'], formula=formula)
                elif resource_type == 'labor':
                    task_obj.add_labor(item['trade'], quantity, item['rate'], currency=item['currency'], formula=formula, unit=item['unit'])
                elif resource_type == 'equipment':
                    task_obj.add_equipment(item['name'], quantity, item['rate'], currency=item['currency'], formula=formula, unit=item['unit'])
                elif resource_type == 'plant':
                    task_obj.add_plant(item['name'], quantity, item['rate'], currency=item['currency'], formula=formula, unit=item['unit'])
                elif resource_type == 'indirect_costs':
                    task_obj.add_indirect_cost(item['description'], quantity, unit=item['unit'], currency=item['currency'], formula=formula)
                self.refresh_view()

    def remove_item(self):
        selected = self.tree.currentItem()
        if not selected: return

        # Check validity before saving state
        valid_selection = False
        if hasattr(selected, 'item_type'): valid_selection = True
        elif hasattr(selected, 'task_object'): valid_selection = True
        
        if not valid_selection: return

        self.save_state() # Save before delete

        if hasattr(selected, 'item_type'):
            # Removing a child item
            parent_item = selected.parent()
            task_obj = getattr(parent_item, 'task_object', None) # Should adhere to parent's task_object
            if not task_obj: return # Should not happen

            item_data = selected.item_data
            if selected.item_type == 'material':
                task_obj.materials.remove(item_data)
            elif selected.item_type == 'labor':
                task_obj.labor.remove(item_data)
            elif selected.item_type == 'equipment':
                task_obj.equipment.remove(item_data)
            elif selected.item_type == 'plant':
                task_obj.plant.remove(item_data)
            elif selected.item_type == 'indirect_costs':
                task_obj.indirect_costs.remove(item_data)
        
        elif hasattr(selected, 'task_object'):
            # Removing a whole task
            self.estimate.tasks.remove(selected.task_object)

        self.refresh_view()

    def handle_library_update(self, table_name, resource_name, new_val, new_curr, auto_update=False):
        """Silently updates matching resources in this estimate if auto_update is True."""
        if not auto_update:
            return  # For estimates, we only do it if the global prompt was accepted

        type_map = {
            'materials': 'material', 'labor': 'labor', 'equipment': 'equipment',
            'plant': 'plant', 'indirect_costs': 'indirect_costs'
        }
        item_type = type_map.get(table_name)
        if not item_type: return

        name_key_map = {
            'material': 'name', 'labor': 'trade', 'equipment': 'name',
            'plant': 'name', 'indirect_costs': 'description'
        }
        name_key = name_key_map.get(item_type)
        rate_key = 'price' if item_type == 'material' else ('amount' if item_type == 'indirect_costs' else 'rate')

        affected = False
        for task in self.estimate.tasks:
            items = getattr(task, table_name, [])
            for item in items:
                if item.get(name_key) == resource_name:
                    if item.get(rate_key) != new_val or item.get('currency') != new_curr:
                        if not affected:
                            self.save_state()
                            affected = True
                            
                        item[rate_key] = new_val
                        if new_curr: item['currency'] = new_curr
                        qty_key = 'qty' if item_type == 'material' else ('amount' if item_type == 'indirect_costs' else 'hours')
                        
                        qty = item.get(qty_key, 1.0)
                        if item_type == 'indirect_costs':
                            item['amount'] = new_val
                            item['total'] = new_val
                        else:
                            item['total'] = qty * new_val

        if auto_update and hasattr(self.estimate, 'sub_rates') and self.estimate.sub_rates:
            from database import DatabaseManager
            rates_db = DatabaseManager("construction_rates.db")
            
            sub_rates_affected = False
            for sub_idx, sub_obj in enumerate(self.estimate.sub_rates):
                db_id = getattr(sub_obj, 'id', None)
                if not db_id:
                    for r in rates_db.get_rates_data():
                        if r[1] == getattr(sub_obj, 'rate_code', ''):
                            db_id = r[0]
                            break
                            
                if db_id:
                    new_sub = rates_db.load_estimate_details(db_id)
                    if new_sub:
                        if not sub_rates_affected and not affected:
                            self.save_state()
                        sub_rates_affected = True
                        
                        new_sub.converted_unit = getattr(sub_obj, 'converted_unit', getattr(sub_obj, 'unit', ''))
                        new_sub.quantity = getattr(sub_obj, 'quantity', 1.0)
                        
                        self.estimate.sub_rates[sub_idx] = new_sub
                        
                        # Apply to Imported Rates task in UI
                        imported_task = None
                        for task in self.estimate.tasks:
                            if task.description == "Imported Rates":
                                imported_task = task
                                break
                                
                        if imported_task:
                            name_str = f"{getattr(new_sub, 'rate_code', '')}: {new_sub.project_name}"
                            calc_subtotal = new_sub.calculate_totals()['subtotal']
                            for m in imported_task.materials:
                                if m.get('name') == name_str:
                                    m['unit_cost'] = calc_subtotal
                                    m['total'] = calc_subtotal * m.get('qty', 1.0)
                                    
            if sub_rates_affected and not affected:
                affected = True

        if affected:
            self.refresh_view()
            self.stateChanged.emit()

    def refresh_view(self):
        """Refreshes the tree view and summaries."""
        self.tree.clear()
        base_sym = self.currency_symbol

        bold_font = self.tree.font()
        bold_font.setBold(True)

        for i, task in enumerate(self.estimate.tasks, 1):
            # Calculate total for display
            task_total = sum([
                sum(self.estimate._get_item_total_in_base_currency(m) for m in task.materials),
                sum(self.estimate._get_item_total_in_base_currency(l) for l in task.labor),
                sum(self.estimate._get_item_total_in_base_currency(e) for e in task.equipment),
                sum(self.estimate._get_item_total_in_base_currency(p) for p in task.plant),
                sum(self.estimate._get_item_total_in_base_currency(i) for i in task.indirect_costs)
            ])
            
            task_item = QTreeWidgetItem(self.tree, [str(i), task.description, "", "", f"{base_sym}{task_total:,.2f}"])
            task_item.task_object = task
            for col in range(self.tree.columnCount()):
                task_item.setFont(col, bold_font)

            # Define configurations for each type of resource
            # (list_attr, display_name, name_key, unit_func, qty_key, rate_key, type_code)
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
                    child.item_data = item
                    child.item_type = type_code
                    sub_idx += 1

        self.tree.expandAll()
        for i in range(self.tree.columnCount()):
            self.tree.resizeColumnToContents(i)
        
        self.tree.header().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.tree.header().setStretchLastSection(True)

        self.update_summary()

    def update_summary(self):
        totals = self.estimate.calculate_totals()
        sym = self.currency_symbol
        
        self.subtotal_label.setText(f"{sym}{totals['subtotal']:,.2f}")
        self.overhead_pct_label.setText(f"Overhead ({self.estimate.overhead_percent:.2f}%):")
        self.profit_pct_label.setText(f"Profit ({self.estimate.profit_margin_percent:.2f}%):")
        self.overhead_label.setText(f"{sym}{totals['overhead']:,.2f}")
        self.profit_label.setText(f"{sym}{totals['profit']:,.2f}")
        self.grand_total_label.setText(f"{sym}{totals['grand_total']:,.2f}")

    def generate_report(self):
        filename, _ = QFileDialog.getSaveFileName(self, "Export PDF Report", 
                                                  f"{self.estimate.project_name}_estimate.pdf",
                                                  "PDF Files (*.pdf)")
        if filename:
            try:
                company_name = self.db_manager.get_setting("company_name", "")
                company_logo = self.db_manager.get_setting("company_logo", "")
                
                generator = ReportGenerator(self.estimate)
                if generator.export_to_pdf(filename, company_name, company_logo):
                    QMessageBox.information(self, "Success", f"Report successfully exported to:\n{filename}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to generate report:\n{str(e)}")


class SelectItemDialog(QDialog):
    """Dialog for selecting items from the database."""
    def __init__(self, item_type, parent=None):
        super().__init__(parent)
        self.item_type = item_type
        singular_name = item_type[:-1] if item_type.endswith('s') else item_type
        self.setWindowTitle(f"Select {singular_name.capitalize()}")
        self.setMinimumSize(420, 400)
        
        self.db_manager = DatabaseManager()
        self.all_items = self.db_manager.get_items(item_type)
        self.current_items = []

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Search
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search:"))
        search_input = QLineEdit()
        search_input.setPlaceholderText("Type to filter...")
        search_input.textChanged.connect(self.filter_items)
        search_layout.addWidget(search_input)
        layout.addLayout(search_layout)

        # Table
        self.table = QTableWidget()
        self._setup_table_headers()
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setDefaultSectionSize(22)
        self.table.setWordWrap(False)
        self.table.setShowGrid(True)
        self.table.setColumnHidden(0, True) # Hide ID
        layout.addWidget(self.table)

        # Buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        for button in self.button_box.buttons():
            button.setAutoDefault(False)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        self.filter_items("")

    def _setup_table_headers(self):
        if self.item_type == "materials":
            headers = ["ID", "Material", "Unit", "Currency", "Price", "Date", "Location", "Contact", "Remarks"]
        else:
            if self.item_type == "indirect_costs":
                headers = ["ID", "Description", "Unit", "Currency", "Amount", "Date"]
            else:
                name_label = "Labor" if self.item_type == "labor" else ("Plant" if self.item_type == "plant" else "Equipment")
                headers = ["ID", name_label, "Unit", "Currency", "Rate", "Date", "Location", "Contact", "Remarks"]
        
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setStretchLastSection(True)

    def filter_items(self, text):
        search_text = text.lower()
        self.current_items = [
            item for item in self.all_items 
            if search_text in item[1].lower() # item[1] is name/trade
        ]

        self.table.setRowCount(len(self.current_items))
        for row, item_data in enumerate(self.current_items):
            self._fill_row(row, item_data)
        
        self.table.resizeColumnsToContents()
        self.table.resizeRowsToContents()
            
    def _fill_row(self, row, item_data):
        self.table.setItem(row, 0, QTableWidgetItem(str(item_data[0]))) # ID
        self.table.setItem(row, 1, QTableWidgetItem(item_data[1])) # Name
        
        col_offset = 2
        if self.item_type == "materials":
            self.table.setItem(row, 2, QTableWidgetItem(str(item_data[2]))) # Unit
            self.table.setItem(row, 3, QTableWidgetItem(str(item_data[3]))) # Currency
            self.table.setItem(row, 4, QTableWidgetItem(f"{float(item_data[4]):,.2f}")) # Price
            date_idx = 5
        else:
            self.table.setItem(row, 2, QTableWidgetItem(str(item_data[2]))) # Unit
            self.table.setItem(row, 3, QTableWidgetItem(str(item_data[3]))) # Currency
            self.table.setItem(row, 4, QTableWidgetItem(f"{float(item_data[4]):,.2f}")) # Rate
            date_idx = 5
            
        # Common end columns
        qdate = QDate.fromString(str(item_data[date_idx]), "yyyy-MM-dd")
        display_date = qdate.toString("dd-MM-yy") if qdate.isValid() else str(item_data[date_idx])
        
        if self.item_type == "indirect_costs":
             self.table.setItem(row, 5, QTableWidgetItem(display_date))
             return

        self.table.setItem(row, col_offset + (3 if self.item_type == "materials" else 2), QTableWidgetItem(display_date))
        
        # Location, Contact, Remarks
        for i in range(1, 4):
             val = item_data[date_idx + i] if len(item_data) > date_idx + i else ""
             self.table.setItem(row, (6 if self.item_type == "materials" else 6) + i - 1, QTableWidgetItem(str(val) if val else ""))

    def get_selection(self):
        """Returns the selected item, quantity (default 1), and formula (None)."""
        selected_row = self.table.currentRow()
        if selected_row < 0:
            return None, 0, None
            
        return self.current_items[selected_row], 1.00, None
