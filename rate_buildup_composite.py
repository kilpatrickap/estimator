from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, 
                             QHeaderView, QMenu, QMessageBox, QComboBox)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
import copy
from selection_dialogs import RateSelectionDialog

class RateBuildupCompositeWidget(QWidget):
    """Encapsulates the Composite Rate Table for the Rate Build-up Dialog."""
    
    stateChanged = pyqtSignal()
    
    def __init__(self, estimate_object, main_window, db_manager, parent=None):
        super().__init__(parent)
        self.estimate = estimate_object
        self.main_window = main_window
        self.db_manager = db_manager
        self.mismatch_notified = False
        self._init_ui()
        
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.composite_table = QTableWidget()
        headers = ["Rate Code", "Description", "Unit", "Base Curr", "Net Rate", "Convert Unit", "Calculations", "New Net Rate"]
        self.composite_table.setColumnCount(len(headers))
        self.composite_table.setHorizontalHeaderLabels(headers)
        header_view = self.composite_table.horizontalHeader()
        header_view.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header_view.setStretchLastSection(True)
        self.composite_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.composite_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.composite_table.setAlternatingRowColors(True)
        
        self.composite_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.composite_table.customContextMenuRequested.connect(self.show_composite_context_menu)
        self.composite_table.cellDoubleClicked.connect(self.edit_composite_calculation)
        
        layout.addWidget(self.composite_table)

    def show_composite_context_menu(self, pos):
        menu = QMenu(self)
        import_action = menu.addAction("Import Rate")
        import_action.triggered.connect(self.import_composite_rate)
        
        selected_indexes = self.composite_table.selectionModel().selectedRows()
        if selected_indexes:
            row = selected_indexes[0].row()
            if row < len(getattr(self.estimate, 'sub_rates', [])):
                menu.addSeparator()
                
                sync_action = menu.addAction("Sync with Database")
                sync_action.triggered.connect(lambda: self.sync_sub_rate(row))
                
                menu.addSeparator()
                
                insert_action = menu.addAction("Insert Rate")
                insert_action.triggered.connect(lambda: self.insert_composite_rate(row))
                
                goto_action = menu.addAction("Go To Rate")
                goto_action.triggered.connect(lambda: self.go_to_composite_rate(row))
                
                remove_action = menu.addAction("Remove Rate")
                remove_action.triggered.connect(lambda: self.remove_composite_rate(row))
                
        menu.exec(self.composite_table.viewport().mapToGlobal(pos))

    def import_composite_rate(self):
        dialog = RateSelectionDialog(self)
        if dialog.exec() and dialog.selected_rate_id:
            db_id = dialog.selected_rate_id
            
            selected_estimate = self.db_manager.load_estimate_details(db_id)
            if not selected_estimate:
                QMessageBox.warning(self, "Error", "Failed to load rate details from database.")
                return
                
            if selected_estimate.unit != self.estimate.unit:
                QMessageBox.warning(self, "Unit Mismatch",
                    f"The imported rate unit '{selected_estimate.unit}' does not match the current rate unit '{self.estimate.unit}'.\n\n"
                    "Please convert the imported rate unit and its calculations to match after importing.")

            reply = QMessageBox.question(
                self, 'Import Rate',
                f"Are you sure you want to add rate '{selected_estimate.rate_code}' to the composite build-up?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                new_sub = copy.deepcopy(selected_estimate)
                self.estimate.add_sub_rate(new_sub)
                self.stateChanged.emit()

    def sync_sub_rate(self, sub_idx):
        sub_obj = self.estimate.sub_rates[sub_idx]
        name = f"{getattr(sub_obj, 'rate_code', '')}: {getattr(sub_obj, 'project_name', '')}"
        
        db_id = getattr(sub_obj, 'id', None)
        if not db_id:
            for r in self.db_manager.get_rates_data():
                # In db_manager.get_rates_data(), r is a dict if factory used, or tuple. 
                # According to rate_buildup_dialog, it was accessed as r[1] or dict r['rate_code']? Wait, let me check.
                # The existing code did `r[1] == getattr(sub_obj, 'rate_code', '')`
                
                # We'll adapt based on dictionary vs tuple
                r_code = r.get('rate_code') if isinstance(r, dict) else r[1]
                r_id = r.get('id') if isinstance(r, dict) else r[0]
                if r_code == getattr(sub_obj, 'rate_code', ''):
                    db_id = r_id
                    break
        
        if not db_id:
            QMessageBox.warning(self, "Error", f"No database record exists for '{name}'.")
            return
            
        new_sub = self.db_manager.load_estimate_details(db_id)
        if not new_sub:
            QMessageBox.warning(self, "Error", f"Failed to load updated data for '{name}'.")
            return
            
        # Keep old converted unit and quantity
        new_sub.converted_unit = getattr(sub_obj, 'converted_unit', getattr(sub_obj, 'unit', ''))
        new_sub.quantity = getattr(sub_obj, 'quantity', 1.0)
        
        self.estimate.sub_rates[sub_idx] = new_sub
        
        self.stateChanged.emit()
        
        QMessageBox.information(
            self, 
            "Sync Successful", 
            f"'{name}' has been synced with the latest changes from the database.\n\n"
            "Please check for any unit mismatches and calculation changes in the Composite rate table below.\n\n"
            "Once verified, right-click the rate and select 'Insert Rate' to update its calculations in the main Edit Rate Build-up table."
        )

    def insert_composite_rate(self, row):
        if row >= len(self.estimate.sub_rates): return
        sub = self.estimate.sub_rates[row]
        
        imported_task = None
        for task in self.estimate.tasks:
            if task.description == "Imported Rates":
                imported_task = task
                break
                
        if not imported_task:
            from models import Task
            imported_task = Task("Imported Rates")
            self.estimate.add_task(imported_task)
            
        qty = getattr(sub, 'quantity', 1.0)
        calc_subtotal = sub.calculate_totals()['subtotal']
        name = f"{getattr(sub, 'rate_code', '')}: {getattr(sub, 'project_name', '')}"
        
        existing_mat = None
        for m in imported_task.materials:
            if m.get('name') == name:
                existing_mat = m
                break
                
        if existing_mat:
            existing_mat['qty'] = qty
            existing_mat['unit'] = getattr(sub, 'converted_unit', sub.unit)
            existing_mat['unit_cost'] = calc_subtotal
            existing_mat['currency'] = sub.currency
            existing_mat['total'] = calc_subtotal * qty
            QMessageBox.information(self, "Rate Updated", f"Calculations and Net Rate for '{name}' have been successfully updated in the Edit Rate Build-up table.")
        else:
            imported_task.add_material(
                name=name,
                quantity=qty,
                unit=getattr(sub, 'converted_unit', sub.unit),
                unit_cost=calc_subtotal,
                currency=sub.currency
            )
            
        self.stateChanged.emit()

    def go_to_composite_rate(self, row):
        if row < len(self.estimate.sub_rates):
            sub = self.estimate.sub_rates[row]
            rate_code = getattr(sub, 'rate_code', '')
            if rate_code and self.main_window and hasattr(self.main_window, 'show_rate_in_database'):
                self.main_window.show_rate_in_database(rate_code)

    def remove_composite_rate(self, index):
        if 0 <= index < len(self.estimate.sub_rates):
            reply = QMessageBox.question(
                self, 'Remove Rate',
                "Are you sure you want to remove this rate from the composite build-up?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.estimate.remove_sub_rate(index)
                self.stateChanged.emit()

    def edit_composite_calculation(self, row, col):
        if col != 6: # Calculations column
            return
            
        if row >= len(self.estimate.sub_rates):
            return
            
        sub = self.estimate.sub_rates[row]
        totals = sub.calculate_totals()
        
        class SubRateAdapterProxy(dict):
            def __setitem__(self_proxy, key, value):
                super().__setitem__(key, value)
                if key == 'qty':
                    sub.quantity = value
                    name_str = f"{getattr(sub, 'rate_code', '')}: {getattr(sub, 'project_name', '')}"
                    for task in self.estimate.tasks:
                        if task.description == "Imported Rates":
                            for m in task.materials:
                                if m.get('name') == name_str:
                                    m['qty'] = value
                                    m['total'] = value * m.get('unit_cost', 0.0)
                elif key == 'formula':
                    sub.formula = value

        mock_item = SubRateAdapterProxy({
            'name': getattr(sub, 'project_name', ''),
            'qty': getattr(sub, 'quantity', 1.0),
            'formula': getattr(sub, 'formula', None),
            'unit_cost': totals['grand_total'] 
        })
        
        if self.main_window and hasattr(self.main_window, 'open_edit_item_window'):
            self.main_window.open_edit_item_window(
                mock_item, 'material', self.estimate.currency, self, 
                custom_title=f"Convert Unit: {getattr(sub, 'rate_code', '')}"
            )
        else:
            from edit_item_dialog import EditItemDialog
            dialog = EditItemDialog(mock_item, 'material', self.estimate.currency, self)
            dialog.setWindowTitle(f"Convert Unit: {getattr(sub, 'rate_code', '')}")
            
            if dialog.exec():
                sub.quantity = mock_item['qty']
                sub.formula = mock_item['formula']
                self.stateChanged.emit()

    def _update_sub_rate_unit(self, sub_estimate, new_unit):
        current = getattr(sub_estimate, 'converted_unit', sub_estimate.unit)
        if current != new_unit:
            sub_estimate.converted_unit = new_unit
            self.stateChanged.emit()

    def refresh_ui(self):
        self.composite_table.setRowCount(0)
        
        mismatched_rates = []
        
        for sub in getattr(self.estimate, 'sub_rates', []):
            row = self.composite_table.rowCount()
            self.composite_table.insertRow(row)
            
            totals = sub.calculate_totals()
            
            items = [
                QTableWidgetItem(str(getattr(sub, 'rate_code', ''))),
                QTableWidgetItem(str(getattr(sub, 'project_name', ''))),
                QTableWidgetItem(str(getattr(sub, 'unit', ''))),
                QTableWidgetItem(str(getattr(sub, 'currency', ''))),
                QTableWidgetItem(f"{totals['subtotal']:,.2f}"),
                None, # Convert Unit
                QTableWidgetItem(f"{getattr(sub, 'quantity', 1.0):.2f}"), # Calculations
                QTableWidgetItem(f"{(totals['subtotal'] * getattr(sub, 'quantity', 1.0)):,.2f}") # New Net Rate
            ]
            for col, item in enumerate(items):
                if item:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    if col == 0:
                        item.setData(Qt.ItemDataRole.UserRole, sub)
                    self.composite_table.setItem(row, col, item)
            
            combo = QComboBox()
            units_list = ["m", "m2", "m3", "kg", "t", "Item"]
            
            if sub.unit and sub.unit not in units_list:
                units_list.append(sub.unit)
                
            converted_unit = getattr(sub, 'converted_unit', sub.unit)
            if converted_unit and converted_unit not in units_list:
                units_list.append(converted_unit)
                
            combo.addItems(units_list)
            combo.setEditable(True)
            combo.setCurrentText(converted_unit or "")
            
            if converted_unit != self.estimate.unit:
                combo.setStyleSheet("color: red; font-weight: bold;")
                mismatched_rates.append(getattr(sub, 'rate_code', 'Unknown Rate'))
            else:
                combo.setStyleSheet("")
                
            combo.currentTextChanged.connect(lambda txt, s=sub: self._update_sub_rate_unit(s, txt))
            self.composite_table.setCellWidget(row, 5, combo)
                
        self.composite_table.resizeColumnsToContents()
        self.composite_table.horizontalHeader().setStretchLastSection(True)
        
        if mismatched_rates and not self.mismatch_notified:
            self.mismatch_notified = True
            QMessageBox.warning(self, "Unit Mismatches Detected", 
                f"The following imported rates have units that do not match the current rate unit ({self.estimate.unit}):\n"
                f"{', '.join(mismatched_rates)}\n\n"
                f"Please convert the imported rate units and review their calculations to match.")
