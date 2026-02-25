from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTreeWidget, 
                             QTreeWidgetItem, QHeaderView, QLabel, QFrame, QPushButton,
                             QInputDialog, QMessageBox, QLineEdit, QTableWidget, QTableWidgetItem,
                             QComboBox, QMenu, QFormLayout, QTextEdit, QSplitter, QWidget,
                             QRadioButton, QButtonGroup)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QDoubleValidator
from database import DatabaseManager
from edit_item_dialog import EditItemDialog
from currency_conversion_dialog import CurrencyConversionDialog
from selection_dialogs import CostSelectionDialog, RateSelectionDialog
from event_bus import EventBus
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
        
        self.is_loading = False
        
        # Track items updated by library changes for highlighting
        self.impacted_resources = set() # Stores (type, name) tuples
        self.show_impact_highlights = True
        self.mismatch_notified = False
        
        self._init_ui()
        self.refresh_view()
        
    def resizeEvent(self, event):
        """Dynamic resizing logic for the notes section."""
        super().resizeEvent(event)
        # We allow full dynamic adjustment now via splitters, 
        # but keep a reasonable base width to prevent accidental collapse
        if hasattr(self, 'notes_widget'):
            self.notes_widget.setMinimumWidth(int(self.rect().width() * 0.4))

    def eventFilter(self, obj, event):
        from PyQt6.QtCore import QEvent
        if obj == self.desc_input and event.type() == QEvent.Type.FocusOut:
            self.on_description_edited()
        return super().eventFilter(obj, event)

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

        # Add Header Widget
        from rate_buildup_header import RateBuildupHeaderWidget
        self.header_widget = RateBuildupHeaderWidget(self.estimate, self)
        
        self.header_widget.descriptionChanged.connect(self._on_header_description_changed)
        self.header_widget.rateTypeChanged.connect(self._toggle_rate_type)
        self.header_widget.categoryChanged.connect(self.change_category)
        self.header_widget.baseCurrencyChanged.connect(self.change_base_currency)
        self.header_widget.unitChanged.connect(self.change_unit)
        self.header_widget.adjustmentFactorChanged.connect(self._on_header_factor_changed)
        self.header_widget.exchangeRatesRequested.connect(self.open_exchange_rates)
        
        layout.addWidget(self.header_widget)

        # Main Vertical Splitter for dynamic height management
        self.main_v_splitter = QSplitter(Qt.Orientation.Vertical)
        self.main_v_splitter.setHandleWidth(8)
        
        # Build-up Tree
        from rate_buildup_tree import RateBuildupTreeWidget
        self.tree_widget = RateBuildupTreeWidget(self.estimate, self.main_window, self.db_manager, self)
        self.tree_widget.stateChanged.connect(self._on_tree_state_changed)
        
        # Composite Table
        from rate_buildup_composite import RateBuildupCompositeWidget
        self.composite_widget = RateBuildupCompositeWidget(self.estimate, self.main_window, self.db_manager, self)
        self.composite_widget.stateChanged.connect(self._on_tree_state_changed)
        
        self.tables_splitter = QSplitter(Qt.Orientation.Vertical)
        self.tables_splitter.addWidget(self.tree_widget)
        self.tables_splitter.addWidget(self.composite_widget)
        self.tables_splitter.setSizes([350, 150]) # Give main tree more space
        
        self.main_v_splitter.addWidget(self.tables_splitter)

        # Add Summary Widget
        from rate_buildup_summary import RateBuildupSummaryWidget
        self.summary_widget = RateBuildupSummaryWidget(self.estimate, self)
        self.summary_widget.notesChanged.connect(self._on_summary_notes_changed)
        self.main_v_splitter.addWidget(self.summary_widget)
        
        self.main_v_splitter.setStretchFactor(0, 4) # Tree takes more height by default
        self.main_v_splitter.setStretchFactor(1, 1) # Summary takes less but is adjustable
        
        layout.addWidget(self.main_v_splitter)

        # Ensure correct visibility of the tables at startup
        self.header_widget.update_rate_type_style()
        self._sync_tables_visibility()
        

    def _sync_tables_visibility(self):
        """Updates the visibility of the tables based on the rate type."""
        if self.estimate.rate_type == 'Simple':
            if hasattr(self, 'composite_widget'): self.composite_widget.hide()
            if hasattr(self, 'tree_widget'): self.tree_widget.show()
        else:
            if hasattr(self, 'composite_widget'): self.composite_widget.show()
            if hasattr(self, 'tree_widget'): self.tree_widget.show()

    def _on_tree_state_changed(self):
        self._save_state()
        self.save_changes(show_message=False)
        self.refresh_view()
        self.stateChanged.emit()

    def _toggle_rate_type(self):
        new_type = 'Simple' if self.estimate.rate_type == 'Composite' else 'Composite'
        if new_type == 'Simple':
            if hasattr(self.estimate, 'sub_rates') and len(self.estimate.sub_rates) > 0:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(self, "Cannot Switch to Simple", 
                                    "This rate currently contains imported rates.\n\n"
                                    "Please remove all imported rates from the composite build-up before switching back to a Simple rate.")
                self.header_widget.update_rate_type_style()
                return

        self._save_state()
        self.estimate.rate_type = new_type
        self.header_widget.update_rate_type_style()
        self._sync_tables_visibility()
        self.save_changes(show_message=False)

    def _on_header_factor_changed(self):
        text = self.header_widget.adjstmt_factor_input.text().strip()
        try:
            if not text or text.upper() == "N/A":
                self.estimate.adjustment_factor = 1.0
            else:
                val = float(text)
                self.estimate.adjustment_factor = val if val > 0 else 1.0
        except ValueError:
            self.estimate.adjustment_factor = 1.0

        self._save_state()
        self.save_changes(show_message=False)
        self.refresh_view()
        self.stateChanged.emit()
        
    def _on_header_description_changed(self):
        new_desc = self.header_widget.desc_input.toPlainText().strip()
        if new_desc and new_desc != self.estimate.project_name:
            self._save_state()
            self.estimate.project_name = new_desc
            self.save_changes(show_message=False)
            self.refresh_view()
        
    def _on_summary_notes_changed(self):
        self._save_state()
        self.save_changes(show_message=False)



    def sync_sub_rate(self, sub_idx):
        sub_obj = self.estimate.sub_rates[sub_idx]
        name = f"{getattr(sub_obj, 'rate_code', '')}: {sub_obj.project_name}"
        
        # 2. Re-load from DB
        db_id = getattr(sub_obj, 'id', None)
        from database import DatabaseManager
        rates_db = DatabaseManager("construction_rates.db")
        
        if not db_id:
            for r in rates_db.get_rates_data():
                if r[1] == getattr(sub_obj, 'rate_code', ''):
                    db_id = r[0]
                    break
        
        if not db_id:
            QMessageBox.warning(self, "Error", f"No database record exists for '{name}'.")
            return
            
        new_sub = rates_db.load_estimate_details(db_id)
        if not new_sub:
            QMessageBox.warning(self, "Error", f"Failed to load updated data for '{name}'.")
            return
            
        self._save_state()
        
        # Keep old converted unit and quantity so the user's local work isn't fully wiped out seamlessly
        new_sub.converted_unit = getattr(sub_obj, 'converted_unit', getattr(sub_obj, 'unit', ''))
        new_sub.quantity = getattr(sub_obj, 'quantity', 1.0)
        
        # 3. Replace in sub-rates
        self.estimate.sub_rates[sub_idx] = new_sub
        
        self.refresh_view()
        self.save_changes(show_message=False)
        
        QMessageBox.information(
            self, 
            "Sync Successful", 
            f"'{name}' has been synced with the latest changes from the database.\n\n"
            "Please check for any unit mismatches and calculation changes in the Composite rate table below.\n\n"
            "Once verified, right-click the rate and select 'Insert Rate' to update its calculations in the main Edit Rate Build-up table."
        )



    def open_exchange_rates(self):
        """Opens exchange rate settings in MDI."""
        for sub in self.main_window.mdi_area.subWindowList():
            if isinstance(sub.widget(), CurrencyConversionDialog):
                self.main_window.mdi_area.setActiveSubWindow(sub)
                return
                
        dialog = CurrencyConversionDialog(self.estimate, self)
        sub = self.main_window.mdi_area.addSubWindow(dialog)
        
        # Color code border
        if hasattr(self.main_window, '_get_color_for_rate') and hasattr(self.estimate, 'rate_code'):
            color = self.main_window._get_color_for_rate(self.estimate.rate_code)
            if color != "transparent":
                sub.setStyleSheet(f"QMdiSubWindow {{ border: 4px solid {color}; background-color: #ffffff; }}")
        
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
        
        self.save_changes(show_message=False)
        self.refresh_view()
        self.stateChanged.emit()

    def on_description_edited(self):
        """Handles manual editing of the main Rate Description."""
        new_desc = self.desc_input.toPlainText().strip()
        if new_desc and new_desc != self.estimate.project_name:
            self._save_state()
            self.estimate.project_name = new_desc
            self.save_changes(show_message=False)
            self.refresh_view()

    def handle_library_update(self, table_name, resource_name, new_val, new_curr, new_unit="", auto_update=False):
        """Checks if this rate uses the updated resource and prompts to update."""
        # Map table_name back to item_type
        type_map = {
            'materials': 'material',
            'labor': 'labor',
            'equipment': 'equipment',
            'plant': 'plant',
            'indirect_costs': 'indirect_costs'
        }
        item_type = type_map.get(table_name)
        if not item_type: return

        # Map item_type back to internal name keys (for matching)
        name_key_map = {
            'material': 'name',
            'labor': 'trade',
            'equipment': 'name',
            'plant': 'name',
            'indirect_costs': 'description'
        }
        name_key = name_key_map.get(item_type)
        rate_key = 'price' if item_type == 'material' else ('amount' if item_type == 'indirect_costs' else 'rate')

        affected_items = []
        for task in self.estimate.tasks:
            # Check corresponding list based on type
            list_attr = table_name # materials, labor, etc happens to match
            items = getattr(task, list_attr, [])
            for item in items:
                if item.get(name_key) == resource_name:
                    # Check if actually different
                    if item.get(rate_key) != new_val or item.get('currency') != new_curr or (new_unit and item.get('unit') != new_unit):
                        affected_items.append(item)

        if affected_items:
            if auto_update:
                reply = QMessageBox.StandardButton.Yes
            else:
                reply = QMessageBox.question(self, "Library Resource Updated",
                                           f"The resource '{resource_name}' was updated in the library.\n\n"
                                           f"Rate {self.estimate.rate_code} uses this resource. Do you want to update it to the new rate and currency: {new_curr} {new_val:,.2f}?",
                                           QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                           QMessageBox.StandardButton.Yes)
            
            if reply == QMessageBox.StandardButton.Yes:
                self._save_state()
                for item in affected_items:
                    item[rate_key] = new_val
                    if new_curr: item['currency'] = new_curr
                    if new_unit: item['unit'] = new_unit
                    # Recalculate item total (depends on qty)
                    qty_key = 'qty' if item_type == 'material' else ('amount' if item_type == 'indirect_costs' else 'hours')
                    item['total'] = item[qty_key] * new_val
                
                # Mark as impacted for highlighting
                self.impacted_resources.add((item_type, resource_name))
                self.refresh_view()
                self.stateChanged.emit()

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
                        if not sub_rates_affected and not affected_items:
                            self._save_state()
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
            
            if sub_rates_affected and not affected_items:
                self.refresh_view()
                self.stateChanged.emit()

    def save_changes(self, show_message=True):
        """Saves the modified rate build-up back to the rates database."""
        # Note: UI inputs are already synchronized with self.estimate via Event signals
        
        # Update timestamp to the current time of archiving/saving
        self.estimate.date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        if self.db_manager.save_estimate(self.estimate):
            self.dataCommitted.emit()
            if show_message:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.information(self, "Success", "Rate build-up updated successfully.")
        else:
            if show_message:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.critical(self, "Error", "Failed to save changes.")

    def closeEvent(self, event):
        """Automatically save changes when the window is closed."""
        self.save_changes(show_message=False)
        super().closeEvent(event)

    def refresh_view(self):
        self.is_loading = True
        
        # Update currency symbol
        match = re.search(r'\((.*?)\)', self.estimate.currency)
        self.currency_symbol = match.group(1) if match else "$"
        
        base_sym = self.currency_symbol
        
        self.header_widget.refresh_ui()
        self.summary_widget.refresh_ui()
        
        # Update Summary Labels
        totals = self.estimate.calculate_totals()
        
        # Format for summary
        totals_dict = {
            'subtotal': totals['subtotal'],
            'overhead': totals['overhead'],
            'profit': totals['profit'],
            'grand_total': totals['grand_total']
        }
        self.summary_widget.update_totals(totals_dict, base_sym=base_sym)
        
        adj_factor = getattr(self.estimate, 'adjustment_factor', 1.0)
        is_adjusted = (adj_factor != 1.0)

        # Update Dynamic Status Badge and Window Title
        if is_adjusted:
            self.header_widget.status_badge.setText("ADJUSTED RATE")
            self.header_widget.status_badge.setStyleSheet("QLabel { border-radius: 11px; font-size: 8px; font-weight: bold; color: white; background-color: #673ab7; border: none; }")
            self.setWindowTitle(f"Edit Rate Build-up: {self.estimate.rate_code} (ADJUSTED)")
            self.summary_widget.subtotal_header_label.setText("Build-up Sub-Total (Sum of Adjusted Net Rates):")
        else:
            self.header_widget.status_badge.setText("BASE RATE")
            self.header_widget.status_badge.setStyleSheet("QLabel { border-radius: 11px; font-size: 8px; font-weight: bold; color: #333; background-color: #fbc02d; border: none; }")
            self.setWindowTitle(f"Edit Rate Build-up: {self.estimate.rate_code}")
            self.summary_widget.subtotal_header_label.setText("Build-up Sub-Total (Sum of Net Rates):")

        if hasattr(self, 'show_impact_highlights'):
            self.tree_widget.set_impact_highlights(self.show_impact_highlights, getattr(self, 'impacted_resources', set()))
        else:
            self.tree_widget.refresh_ui()
        
        # Refresh Composite Table
        if hasattr(self, 'composite_widget'):
            self.composite_widget.refresh_ui()
        
        self.is_loading = False
        # self._update_undo_redo_buttons()

