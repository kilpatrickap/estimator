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
    
    def __init__(self, estimate_object, main_window=None, parent=None, db_path=None):
        super().__init__(parent)
        self.estimate = estimate_object
        self.main_window = main_window
        self.db_path = db_path
        self.db_manager = DatabaseManager(db_path if db_path else "construction_rates.db")
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
        self.is_dirty = False
        
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
        self.is_dirty = True
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
        # self.save_changes(show_message=False)
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
        # self.save_changes(show_message=False)

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
        # self.save_changes(show_message=False)
        self.refresh_view()
        self.stateChanged.emit()
        
    def _on_header_description_changed(self):
        new_desc = self.header_widget.desc_input.toPlainText().strip()
        if new_desc and new_desc != self.estimate.project_name:
            self._save_state()
            self.estimate.project_name = new_desc
            # self.save_changes(show_message=False)
            self.refresh_view()
        
    def _on_summary_notes_changed(self):
        self._save_state()
        # self.save_changes(show_message=False)



    def sync_sub_rate(self, sub_idx):
        sub_obj = self.estimate.sub_rates[sub_idx]
        name = f"{getattr(sub_obj, 'rate_code', '')}: {sub_obj.project_name}"
        
        # 2. Re-load from DB
        db_id = getattr(sub_obj, 'id', None)
        from database import DatabaseManager
        rates_db = DatabaseManager(self.db_manager.db_file)
        
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
        # self.save_changes(show_message=False)
        
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
                sub.widget().populate_table()
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
        
        # self.save_changes(show_message=False)
        self.refresh_view()
        self.stateChanged.emit()

    def on_description_edited(self):
        """Handles manual editing of the main Rate Description."""
        new_desc = self.desc_input.toPlainText().strip()
        if new_desc and new_desc != self.estimate.project_name:
            self._save_state()
            self.estimate.project_name = new_desc
            # self.save_changes(show_message=False)
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
            rates_db = DatabaseManager(self.db_manager.db_file)
            
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
            self.is_dirty = False
            self.dataCommitted.emit()
            
            # Global Sync
            self._trigger_global_sync()

            if show_message:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.information(self, "Success", "Rate build-up updated successfully.")
        else:
            if show_message:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.critical(self, "Error", "Failed to save changes.")

    def closeEvent(self, event):
        """Confirm to the User whether he would like to save or not."""
        if getattr(self, 'is_dirty', False):
            from PyQt6.QtWidgets import QMessageBox
            reply = QMessageBox.question(
                self, 
                "Save Changes", 
                "Do you want to save your changes to this rate build-up before closing?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Yes
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.save_changes(show_message=False)
                event.accept()
            elif reply == QMessageBox.StandardButton.No:
                event.accept()
            else:
                event.ignore()
        else:
            super().closeEvent(event)

    def _trigger_global_sync(self):
        """Analyzes impact of the rate change across the whole project and asks user to sync."""
        import os, sqlite3, json
        
        if not self.db_path or "Project Database" not in self.db_path:
            return # Only sync for project-specific rates

        project_dir = os.path.dirname(os.path.dirname(os.path.abspath(self.db_path)))
        rate_code = self.estimate.rate_code
        new_gross = self.estimate.calculate_totals()['grand_total']
        
        sor_dir = os.path.join(project_dir, "SOR")
        pboq_dir = os.path.join(project_dir, "Priced BOQs")
        
        impact = {'sor': [], 'pboq': []} # List of (path, count)
        rate_code_clean = rate_code.strip().upper()

        # 1. Analyze SOR impact
        if os.path.exists(sor_dir):
            for f in os.listdir(sor_dir):
                if not f.lower().endswith('.db'): continue
                path = os.path.join(sor_dir, f)
                try:
                    conn = sqlite3.connect(path)
                    cursor = conn.cursor()
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sor_items'")
                    if cursor.fetchone():
                        cursor.execute("PRAGMA table_info(sor_items)")
                        cols = [i[1] for i in cursor.fetchall()]
                        if "RateCode" in cols:
                            # Use Trim/Upper for robust matching
                            cursor.execute("SELECT COUNT(*) FROM sor_items WHERE TRIM(UPPER(RateCode)) = ?", (rate_code_clean,))
                            count = cursor.fetchone()[0]
                            if count > 0: impact['sor'].append((path, count))
                    conn.close()
                except: pass

        # 2. Analyze PBOQ impact
        if os.path.exists(pboq_dir):
            for f in os.listdir(pboq_dir):
                if not f.lower().endswith('.db'): continue
                path = os.path.join(pboq_dir, f)
                try:
                    # Discover Mapping for this file to search accurately
                    mapping = None
                    if self.main_window:
                        for sub in self.main_window.mdi_area.subWindowList():
                            w = sub.widget()
                            if getattr(w, '__class__', None).__name__ == 'PBOQDialog':
                                if hasattr(w, 'pboq_file_selector') and w.pboq_file_selector.currentData() == path:
                                    mapping = w.tools_pane.get_mappings()
                                    break
                    if not mapping:
                        state_file = os.path.join(project_dir, "PBOQ States", f + ".json")
                        if os.path.exists(state_file):
                            try:
                                with open(state_file, 'r') as sf:
                                    st_json = json.load(sf)
                                    mapping = st_json.get('mappings')
                            except: pass

                    conn = sqlite3.connect(path)
                    cursor = conn.cursor()
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pboq_items'")
                    if cursor.fetchone():
                        cursor.execute("PRAGMA table_info(pboq_items)")
                        db_cols = [info[1] for info in cursor.fetchall()]
                        
                        found_count = 0
                        # 1. Try Mapping Search
                        if mapping and mapping.get('rate_code', -1) >= 0:
                            db_idx = mapping['rate_code'] + 1
                            if db_idx < len(db_cols):
                                try:
                                    cursor.execute(f'SELECT COUNT(*) FROM pboq_items WHERE TRIM(UPPER("{db_cols[db_idx]}")) = ?', (rate_code_clean,))
                                    found_count = cursor.fetchone()[0]
                                except: pass
                        
                        # 2. Try Logical 'RateCode' Column Search
                        if found_count == 0 and "RateCode" in db_cols:
                            try:
                                cursor.execute('SELECT COUNT(*) FROM pboq_items WHERE TRIM(UPPER(RateCode)) = ?', (rate_code_clean,))
                                found_count = cursor.fetchone()[0]
                            except: pass
                        
                        # 3. Brute Force Search all columns as final fallback
                        if found_count == 0:
                            try:
                                conditions = " OR ".join([f'TRIM(UPPER("{c}")) = ?' for c in db_cols])
                                cursor.execute(f"SELECT COUNT(*) FROM pboq_items WHERE {conditions}", [rate_code_clean] * len(db_cols))
                                found_count = cursor.fetchone()[0]
                            except: pass
                        
                        if found_count > 0:
                            impact['pboq'].append((path, found_count))
                    conn.close()
                except: pass

        if not impact['sor'] and not impact['pboq']:
            return

        # 3. Present to user
        msg = f"<b>Rate Sync Notification</b><br><br>The rate <b>{rate_code}</b> has been updated.<br><br>"
        if impact['sor']:
            total_sor = sum(c for p, c in impact['sor'])
            msg += f"• Found <b>{total_sor}</b> SOR item(s) in {len(impact['sor'])} file(s).<br>"
        if impact['pboq']:
            total_pboq = sum(c for p, c in impact['pboq'])
            msg += f"• Found <b>{total_pboq}</b> PBOQ row(s) in {len(impact['pboq'])} file(s).<br>"
        
        msg += "<br>Would you like to synchronize all project files with this new rate?"
        
        reply = QMessageBox.question(self, "Global Project Sync", msg, 
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
                                   QMessageBox.StandardButton.Yes)
        
        if reply == QMessageBox.StandardButton.Yes:
            self._perform_global_sync(project_dir, rate_code, new_gross, impact)

    def _perform_global_sync(self, project_dir, rate_code, new_gross, impact):
        """Executes the actual database updates and UI refreshes."""
        import sqlite3, json, os
        new_gross_str = "{:,.2f}".format(new_gross)
        rate_code_clean = rate_code.strip().upper()

        # 1. Update SOR Files
        for path, count in impact['sor']:
            try:
                conn = sqlite3.connect(path)
                cursor = conn.cursor()
                cursor.execute("UPDATE sor_items SET GrossRate = ? WHERE TRIM(UPPER(RateCode)) = ?", (new_gross_str, rate_code_clean))
                conn.commit()
                conn.close()
            except: pass

        # 2. Update PBOQ Files
        states_dir = os.path.join(project_dir, "PBOQ States")
        for path, count in impact['pboq']:
            try:
                # 1. Identify Mappings (Priority: Open Viewer > Saved State > Defaults)
                mappings = None
                if self.main_window:
                    for sub in self.main_window.mdi_area.subWindowList():
                        w = sub.widget()
                        if getattr(w, '__class__', None).__name__ == 'PBOQDialog':
                            if hasattr(w, 'pboq_file_selector') and w.pboq_file_selector.currentData() == path:
                                if hasattr(w, 'tools_pane'):
                                    mappings = w.tools_pane.get_mappings()
                                    break
                
                if not mappings:
                    st_file = os.path.join(states_dir, os.path.basename(path) + ".json")
                    if os.path.exists(st_file):
                        try:
                            with open(st_file, 'r') as f:
                                st_json = json.load(f)
                                mappings = st_json.get('mappings')
                        except: pass
                
                # Fallback to standard app defaults if no mapping is found anywhere
                if not mappings:
                    # Standard software defaults based on typical PBOQ structure:
                    # Col 0:Ref, 1:Desc, 2:Qty, 3:Unit, 4:Bill Rate, 5:Bill Amount, 6:Gross Rate, 7:Rate Code
                    mappings = {
                        'ref': 0,
                        'desc': 1,
                        'qty': 2,
                        'unit': 3,
                        'bill_rate': 4,
                        'bill_amount': 5,
                        'rate': 6,
                        'rate_code': 7
                    }

                conn = sqlite3.connect(path)
                cursor = conn.cursor()
                
                # Fetch database columns to identify physical names (Column 0, Column 1, etc.)
                cursor.execute("PRAGMA table_info(pboq_items)")
                db_col_info = cursor.fetchall()
                db_cols = [info[1] for info in db_col_info]
                
                # Find physical column for Rate Code search
                code_db_col = None
                if mappings.get('rate_code', -1) >= 0:
                    db_idx = mappings['rate_code'] + 1
                    if db_idx < len(db_cols):
                        code_db_col = db_cols[db_idx]
                
                if not code_db_col and "RateCode" in db_cols:
                    code_db_col = "RateCode"
                
                if db_cols:
                    # Identify mappings for specific roles
                    m_rate = mappings.get('bill_rate', -1)
                    m_gross = mappings.get('rate', -1)
                    m_code = mappings.get('rate_code', -1)
                    m_amt = mappings.get('bill_amount', -1)
                    m_qty = mappings.get('qty', -1)

                    # Robust WHERE clause construction
                    search_col = code_db_col if code_db_col else "RateCode"
                    where_frag = f'TRIM(UPPER("{search_col}")) = ?'
                    
                    # Verify if specific column works; otherwise fallback to brute force
                    cursor.execute(f'SELECT COUNT(*) FROM pboq_items WHERE {where_frag}', (rate_code_clean,))
                    if cursor.fetchone()[0] == 0:
                        where_frag = " OR ".join([f'TRIM(UPPER("{c}")) = ?' for c in db_cols])
                        q_params = [rate_code_clean] * len(db_cols)
                    else:
                        q_params = [rate_code_clean]

                    # 1. Update all mapped rate-related columns in a single pass if possible
                    update_fields = []
                    upd_params = []
                    
                    # Physical mapped columns
                    for m_idx, val in [(m_rate, new_gross_str), (m_gross, new_gross_str), (m_code, rate_code)]:
                        if m_idx >= 0:
                            db_idx = m_idx + 1
                            if db_idx < len(db_cols):
                                update_fields.append(f'"{db_cols[db_idx]}" = ?')
                                upd_params.append(val)
                    
                    # Always update logical helper columns too
                    if "GrossRate" in db_cols:
                        update_fields.append("GrossRate = ?")
                        upd_params.append(new_gross_str)
                    if "RateCode" in db_cols:
                        update_fields.append("RateCode = ?")
                        upd_params.append(rate_code)

                    if update_fields:
                        cursor.execute(f'UPDATE pboq_items SET {", ".join(update_fields)} WHERE {where_frag}', upd_params + q_params)

                    # 2. Row-by-row recalculation of Bill Amount
                    if m_amt >= 0 and m_qty >= 0:
                        db_idx_amt, db_idx_qty = m_amt + 1, m_qty + 1
                        if db_idx_amt < len(db_cols) and db_idx_qty < len(db_cols):
                            a_col = db_cols[db_idx_amt]
                            q_col = db_cols[db_idx_qty]
                            cursor.execute(f'SELECT rowid, "{q_col}" FROM pboq_items WHERE {where_frag}', q_params)
                            rows_to_recalc = cursor.fetchall()
                            for rid, q_str in rows_to_recalc:
                                try:
                                    if q_str is None or str(q_str).strip() == "": continue
                                    qv = float(str(q_str).replace(',', ''))
                                    r_val_rounded = round(float(new_gross), 2)
                                    q_val_rounded = round(float(qv), 4)
                                    av = round(r_val_rounded * q_val_rounded, 2)
                                    cursor.execute(f'UPDATE pboq_items SET "{a_col}" = ? WHERE rowid = ?', ("{:,.2f}".format(av), rid))
                                except: pass
                
                conn.commit()
                conn.close()
            except Exception as e:
                print(f"Error syncing PBOQ {path}: {e}")
                pass

        # 3. Refresh Viewers
        if self.main_window:
            for sub in self.main_window.mdi_area.subWindowList():
                w = sub.widget()
                w_class = getattr(w, '__class__', None).__name__
                
                if w_class == 'SORDialog':
                    if hasattr(w, '_load_selected_sor'): w._load_selected_sor()
                
                if w_class == 'PBOQDialog':
                    # Check if it's the right project
                    if hasattr(w, 'project_dir') and os.path.abspath(w.project_dir) == os.path.abspath(project_dir):
                        # Reload the current DB to show changes and refresh collections
                        if hasattr(w, '_load_pboq_db'):
                            idx = w.pboq_file_selector.currentIndex()
                            w._load_pboq_db(idx)

    def refresh_view(self):
        self.is_loading = True
        
        # Ensure child widgets are using the latest estimate reference (critical for window reuse)
        if hasattr(self, 'header_widget'): self.header_widget.estimate = self.estimate
        if hasattr(self, 'tree_widget'): self.tree_widget.estimate = self.estimate
        if hasattr(self, 'composite_widget'): self.composite_widget.estimate = self.estimate
        if hasattr(self, 'summary_widget'): self.summary_widget.estimate = self.estimate

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

