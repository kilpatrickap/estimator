# estimate_window.py

from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                             QTreeWidget, QTreeWidgetItem, QLabel, QFormLayout, QMessageBox,
                             QInputDialog, QDialog, QTableWidget, QTableWidgetItem, QHeaderView,
                             QDoubleSpinBox, QTextEdit, QFileDialog, QDialogButtonBox)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt
from database import DatabaseManager, Estimate, Task


class EstimateWindow(QMainWindow):
    def __init__(self, estimate_data, parent=None):
        super().__init__(parent)
        self.db_manager = DatabaseManager()
        self.estimate = Estimate(
            project_name=estimate_data['name'],
            client_name=estimate_data['client'],
            overhead=estimate_data['overhead'],
            profit=estimate_data['profit']
        )
        self.setWindowTitle(f"Estimate: {self.estimate.project_name}")
        self.setMinimumSize(800, 600)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QHBoxLayout(self.central_widget)

        # Left side: Tree view and buttons
        left_layout = QVBoxLayout()
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Item", "Details", "Cost"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        left_layout.addWidget(self.tree)

        btn_layout = QHBoxLayout()
        add_task_btn = QPushButton("Add Task")
        add_material_btn = QPushButton("Add Material")
        add_labor_btn = QPushButton("Add Labor")
        remove_btn = QPushButton("Remove Selected")
        btn_layout.addWidget(add_task_btn)
        btn_layout.addWidget(add_material_btn)
        btn_layout.addWidget(add_labor_btn)
        btn_layout.addWidget(remove_btn)
        left_layout.addLayout(btn_layout)

        # Right side: Summary and report
        right_layout = QVBoxLayout()
        summary_group = QWidget()
        summary_group.setStyleSheet("QWidget { background-color: #f0f0f0; border-radius: 5px; }")
        summary_layout = QFormLayout(summary_group)
        summary_layout.setContentsMargins(20, 20, 20, 20)

        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(14)

        summary_title = QLabel("Project Summary")
        summary_title.setFont(title_font)
        summary_layout.addRow(summary_title)

        self.subtotal_label = QLabel("$0.00")
        self.overhead_label = QLabel("$0.00")
        self.profit_label = QLabel("$0.00")
        self.grand_total_label = QLabel("$0.00")

        bold_font = QFont()
        bold_font.setBold(True)
        self.grand_total_label.setFont(bold_font)

        summary_layout.addRow("Subtotal:", self.subtotal_label)
        summary_layout.addRow(f"Overhead ({self.estimate.overhead_percent}%):", self.overhead_label)
        summary_layout.addRow(f"Profit ({self.estimate.profit_margin_percent}%):", self.profit_label)
        summary_layout.addRow(QLabel("Grand Total:"))
        summary_layout.addRow(self.grand_total_label)

        right_layout.addWidget(summary_group)

        generate_report_btn = QPushButton("Generate Report")
        right_layout.addWidget(generate_report_btn)
        right_layout.addStretch()

        self.layout.addLayout(left_layout, 2)  # 2/3 of space
        self.layout.addLayout(right_layout, 1)  # 1/3 of space

        # Connect signals
        add_task_btn.clicked.connect(self.add_task)
        add_material_btn.clicked.connect(self.add_material)
        add_labor_btn.clicked.connect(self.add_labor)
        remove_btn.clicked.connect(self.remove_item)
        generate_report_btn.clicked.connect(self.generate_report)

    def add_task(self):
        text, ok = QInputDialog.getText(self, "Add Task", "Enter task description:")
        if ok and text:
            task = Task(text)
            self.estimate.add_task(task)
            self.refresh_view()

    def add_material(self):
        selected = self.tree.currentItem()
        if not selected or not hasattr(selected, 'task_object'):
            QMessageBox.warning(self, "Selection Error", "Please select a task to add a material to.")
            return

        task_obj = selected.task_object
        dialog = SelectItemDialog("materials", self)
        if dialog.exec():
            item, quantity = dialog.get_selection()
            if item and quantity > 0:
                task_obj.add_material(item['name'], quantity, item['unit'], item['price'])
                self.refresh_view()

    def add_labor(self):
        selected = self.tree.currentItem()
        if not selected or not hasattr(selected, 'task_object'):
            QMessageBox.warning(self, "Selection Error", "Please select a task to add labor to.")
            return

        task_obj = selected.task_object
        dialog = SelectItemDialog("labor", self)
        if dialog.exec():
            item, hours = dialog.get_selection()
            if item and hours > 0:
                task_obj.add_labor(item['trade'], hours, item['rate_per_hour'])
                self.refresh_view()

    def remove_item(self):
        selected = self.tree.currentItem()
        if not selected: return

        parent = selected.parent()
        if parent:  # It's a material or labor item
            task_item = parent
            task_obj = task_item.task_object
            item_type = selected.text(0)

            if "Material" in item_type:
                task_obj.materials.pop(task_item.indexOfChild(selected))
            elif "Labor" in item_type:
                task_obj.labor.pop(task_item.indexOfChild(selected))
        else:  # It's a task
            self.estimate.tasks.pop(self.tree.indexOfTopLevelItem(selected))

        self.refresh_view()

    def refresh_view(self):
        self.tree.clear()
        for task in self.estimate.tasks:
            task_item = QTreeWidgetItem(self.tree, [task.description, "", f"${task.get_subtotal():.2f}"])
            task_item.task_object = task  # Attach the object to the UI item

            for mat in task.materials:
                QTreeWidgetItem(task_item,
                                [f"Material: {mat['name']}", f"{mat['qty']} {mat['unit']} @ ${mat['unit_cost']:.2f}",
                                 f"${mat['total']:.2f}"])
            for lab in task.labor:
                QTreeWidgetItem(task_item, [f"Labor: {lab['trade']}", f"{lab['hours']} hrs @ ${lab['rate']:.2f}/hr",
                                            f"${lab['total']:.2f}"])

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


class SelectItemDialog(QDialog):
    """Dialog to select a material/labor item and specify quantity/hours."""

    def __init__(self, item_type, parent=None):
        super().__init__(parent)
        self.item_type = item_type
        self.setWindowTitle(f"Select {item_type.capitalize()[:-1]}")
        self.db_manager = DatabaseManager()
        self.items = self.db_manager.get_items(item_type)

        layout = QVBoxLayout(self)
        self.table = QTableWidget()
        headers = ["Name", "Unit/Rate"] if item_type == "materials" else ["Trade", "Rate"]
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        for row, item in enumerate(self.items):
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(item[1]))
            self.table.setItem(row, 1, QTableWidgetItem(str(item[2])))

        self.table.resizeColumnsToContents()
        layout.addWidget(self.table)

        form_layout = QFormLayout()
        label_text = "Quantity:" if item_type == "materials" else "Hours:"
        self.spinbox = QDoubleSpinBox()
        self.spinbox.setRange(0.01, 1000000)
        form_layout.addRow(label_text, self.spinbox)
        layout.addLayout(form_layout)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def get_selection(self):
        selected_row = self.table.currentRow()
        if selected_row < 0:
            return None, 0

        selected_item = self.items[selected_row]
        return selected_item, self.spinbox.value()


class ReportDialog(QDialog):
    def __init__(self, estimate, parent=None):
        super().__init__(parent)
        self.estimate = estimate
        self.setWindowTitle("Final Estimate Report")
        self.setMinimumSize(700, 500)

        layout = QVBoxLayout(self)
        self.report_text = QTextEdit()
        self.report_text.setReadOnly(True)
        self.report_text.setFont(QFont("Courier New", 10))
        layout.addWidget(self.report_text)

        save_btn = QPushButton("Save to File")
        layout.addWidget(save_btn)
        save_btn.clicked.connect(self.save_report)

        self.generate_report_text()

    def generate_report_text(self):
        # This is adapted from the command-line version's report generator
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
            report.append(f"{'':<65}----------")
            report.append(f"{'Task Subtotal:':>65} ${task.get_subtotal():>10.2f}")

        report.append("\n" + sep_long)
        report.append("SUMMARY".center(80))
        report.append(sep_short)
        report.append(f"{'Total Direct Costs (Subtotal)':<65} ${totals['subtotal']:>10.2f}")
        report.append(f"Overhead ({self.estimate.overhead_percent}%):{'.' * 45} ${totals['overhead']:>10.2f}")
        report.append(f"{'Total Cost':<65} ${totals['subtotal'] + totals['overhead']:>10.2f}")
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