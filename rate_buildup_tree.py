from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem, 
                             QHeaderView, QMenu, QMessageBox, QInputDialog)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont
import re
from selection_dialogs import CostSelectionDialog
from edit_item_dialog import EditItemDialog

class RateBuildupTreeWidget(QWidget):
    """Encapsulates the Tree View (Tasks & Resources) for the Rate Build-up."""
    
    # Signals to inform the parent dialog
    stateChanged = pyqtSignal()
    dataCommitted = pyqtSignal()
    
    def __init__(self, estimate_object, main_window, db_manager, parent=None):
        super().__init__(parent)
        self.estimate = estimate_object
        self.main_window = main_window
        self.db_manager = db_manager
        self._init_ui()
        self.expanded_imported_rates = set()
        
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Ref", "Tasks", "Calculations", "Cost", "Net Rate", "Adjusted Net Rate"])
        header_view = self.tree.header()
        header_view.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header_view.setStretchLastSection(True)
        self.tree.setIndentation(15)
        
        self.tree.itemDoubleClicked.connect(self.edit_item)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.show_context_menu)
        self.tree.itemChanged.connect(self.on_item_changed)
        
        layout.addWidget(self.tree)

    def show_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        menu = QMenu(self)
        
        if item and hasattr(item, 'item_type'):
            go_to_action = menu.addAction("Go to Resource")
            go_to_action.triggered.connect(lambda: self.go_to_resource(item))
            menu.addSeparator()

        add_task_action = menu.addAction("Add Task")
        add_task_action.triggered.connect(self.add_task)
        
        if item and not item.parent(): # If a Task is selected, show Edit Task
            edit_task_action = menu.addAction("Edit Task")
            edit_task_action.triggered.connect(lambda: self.edit_task(item))
            
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
        
        toggle_highlights_action = menu.addAction("Show/Hide Changes")
        toggle_highlights_action.triggered.connect(self.toggle_highlights)
        
        if item and hasattr(item, 'item_type') and hasattr(item, 'task_object') and item.task_object.description == "Imported Rates":
            details_action = menu.addAction("Show/Hide Details")
            details_action.triggered.connect(lambda checked=False, i=item: self.toggle_imported_rate_details(i))
            
            sync_action = menu.addAction("Sync with Database")
            sync_action.triggered.connect(lambda checked=False, i=item: self.sync_imported_rate_from_db(i))
        
        remove_action = menu.addAction("Remove Selected")
        remove_action.triggered.connect(self.remove_selected)
        
        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def add_task(self):
        desc, ok = QInputDialog.getText(self, "Add Task", "Task Description:")
        if ok and desc:
            from models import Task
            self.estimate.add_task(Task(desc))
            self.stateChanged.emit()

    def add_resource(self, table_name):
        dialog = CostSelectionDialog(table_name, self)
        if dialog.exec() and dialog.selected_item:
            item_data = dialog.selected_item
            
            # Use appropriate task or 'Imported Rates' task
            if table_name == 'indirect_costs':
                target_task = None
                for task in self.estimate.tasks:
                    if task.description == "Imported Rates":
                        target_task = task
                        break
                if not target_task:
                    from models import Task
                    target_task = Task("Imported Rates")
                    self.estimate.add_task(target_task)
            else:
                selected_item = self.tree.currentItem()
                if selected_item and not selected_item.parent():
                    # It's a task
                    task_idx = self.tree.indexOfTopLevelItem(selected_item)
                    if task_idx >= 0:
                        target_task = self.estimate.tasks[task_idx]
                elif selected_item and selected_item.parent():
                    parent = selected_item.parent()
                    task_idx = self.tree.indexOfTopLevelItem(parent)
                    if task_idx >= 0:
                        target_task = self.estimate.tasks[task_idx]
                else:
                    if self.estimate.tasks:
                        target_task = self.estimate.tasks[0]
                    else:
                        from models import Task
                        target_task = Task("Main Task")
                        self.estimate.add_task(target_task)

            # Map the fields
            new_item = {}
            if table_name == "materials":
                new_item = {
                    'name': item_data['name'], 'unit': item_data.get('unit', ''), 'currency': item_data.get('currency', '$'),
                    'unit_cost': item_data['price'], 'qty': 1.0, 'total': item_data['price']
                }
                target_task.materials.append(new_item)
            elif table_name == "labor":
                new_item = {
                    'trade': item_data['trade'], 'unit': item_data.get('unit', ''), 'currency': item_data.get('currency', '$'),
                    'rate': item_data['rate'], 'hours': 1.0, 'total': item_data['rate']
                }
                target_task.labor.append(new_item)
            elif table_name == "equipment":
                new_item = {
                    'name': item_data['name'], 'unit': item_data.get('unit', ''), 'currency': item_data.get('currency', '$'),
                    'rate': item_data['rate'], 'hours': 1.0, 'total': item_data['rate']
                }
                target_task.equipment.append(new_item)
            elif table_name == "plant":
                new_item = {
                    'name': item_data['name'], 'unit': item_data.get('unit', ''), 'currency': item_data.get('currency', '$'),
                    'rate': item_data['rate'], 'hours': 1.0, 'total': item_data['rate']
                }
                target_task.plant.append(new_item)
            elif table_name == "indirect_costs":
                new_item = {
                    'description': item_data.get('name', 'Indirect Cost'), 'amount': item_data['price'],
                    'qty': 1.0, 'total': item_data['price']
                }
                target_task.indirect_costs.append(new_item)

            self.stateChanged.emit()

    def remove_selected(self):
        item = self.tree.currentItem()
        if not item: return

        if not item.parent(): # It's a Task
            reply = QMessageBox.question(self, 'Remove Task',
                                         "Are you sure you want to remove this task and all its items?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                idx = self.tree.indexOfTopLevelItem(item)
                if idx >= 0:
                    del self.estimate.tasks[idx]
                    self.stateChanged.emit()
            return
            
        # It's a resource (child)
        if hasattr(item, 'item_type') and hasattr(item, 'task_object'):
            reply = QMessageBox.question(self, 'Remove Item',
                                         "Are you sure you want to remove this item?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                if item.item_type == 'material':
                    item.task_object.materials.remove(item.item_data)
                elif item.item_type == 'labor':
                    item.task_object.labor.remove(item.item_data)
                elif item.item_type == 'equipment':
                    item.task_object.equipment.remove(item.item_data)
                elif item.item_type == 'plant':
                    item.task_object.plant.remove(item.item_data)
                elif item.item_type == 'indirect_costs':
                    item.task_object.indirect_costs.remove(item.item_data)
                    
                self.stateChanged.emit()

    def edit_task(self, item):
        self.tree.editItem(item, 1)

    def on_item_changed(self, item, column):
        if not item.parent() and column == 1: # Task desc edit
            idx = self.tree.indexOfTopLevelItem(item)
            if idx >= 0:
                new_desc = item.text(1)
                task = self.estimate.tasks[idx]
                if task.description != new_desc:
                    task.description = new_desc
                    self.stateChanged.emit()

    def go_to_resource(self, item):
        if not hasattr(item, 'item_type') or not hasattr(item, 'item_data'):
            return
            
        type_code = item.item_type
        
        # If the resource is an imported rate (composite sub-rate), open the rate database
        if hasattr(item, 'task_object') and getattr(item.task_object, 'description', '') == "Imported Rates":
            name = item.item_data.get('name', '')
            rate_code = name.split(':')[0].strip() if ':' in name else name.split()[0] if name else ""
            if rate_code and self.main_window and hasattr(self.main_window, 'show_rate_in_database'):
                self.main_window.show_rate_in_database(rate_code)
            return
            
        if type_code == 'material':
            table = 'materials'
            name = item.item_data.get('name')
        elif type_code == 'labor':
            table = 'labor'
            name = item.item_data.get('trade')
        elif type_code == 'equipment':
            table = 'equipment'
            name = item.item_data.get('name')
        elif type_code == 'plant':
            table = 'plant'
            name = item.item_data.get('name')
        elif type_code == 'indirect_costs':
            table = 'indirect_costs'
            name = item.item_data.get('description', '')
        else:
            return

        if self.main_window and table and name:
            if hasattr(self.main_window, 'show_resource_in_database'):
                self.main_window.show_resource_in_database(table, name)

    def edit_item(self, item, column):
        if hasattr(item, 'item_type') and hasattr(item, 'item_data'):
            custom_title = None
            custom_name_label = None
            if hasattr(item, 'task_object') and item.task_object.description == "Imported Rates":
                custom_title = "Edit Rate"
                custom_name_label = "Description:"
                
            if self.main_window and hasattr(self.main_window, 'open_edit_item_window'):
                self.main_window.open_edit_item_window(
                    item.item_data, item.item_type, self.estimate.currency, self, 
                    custom_title=custom_title, custom_name_label=custom_name_label
                )
            else:
                 dialog = EditItemDialog(item.item_data, item.item_type, self.estimate.currency, self, custom_name_label=custom_name_label)
                 if custom_title:
                     dialog.setWindowTitle(custom_title)
                 if dialog.exec():
                     self.stateChanged.emit()

    def toggle_imported_rate_details(self, item):
        if hasattr(item, 'item_data'):
            name = item.item_data.get('name')
            if name:
                if name in self.expanded_imported_rates:
                    self.expanded_imported_rates.remove(name)
                else:
                    self.expanded_imported_rates.add(name)
                # Soft refresh
                self.refresh_ui()

    def sync_imported_rate_from_db(self, item):
        if not hasattr(item, 'item_data'): return
        name = item.item_data.get('name')
        if not name: return
        
        sub_obj = None
        sub_idx = -1
        for i, s in enumerate(getattr(self.estimate, 'sub_rates', [])):
            if name == f"{getattr(s, 'rate_code', '')}: {getattr(s, 'project_name', '')}":
                sub_obj = s
                sub_idx = i
                break
                
        if not sub_obj:
            QMessageBox.warning(self, "Error", f"Could not locate '{name}' in sub-rates.")
            return
            
        self.sync_sub_rate(sub_idx)

    def sync_sub_rate(self, sub_idx):
        sub_obj = self.estimate.sub_rates[sub_idx]
        name = f"{getattr(sub_obj, 'rate_code', '')}: {getattr(sub_obj, 'project_name', '')}"
        
        db_id = getattr(sub_obj, 'id', None)
        from database import DatabaseManager
        rates_db = DatabaseManager("construction_rates.db")
        
        if not db_id:
            for r in rates_db.get_rates_data():
                if r['rate_code'] == getattr(sub_obj, 'rate_code', ''):
                    db_id = r['id']
                    break
        
        if not db_id:
            QMessageBox.warning(self, "Error", f"No database record exists for '{name}'.")
            return
            
        new_sub = rates_db.load_estimate_details(db_id)
        if not new_sub:
            QMessageBox.warning(self, "Error", f"Failed to load updated data for '{name}'.")
            return
            
        new_sub.converted_unit = getattr(sub_obj, 'converted_unit', getattr(sub_obj, 'unit', ''))
        new_sub.quantity = getattr(sub_obj, 'quantity', 1.0)
        
        self.estimate.sub_rates[sub_idx] = new_sub
        
        # Trigger parent update
        self.stateChanged.emit()
        
        QMessageBox.information(
            self, 
            "Sync Successful", 
            f"'{name}' has been synced with the latest changes from the database.\n\n"
            "Please check for any unit mismatches and calculation changes."
        )

    def toggle_highlights(self):
        self.show_impact_highlights = not getattr(self, 'show_impact_highlights', False)
        self.refresh_ui()

    def set_impact_highlights(self, show_highlights, impacted_resources):
        self.show_impact_highlights = show_highlights
        self.impacted_resources = impacted_resources
        self.refresh_ui()

    def refresh_ui(self):
        self.tree.clear()
        
        match = re.search(r'\((.*?)\)', self.estimate.currency)
        base_sym = match.group(1) if match else "$"
        
        adj_factor = getattr(self.estimate, 'adjustment_factor', 1.0)
        is_adjusted = (adj_factor != 1.0)
        
        bold_font = self.tree.font()
        bold_font.setBold(True)

        # Get text colors from settings using the default (costs) database
        from database import DatabaseManager
        settings_db = DatabaseManager()
        type_colors = {
            'material': QColor(settings_db.get_setting("color_materials") or "#000000"),
            'labor': QColor(settings_db.get_setting("color_labour") or "#000000"),
            'equipment': QColor(settings_db.get_setting("color_equipment") or "#000000"),
            'plant': QColor(settings_db.get_setting("color_plant") or "#000000"),
            'indirect_costs': QColor(settings_db.get_setting("color_indirect_costs") or "#000000"),
            'rates': QColor(settings_db.get_setting("color_rates") or "#000000")
        }

        def get_color_for_type(type_name):
            if type_name in type_colors and settings_db.get_setting(f"color_{type_name.replace('labor', 'labour').replace('material', 'materials')}"):
                return type_colors[type_name].name()
            return None

        resources = [
            ('materials', 'Material', 'name', lambda x: x.get('unit') or '', 'qty', 'unit_cost', 'material'),
            ('labor', 'Labor', 'trade', lambda x: x.get('unit') or 'hrs', 'hours', 'rate', 'labor'),
            ('equipment', 'Equipment', 'name', lambda x: x.get('unit') or 'hrs', 'hours', 'rate', 'equipment'),
            ('plant', 'Plant', 'name', lambda x: x.get('unit') or 'hrs', 'hours', 'rate', 'plant'),
            ('indirect_costs', 'Indirect', 'description', lambda x: x.get('unit') or '', 'qty', 'amount', 'indirect_costs')
        ]

        def _render_sub_rate_recursive(parent_item, sub_estimate):
            sub_match = re.search(r'\((.*?)\)', sub_estimate.currency)
            sub_sym = sub_match.group(1) if sub_match else "$"
            
            for s_tidx, s_task in enumerate(getattr(sub_estimate, 'tasks', []), 1):
                s_task_total = sum([
                    sum(sub_estimate._get_item_total_in_base_currency(m) for m in getattr(s_task, 'materials', [])),
                    sum(sub_estimate._get_item_total_in_base_currency(l) for l in getattr(s_task, 'labor', [])),
                    sum(sub_estimate._get_item_total_in_base_currency(e) for e in getattr(s_task, 'equipment', [])),
                    sum(sub_estimate._get_item_total_in_base_currency(p) for p in getattr(s_task, 'plant', [])),
                    sum(sub_estimate._get_item_total_in_base_currency(ind) for ind in getattr(s_task, 'indirect_costs', []))
                ])
                
                s_task_item = QTreeWidgetItem(parent_item, [
                    "",
                    f"Task {s_tidx}: {s_task.description}",
                    "",
                    "",
                    f"{sub_sym}{s_task_total:,.2f}",
                    ""
                ])
                
                s_task_bg = QColor("#e3f2fd") 
                b_font = QFont()
                b_font.setBold(True)
                for c_idx in range(self.tree.columnCount()):
                    s_task_item.setBackground(c_idx, s_task_bg)
                    s_task_item.setFont(c_idx, b_font)
                    s_task_item.setFlags(s_task_item.flags() & ~Qt.ItemFlag.ItemIsEditable)

                for s_list_attr, s_label_prefix, s_name_key, s_unit_func, s_qty_key, s_rate_key, s_type_code in resources:
                    s_items = getattr(s_task, s_list_attr, [])
                    for s_item in s_items:
                        s_uc_conv = sub_estimate.convert_to_base_currency(s_item.get(s_rate_key, 0), s_item.get('currency', '$'))
                        s_total_conv = sub_estimate.convert_to_base_currency(s_item.get('total', 0), s_item.get('currency', '$'))
                        s_unit_str = s_unit_func(s_item)
                        s_qty_val = s_item.get(s_qty_key, 1.0)
                        
                        item_display_name = s_item.get(s_name_key, 'Unknown')
                        item_label = f"  {s_label_prefix}: {item_display_name}"
                        if s_task.description == "Imported Rates":
                            item_label = f"  {item_display_name}"
                        
                        s_child = QTreeWidgetItem(s_task_item, [
                            "",
                            item_label,
                            f"{s_qty_val:.2f} {s_unit_str} @ {sub_sym}{s_uc_conv:,.2f}",
                            f"{sub_sym}{s_total_conv:,.2f}",
                            "",
                            ""
                        ])
                        
                        s_child.item_type = s_type_code
                        s_child.item_data = s_item
                        s_child.task_object = s_task
                        
                        s_child_bg = QColor("#f4f9fb")
                        for c_idx in range(self.tree.columnCount()):
                            s_child.setBackground(c_idx, s_child_bg)
                            s_child.setFlags(s_child.flags() & ~Qt.ItemFlag.ItemIsEditable)
                            
                        item_type_for_color = 'rates' if s_task.description == "Imported Rates" else s_type_code
                        color_hex = get_color_for_type(item_type_for_color)
                        if color_hex:
                            from PyQt6.QtWidgets import QLabel
                            s_child.setForeground(1, QColor(0, 0, 0, 0)) # Hide default text
                            if s_task.description != "Imported Rates":
                                lbl = QLabel(f'&nbsp;&nbsp;<span style="color: {color_hex}; font-weight: bold;">{s_label_prefix}:</span> {item_display_name}')
                            else:
                                parts = item_display_name.split(':', 1)
                                if len(parts) > 1:
                                    lbl = QLabel(f'&nbsp;&nbsp;<span style="color: {color_hex}; font-weight: bold;">{parts[0]}:</span>{parts[1]}')
                                else:
                                    lbl = QLabel(f'&nbsp;&nbsp;<span style="color: {color_hex}; font-weight: bold;">{item_display_name}</span>')
                            lbl.setStyleSheet("background: transparent;")
                            self.tree.setItemWidget(s_child, 1, lbl)
                            
                        if getattr(self, 'show_impact_highlights', False) and (s_type_code, item_display_name) in getattr(self, 'impacted_resources', set()):
                            for c in range(self.tree.columnCount()):
                                s_child.setBackground(c, QColor("#fce4ec"))
                                s_child.setForeground(c, Qt.GlobalColor.black)

                        if s_task.description == "Imported Rates" and item_display_name in self.expanded_imported_rates:
                            nested_sub = None
                            for n_s in getattr(sub_estimate, 'sub_rates', []):
                                n_s_name = f"{getattr(n_s, 'rate_code', '')}: {getattr(n_s, 'project_name', '')}"
                                if item_display_name == n_s_name:
                                    nested_sub = n_s
                                    break
                                    
                            if nested_sub:
                                _render_sub_rate_recursive(s_child, nested_sub)
                                s_child.setExpanded(True)

            parent_item.setExpanded(True)

        for i, task in enumerate(self.estimate.tasks, 1):
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
            task_item.setFlags(task_item.flags() | Qt.ItemFlag.ItemIsEditable)
            
            for col in range(self.tree.columnCount()):
                task_item.setFont(col, bold_font)
            
            sub_idx = 1
            for list_attr, label_prefix, name_key, unit_func, qty_key, rate_key, type_code in resources:
                items = getattr(task, list_attr)
                for item in items:
                    uc_conv = self.estimate.convert_to_base_currency(item.get(rate_key, 0), item.get('currency', '$'))
                    total_conv = self.estimate.convert_to_base_currency(item.get('total', 0), item.get('currency', '$'))
                    
                    unit_str = unit_func(item)
                    qty_val = item.get(qty_key, 1.0)
                    
                    item_display_name = item.get(name_key, 'Unknown')
                    item_label = f"  {label_prefix}: {item_display_name}"
                    
                    if task.description == "Imported Rates":
                        item_label = f"  {item_display_name}"
                    
                    child = QTreeWidgetItem(task_item, [
                        f"{i}.{sub_idx}", 
                        item_label, 
                        f"{qty_val:.2f} {unit_str} @ {base_sym}{uc_conv:,.2f}",
                        f"{base_sym}{total_conv:,.2f}",
                        "",
                        ""
                    ])
                    
                    child.item_type = type_code
                    child.item_data = item
                    child.task_object = task
                    
                    for c in range(self.tree.columnCount()):
                        child.setFlags(child.flags() & ~Qt.ItemFlag.ItemIsEditable)
                        
                    item_type_for_color = 'rates' if task.description == "Imported Rates" else type_code
                    color_hex = get_color_for_type(item_type_for_color)
                    if color_hex:
                        from PyQt6.QtWidgets import QLabel
                        child.setForeground(1, QColor(0, 0, 0, 0)) # Hide default text
                        if task.description != "Imported Rates":
                            lbl = QLabel(f'&nbsp;&nbsp;<span style="color: {color_hex}; font-weight: bold;">{label_prefix}:</span> {item_display_name}')
                        else:
                            parts = item_display_name.split(':', 1)
                            if len(parts) > 1:
                                lbl = QLabel(f'&nbsp;&nbsp;<span style="color: {color_hex}; font-weight: bold;">{parts[0]}:</span>{parts[1]}')
                            else:
                                lbl = QLabel(f'&nbsp;&nbsp;<span style="color: {color_hex}; font-weight: bold;">{item_display_name}</span>')
                        lbl.setStyleSheet("background: transparent;")
                        self.tree.setItemWidget(child, 1, lbl)
                        
                    if getattr(self, 'show_impact_highlights', False) and (type_code, item_display_name) in getattr(self, 'impacted_resources', set()):
                        for c in range(self.tree.columnCount()):
                            child.setBackground(c, QColor("#fce4ec"))
                            child.setForeground(c, Qt.GlobalColor.black)

                    if task.description == "Imported Rates" and item_display_name in self.expanded_imported_rates:
                        sub = None
                        for s in getattr(self.estimate, 'sub_rates', []):
                            s_name = f"{getattr(s, 'rate_code', '')}: {getattr(s, 'project_name', '')}"
                            if item_display_name == s_name:
                                sub = s
                                break
                                
                        if sub:
                            _render_sub_rate_recursive(child, sub)

                    sub_idx += 1

        self.tree.expandAll()
        for c_i in range(self.tree.columnCount()):
            self.tree.resizeColumnToContents(c_i)
        
        self.tree.header().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.tree.header().setStretchLastSection(True)
