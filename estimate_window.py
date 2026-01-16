# estimate_window.py

from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                             QTreeWidget, QTreeWidgetItem, QLabel, QFormLayout, QMessageBox,
                             QInputDialog, QDialog, QTableWidget, QTableWidgetItem, QHeaderView,
                             QDoubleSpinBox, QTextEdit, QFileDialog, QDialogButtonBox, QLineEdit,
                             QSplitter, QFrame)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt
from database import DatabaseManager, Estimate, Task


class EstimateWindow(QMainWindow):
    def __init__(self, estimate_data=None, estimate_object=None, parent=None):
        super().__init__(parent)
        self.db_manager = DatabaseManager()

        if estimate_object:
            self.estimate = estimate_object
        elif estimate_data:
            self.estimate = Estimate(
                project_name=estimate_data['name'],
                client_name=estimate_data['client'],
                overhead=estimate_data['overhead'],
                profit=estimate_data['profit']
            )
        else:  # Fallback
            self.estimate = Estimate("Error", "Error", 0, 0)

        self.setWindowTitle(f"Estimate: {self.estimate.project_name}")
        self.setMinimumSize(1000, 700) # Increased default minimum

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)

        # Use QSplitter for responsiveness
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left side - Tree view and action buttons
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Item", "Details", "Cost"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        left_layout.addWidget(self.tree)

        btn_layout = QHBoxLayout()
        add_task_btn = QPushButton("Add Task")
        add_material_btn = QPushButton("Add Material")
        add_labor_btn = QPushButton("Add Labor")
        add_equipment_btn = QPushButton("Add Equipment")
        remove_btn = QPushButton("Remove Selected")
        
        # Give buttons a bit more style and minimum width
        for btn in [add_task_btn, add_material_btn, add_labor_btn, add_equipment_btn, remove_btn]:
            btn.setMinimumHeight(40)
            btn_layout.addWidget(btn)
        
        remove_btn.setStyleSheet("background-color: #d32f2f;") # Red for remove
        remove_btn.setStyleSheet(remove_btn.styleSheet() + " QPushButton:hover { background-color: #ef5350; }")

        left_layout.addLayout(btn_layout)
        self.splitter.addWidget(left_widget)

        # Right side - Summary and main actions
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(10, 0, 0, 0)

        summary_group = QFrame()
        summary_group.setFrameShape(QFrame.Shape.StyledPanel)
        summary_group.setStyleSheet("QFrame { background-color: #ffffff; border: 1px solid #dcdfe6; border-radius: 8px; } QLabel { border: none; }")
        
        summary_layout = QFormLayout(summary_group)
        summary_layout.setContentsMargins(20, 20, 20, 20)
        summary_layout.setSpacing(15)

        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(16)

        summary_title = QLabel("Project Summary")
        summary_title.setFont(title_font)
        summary_title.setStyleSheet("color: #2e7d32; margin-bottom: 10px;")
        summary_layout.addRow(summary_title)

        value_font = QFont()
        value_font.setPointSize(12)

        self.subtotal_label = QLabel("$0.00")
        self.overhead_label = QLabel("$0.00")
        self.profit_label = QLabel("$0.00")
        self.grand_total_label = QLabel("$0.00")
        
        for lbl in [self.subtotal_label, self.overhead_label, self.profit_label, self.grand_total_label]:
            lbl.setFont(value_font)
            lbl.setAlignment(Qt.AlignmentFlag.AlignRight)

        grand_font = QFont()
        grand_font.setBold(True)
        grand_font.setPointSize(18)
        self.grand_total_label.setFont(grand_font)
        self.grand_total_label.setStyleSheet("color: #2e7d32;")

        summary_layout.addRow("Subtotal:", self.subtotal_label)
        summary_layout.addRow(f"Overhead ({self.estimate.overhead_percent}%):", self.overhead_label)
        summary_layout.addRow(f"Profit ({self.estimate.profit_margin_percent}%):", self.profit_label)
        
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setStyleSheet("background-color: #dcdfe6; max-height: 1px;")
        summary_layout.addRow(line)
        
        grand_total_desc = QLabel("GRAND TOTAL:")
        grand_total_desc.setFont(grand_font)
        summary_layout.addRow(grand_total_desc, self.grand_total_label)
        
        right_layout.addWidget(summary_group)

        action_layout = QVBoxLayout() # Changed to vertical for better fitting
        action_layout.setSpacing(10)
        action_layout.setContentsMargins(0, 20, 0, 0)
        
        save_estimate_btn = QPushButton("Save Estimate")
        generate_report_btn = QPushButton("Generate Report")
        save_estimate_btn.setMinimumHeight(45)
        generate_report_btn.setMinimumHeight(45)
        
        action_layout.addWidget(save_estimate_btn)
        action_layout.addWidget(generate_report_btn)
        right_layout.addLayout(action_layout)
        right_layout.addStretch()

        self.splitter.addWidget(right_widget)
        self.splitter.setStretchFactor(0, 3) # Left side gets more space
        self.splitter.setStretchFactor(1, 1)
        
        self.main_layout.addWidget(self.splitter)

        # Connect signals
        add_task_btn.clicked.connect(self.add_task)
        add_material_btn.clicked.connect(self.add_material)
        add_labor_btn.clicked.connect(self.add_labor)
        add_equipment_btn.clicked.connect(self.add_equipment)
        remove_btn.clicked.connect(self.remove_item)
        save_estimate_btn.clicked.connect(self.save_estimate)
        generate_report_btn.clicked.connect(self.generate_report)

        self.refresh_view()

    def _get_selected_task_object(self):
        """Helper to find the parent task object from any selection in the tree."""
        selected = self.tree.currentItem()
        if not selected:
            QMessageBox.warning(self, "Selection Error", "Please select an item in a task.")
            return None

        task_item = selected if not selected.parent() else selected.parent()

        if not hasattr(task_item, 'task_object'):
            QMessageBox.warning(self, "Selection Error", "Invalid item selected. Please select a task.")
            return None

        return task_item.task_object

    def save_estimate(self):
        reply = QMessageBox.question(self, "Confirm Save",
                                     "Do you want to save this estimate to the database?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            if self.db_manager.save_estimate(self.estimate):
                QMessageBox.information(self, "Success", "Estimate has been saved successfully.")
            else:
                QMessageBox.critical(self, "Error", "Failed to save the estimate.")

    def add_task(self):
        text, ok = QInputDialog.getText(self, "Add Task", "Enter task description:")
        if ok and text:
            self.estimate.add_task(Task(text))
            self.refresh_view()

    def add_material(self):
        task_obj = self._get_selected_task_object()
        if not task_obj: return

        dialog = SelectItemDialog("materials", self)
        if dialog.exec():
            item, quantity = dialog.get_selection()
            if item and quantity > 0:
                task_obj.add_material(item['name'], quantity, item['unit'], item['price'])
                self.refresh_view()

    def add_labor(self):
        task_obj = self._get_selected_task_object()
        if not task_obj: return

        dialog = SelectItemDialog("labor", self)
        if dialog.exec():
            item, hours = dialog.get_selection()
            if item and hours > 0:
                task_obj.add_labor(item['trade'], hours, item['rate_per_hour'])
                self.refresh_view()

    def add_equipment(self):
        task_obj = self._get_selected_task_object()
        if not task_obj: return

        dialog = SelectItemDialog("equipment", self)
        if dialog.exec():
            item, hours = dialog.get_selection()
            if item and hours > 0:
                task_obj.add_equipment(item['name'], hours, item['rate_per_hour'])
                self.refresh_view()

    def remove_item(self):
        selected = self.tree.currentItem()
        if not selected: return

        if hasattr(selected, 'item_type'):  # It's a material, labor, or equipment item
            parent_item = selected.parent()
            task_obj = parent_item.task_object
            item_data = selected.item_data

            if selected.item_type == 'material':
                task_obj.materials.remove(item_data)
            elif selected.item_type == 'labor':
                task_obj.labor.remove(item_data)
            elif selected.item_type == 'equipment':
                task_obj.equipment.remove(item_data)

        elif hasattr(selected, 'task_object'):  # It's a top-level task item
            task_obj = selected.task_object
            self.estimate.tasks.remove(task_obj)

        self.refresh_view()

    def refresh_view(self):
        self.tree.clear()
        for task in self.estimate.tasks:
            task_item = QTreeWidgetItem(self.tree, [task.description, "", f"${task.get_subtotal():.2f}"])
            task_item.task_object = task  # Attach the main task object

            for mat in task.materials:
                child = QTreeWidgetItem(task_item, [f"Material: {mat['name']}",
                                                    f"{mat['qty']} {mat['unit']} @ ${mat['unit_cost']:.2f}",
                                                    f"${mat['total']:.2f}"])
                child.item_data = mat
                child.item_type = 'material'

            for lab in task.labor:
                child = QTreeWidgetItem(task_item,
                                        [f"Labor: {lab['trade']}", f"{lab['hours']} hrs @ ${lab['rate']:.2f}/hr",
                                         f"${lab['total']:.2f}"])
                child.item_data = lab
                child.item_type = 'labor'

            for equip in task.equipment:
                child = QTreeWidgetItem(task_item, [f"Equipment: {equip['name']}",
                                                    f"{equip['hours']} hrs @ ${equip['rate']:.2f}/hr",
                                                    f"${equip['total']:.2f}"])
                child.item_data = equip
                child.item_type = 'equipment'

        self.tree.expandAll()
        self.update_summary()

    def update_summary(self):
        totals = self.estimate.calculate_totals()
        self.subtotal_label.setText(f"${totals['subtotal']:.2f}")
        self.overhead_label.setText(f"${totals['overhead']:.2f}")
        self.profit_label.setText(f"${totals['profit']:.2f}")
        self.grand_total_label.setText(f"${totals['grand_total']:.2f}")

    def generate_report(self):
        report_dialog = ReportDialog(self.estimate, self)
        report_dialog.exec()


# --- START OF CHANGE: Updated SelectItemDialog with Search ---
class SelectItemDialog(QDialog):
    def __init__(self, item_type, parent=None):
        super().__init__(parent)
        self.item_type = item_type
        singular_name = item_type[:-1] if item_type.endswith('s') else item_type
        self.setWindowTitle(f"Select {singular_name.capitalize()}")
        self.db_manager = DatabaseManager()

        self.all_items = self.db_manager.get_items(item_type)
        self.current_items = []

        layout = QVBoxLayout(self)

        # Add search bar
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search:"))
        search_input = QLineEdit()
        search_input.setPlaceholderText("Type to filter...")
        search_layout.addWidget(search_input)
        layout.addLayout(search_layout)

        # Setup table
        self.table = QTableWidget()
        if item_type == "materials":
            headers = ["Name", "Unit/Price"]
        elif item_type == "labor":
            headers = ["Trade", "Rate"]
        else:
            headers = ["Name", "Rate"]  # For equipment

        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

        # Setup spinbox and buttons
        form_layout = QFormLayout()
        label_text = "Quantity:" if item_type == "materials" else "Hours:"
        self.spinbox = QDoubleSpinBox()
        self.spinbox.setRange(0.01, 1000000)
        self.spinbox.setValue(1.0)
        form_layout.addRow(label_text, self.spinbox)
        layout.addLayout(form_layout)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        # Connect search signal and populate table initially
        search_input.textChanged.connect(self.filter_items)
        self.filter_items("")  # Populate with all items

    def filter_items(self, text):
        """Filters and repopulates the table based on the search text."""
        self.table.setRowCount(0)
        self.current_items.clear()
        search_text = text.lower()

        for item in self.all_items:
            item_name = item[1].lower()  # Column 1 is always name/trade in the DB record
            if search_text in item_name:
                self.current_items.append(item)

        self.table.setRowCount(len(self.current_items))
        for row, item_data in enumerate(self.current_items):
            self.table.setItem(row, 0, QTableWidgetItem(item_data[1]))
            self.table.setItem(row, 1, QTableWidgetItem(str(item_data[2])))

    def get_selection(self):
        selected_row = self.table.currentRow()
        if selected_row < 0:
            return None, 0
        # Use the filtered list to get the correct item
        selected_item = self.current_items[selected_row]
        return selected_item, self.spinbox.value()


# --- END OF CHANGE ---


class ReportDialog(QDialog):
    def __init__(self, estimate, parent=None):
        super().__init__(parent)
        self.estimate = estimate
        self.setWindowTitle("Final Estimate Report")
        self.setMinimumSize(800, 600)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        self.report_text = QTextEdit()
        self.report_text.setReadOnly(True)
        # Use a more modern monospace font
        self.report_text.setFont(QFont("Consolas", 11) if sys.platform == "win32" else QFont("Monospace", 11))
        self.report_text.setStyleSheet("border: 1px solid #dcdfe6; border-radius: 4px; background-color: white; padding: 10px;")
        layout.addWidget(self.report_text)

        button_layout = QHBoxLayout()
        button_layout.addStretch(1)
        
        save_btn = QPushButton("Save to File")
        save_btn.setMinimumHeight(40)
        save_btn.clicked.connect(self.save_report)
        
        close_btn = QPushButton("Close")
        close_btn.setMinimumHeight(40)
        close_btn.setStyleSheet("background-color: #909399;")
        close_btn.clicked.connect(self.accept)
        
        button_layout.addWidget(save_btn)
        button_layout.addWidget(close_btn)
        layout.addLayout(button_layout)
        
        self.generate_report_text()

    def generate_report_text(self):
        totals = self.estimate.calculate_totals()
        report = []
        sep_long = "=" * 80
        sep_short = "-" * 80

        report.append(sep_long)
        report.append("CONSTRUCTION ESTIMATE".center(80))
        report.append(sep_short)
        report.append(f"{'Project:':<10} {self.estimate.project_name}")
        report.append(f"{'Client:':<10} {self.estimate.client_name}")
        report.append(sep_long)

        for i, task in enumerate(self.estimate.tasks, 1):
            report.append(f"\nTASK {i}: {task.description.upper()}")
            if task.materials:
                report.append("  Materials:")
                for m in task.materials:
                    report.append(
                        f"    - {m['name']:<30} {m['qty']:>8.2f} {m['unit']:<10} @ ${m['unit_cost']:>8.2f} = ${m['total']:>10.2f}")
            if task.labor:
                report.append("  Labor:")
                for l in task.labor:
                    report.append(
                        f"    - {l['trade']:<30} {l['hours']:>8.2f} {'hrs':<10} @ ${l['rate']:>8.2f} = ${l['total']:>10.2f}")
            if task.equipment:
                report.append("  Equipment:")
                for e in task.equipment:
                    report.append(
                        f"    - {e['name']:<30} {e['hours']:>8.2f} {'hrs':<10} @ ${e['rate']:>8.2f} = ${e['total']:>10.2f}")

            report.append(f"{'':<65}----------")
            report.append(f"{'Task Subtotal:':>65} ${task.get_subtotal():>10.2f}")

        report.append("\n" + sep_long)
        report.append("SUMMARY".center(80))
        report.append(sep_short)
        report.append(f"{'Total Direct Costs (Subtotal)':<65} ${totals['subtotal']:.2f}")
        report.append(f"Overhead ({self.estimate.overhead_percent}%):{'.' * 45} ${totals['overhead']:>10.2f}")
        report.append(f"{'Total Cost':<65} ${totals['subtotal'] + totals['overhead']:.2f}")
        report.append(f"Profit Margin ({self.estimate.profit_margin_percent}%):{'.' * 42} ${totals['profit']:>10.2f}")
        report.append(sep_short)
        report.append(f"{'GRAND TOTAL':<65} ${totals['grand_total']:>10.2f}")
        report.append(sep_long)

        self.report_text.setText("\n".join(report))

    def save_report(self):
        filename, _ = QFileDialog.getSaveFileName(self, "Save Report", f"{self.estimate.project_name}_estimate.txt",
                                                  "Text Files (*.txt)")
        if filename:
            with open(filename, 'w') as f:
                f.write(self.report_text.toPlainText())
            QMessageBox.information(self, "Success", f"Report saved to {filename}")