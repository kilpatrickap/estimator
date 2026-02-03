from datetime import datetime

from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                             QTreeWidget, QTreeWidgetItem, QLabel, QFormLayout, QMessageBox,
                             QInputDialog, QDialog, QTableWidget, QTableWidgetItem, QHeaderView,
                             QTextEdit, QFileDialog, QDialogButtonBox, QLineEdit,
                             QSplitter, QFrame)
from report_generator import ReportGenerator
from PyQt6.QtGui import QFont, QDoubleValidator
from PyQt6.QtCore import Qt, QDate, QTimer
from database import DatabaseManager
from models import Estimate, Task
from currency_conversion_dialog import CurrencyConversionDialog


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
                profit=estimate_data['profit'],
                currency=estimate_data.get('currency', "GHS (₵)"),
                date=estimate_data.get('date')
            )
        else:  # Fallback
            self.estimate = Estimate("Error", "Error", 0, 0)

        # Setup Auto-Save
        self.autosave_timer = QTimer(self)
        self.autosave_timer.timeout.connect(self.auto_save)
        self.autosave_timer.start(60000) # Auto-save every 60 seconds

        self.setWindowTitle(f"Estimate: {self.estimate.project_name}")
# ...

        self.setMinimumSize(1000, 700) # Increased default minimum

        # Extract currency symbol
        import re
        match = re.search(r'\((.*?)\)', self.estimate.currency)
        self.currency_symbol = match.group(1) if match else "$"




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
        self.tree.setHeaderLabels(["Ref", "Tasks", "Calculations", "Cost", "Net Rate"])
        header = self.tree.header()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
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
        
        remove_btn.setStyleSheet("""
            QPushButton {
                background-color: #d32f2f;
                color: white;
            }
            QPushButton:hover {
                background-color: #ef5350;
            }
        """)

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
            lbl.setText(f"{self.currency_symbol}0.00")

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
        exchange_rates_btn = QPushButton("Exchange Rates")
        generate_report_btn = QPushButton("Generate Report")
        save_estimate_btn.setMinimumHeight(45)
        exchange_rates_btn.setMinimumHeight(45)
        generate_report_btn.setMinimumHeight(45)
        
        action_layout.addWidget(save_estimate_btn)
        action_layout.addWidget(exchange_rates_btn)
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
        exchange_rates_btn.clicked.connect(self.open_exchange_rates)
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

    def open_exchange_rates(self):
        dialog = CurrencyConversionDialog(self.estimate, self)
        if dialog.exec():
            self.refresh_view()

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
                task_obj.add_material(item['name'], quantity, item['unit'], item['price'], currency=item['currency'])
                self.refresh_view()

    def add_labor(self):
        task_obj = self._get_selected_task_object()
        if not task_obj: return

        dialog = SelectItemDialog("labor", self)
        if dialog.exec():
            item, hours = dialog.get_selection()
            if item and hours > 0:
                task_obj.add_labor(item['trade'], hours, item['rate_per_hour'], currency=item['currency'])
                self.refresh_view()

    def add_equipment(self):
        task_obj = self._get_selected_task_object()
        if not task_obj: return

        dialog = SelectItemDialog("equipment", self)
        if dialog.exec():
            item, hours = dialog.get_selection()
            if item and hours > 0:
                task_obj.add_equipment(item['name'], hours, item['rate_per_hour'], currency=item['currency'])
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

    def _get_currency_symbol(self, currency_text):
        if not currency_text: return "$"
        import re
        match = re.search(r'\((.*?)\)', currency_text)
        return match.group(1) if match else "$"

    def refresh_view(self):
        self.tree.clear()
        
        # We will display everything in Base Currency
        base_sym = self.currency_symbol

        for i, task in enumerate(self.estimate.tasks, 1):
            # Calculate converted subtotal for task
            task_subtotal_converted = 0
            for m in task.materials: task_subtotal_converted += self.estimate._get_item_total_in_base_currency(m)
            for l in task.labor: task_subtotal_converted += self.estimate._get_item_total_in_base_currency(l)
            for e in task.equipment: task_subtotal_converted += self.estimate._get_item_total_in_base_currency(e)
            
            task_item = QTreeWidgetItem(self.tree, [str(i), task.description, "", "", f"{base_sym}{task_subtotal_converted:,.2f}"])
            task_item.task_object = task  # Attach the main task object
            
            # Bold the task (parent) row
            bold_font = self.tree.font()
            bold_font.setBold(True)
            for col in range(self.tree.columnCount()):
                task_item.setFont(col, bold_font)

            for j, mat in enumerate(task.materials, 1):
                # Convert values to Base Currency
                uc_conv = self.estimate.convert_to_base_currency(mat['unit_cost'], mat.get('currency'))
                total_conv = self.estimate.convert_to_base_currency(mat['total'], mat.get('currency'))
                
                child = QTreeWidgetItem(task_item, [f"{i}.{j}",
                                                    f"Material: {mat['name']}",
                                                    f"{mat['qty']} {mat['unit']} @ {base_sym}{uc_conv:,.2f}",
                                                    f"{base_sym}{total_conv:,.2f}",
                                                    ""])
                child.item_data = mat
                child.item_type = 'material'

            offset = len(task.materials)
            for j, lab in enumerate(task.labor, 1):
                rate_conv = self.estimate.convert_to_base_currency(lab['rate'], lab.get('currency'))
                total_conv = self.estimate.convert_to_base_currency(lab['total'], lab.get('currency'))

                child = QTreeWidgetItem(task_item,
                                        [f"{i}.{offset + j}",
                                         f"Labor: {lab['trade']}", 
                                         f"{lab['hours']} hrs @ {base_sym}{rate_conv:,.2f}/hr",
                                         f"{base_sym}{total_conv:,.2f}",
                                         ""])
                child.item_data = lab
                child.item_type = 'labor'

            offset += len(task.labor)
            for j, equip in enumerate(task.equipment, 1):
                rate_conv = self.estimate.convert_to_base_currency(equip['rate'], equip.get('currency'))
                total_conv = self.estimate.convert_to_base_currency(equip['total'], equip.get('currency'))

                child = QTreeWidgetItem(task_item, [f"{i}.{offset + j}",
                                                    f"Equipment: {equip['name']}",
                                                    f"{equip['hours']} hrs @ {base_sym}{rate_conv:,.2f}/hr",
                                                    f"{base_sym}{total_conv:,.2f}",
                                                    ""])
                child.item_data = equip
                child.item_type = 'equipment'

        self.tree.expandAll()
        
        # Adjust widths
        for i in range(self.tree.columnCount()):
            self.tree.resizeColumnToContents(i)
            
        # Switch to interactive to allow manual adjustment
        self.tree.header().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.tree.header().setStretchLastSection(True)

        self.update_summary()

    def update_summary(self):
        totals = self.estimate.calculate_totals()
        symbol = self.currency_symbol
        self.subtotal_label.setText(f"{symbol}{totals['subtotal']:.2f}")
        self.overhead_label.setText(f"{symbol}{totals['overhead']:.2f}")
        self.profit_label.setText(f"{symbol}{totals['profit']:.2f}")
        self.grand_total_label.setText(f"{symbol}{totals['grand_total']:.2f}")

    def auto_save(self):
        """Silently saves the estimate if it has been saved before (has an ID)."""
        if self.estimate.id:
            self.db_manager.save_estimate(self.estimate)
            self.statusBar().showMessage(f"Auto-saved at {datetime.now().strftime('%H:%M')}", 3000)

    def save_estimate(self):
        reply = QMessageBox.question(self, "Confirm Save",
                                     "Do you want to save this estimate to the database?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            if self.db_manager.save_estimate(self.estimate):
                # Update ID if it was a new estimate
                QMessageBox.information(self, "Success", "Estimate has been saved successfully.")
            else:
                QMessageBox.critical(self, "Error", "Failed to save the estimate.")




    def generate_report(self):
        filename, _ = QFileDialog.getSaveFileName(self, "Export PDF Report", 
                                                  f"{self.estimate.project_name}_estimate.pdf",
                                                  "PDF Files (*.pdf)")
        if filename:
            try:
                # Get company name from settings
                company_name = self.db_manager.get_setting("company_name", "")
                company_logo = self.db_manager.get_setting("company_logo", "")
                
                generator = ReportGenerator(self.estimate)
                if generator.export_to_pdf(filename, company_name, company_logo):
                    QMessageBox.information(self, "Success", f"Report successfully exported to:\n{filename}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to generate report:\n{str(e)}")


class SelectItemDialog(QDialog):
    def __init__(self, item_type, parent=None):
        super().__init__(parent)
        self.item_type = item_type
        singular_name = item_type[:-1] if item_type.endswith('s') else item_type
        self.setWindowTitle(f"Select {singular_name.capitalize()}")
        self.resize(800, 500) # Widen the window by 2x (assuming ~400 default)
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
            headers = ["ID", "Material", "Unit", "Currency", "Price", "Date", "Location", "Contact", "Remarks"]
            self.table.setColumnCount(9)
        elif item_type == "labor":
            headers = ["ID", "Labor", "Currency", "Rate", "Date", "Location", "Contact", "Remarks"]
            self.table.setColumnCount(8)
        else:
            headers = ["ID", "Equipment", "Currency", "Rate", "Date", "Location", "Contact", "Remarks"]  # For equipment
            self.table.setColumnCount(8)

        self.table.setHorizontalHeaderLabels(headers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setDefaultSectionSize(50)  # Adjusted to 50px
        self.table.setShowGrid(True)
        self.table.setColumnHidden(0, True)
        layout.addWidget(self.table)

        # Setup input and buttons
        form_layout = QFormLayout()
        label_text = "Quantity:" if item_type == "materials" else "Hours:"
        
        # Validator for numerical input
        num_validator = QDoubleValidator(0.01, 1000000.0, 2)
        num_validator.setNotation(QDoubleValidator.Notation.StandardNotation)

        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("0.00")
        self.input_field.setText("1.00")
        self.input_field.setValidator(num_validator)
        
        form_layout.addRow(label_text, self.input_field)
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
            self.table.setItem(row, 0, QTableWidgetItem(str(item_data[0]))) # ID
            self.table.setItem(row, 1, QTableWidgetItem(item_data[1])) # Name/Trade
            
            if self.item_type == "materials":
                self.table.setItem(row, 2, QTableWidgetItem(str(item_data[2]))) # Unit
                self.table.setItem(row, 3, QTableWidgetItem(str(item_data[3]))) # Currency
                try:
                    price_text = f"{float(item_data[4]):.2f}"
                except (ValueError, TypeError):
                    price_text = str(item_data[4])
                self.table.setItem(row, 4, QTableWidgetItem(price_text)) # Price
                
                # Additional columns
                qdate = QDate.fromString(str(item_data[5]), "yyyy-MM-dd")
                display_date = qdate.toString("dd-MM-yy") if qdate.isValid() else str(item_data[5])
                self.table.setItem(row, 5, QTableWidgetItem(display_date)) # Date
                self.table.setItem(row, 6, QTableWidgetItem(str(item_data[6]) if item_data[6] else "")) # Location
                self.table.setItem(row, 7, QTableWidgetItem(str(item_data[7]) if item_data[7] else "")) # Contact
                self.table.setItem(row, 8, QTableWidgetItem(str(item_data[8]) if item_data[8] else "")) # Remarks
            else:
                self.table.setItem(row, 2, QTableWidgetItem(str(item_data[2]))) # Currency
                try:
                    rate_text = f"{float(item_data[3]):.2f}"
                except (ValueError, TypeError):
                    rate_text = str(item_data[3])
                self.table.setItem(row, 3, QTableWidgetItem(rate_text)) # Rate

                # Additional columns
                qdate = QDate.fromString(str(item_data[4]), "yyyy-MM-dd")
                display_date = qdate.toString("dd-MM-yy") if qdate.isValid() else str(item_data[4])
                self.table.setItem(row, 4, QTableWidgetItem(display_date)) # Date
                self.table.setItem(row, 5, QTableWidgetItem(str(item_data[5]) if item_data[5] else "")) # Location
                self.table.setItem(row, 6, QTableWidgetItem(str(item_data[6]) if item_data[6] else "")) # Contact
                self.table.setItem(row, 7, QTableWidgetItem(str(item_data[7]) if item_data[7] else "")) # Remarks
            
        # Adjust and reset to interactive
        for i in range(self.table.columnCount()):
            self.table.resizeColumnToContents(i)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)

    def get_selection(self):
        selected_row = self.table.currentRow()
        if selected_row < 0:
            return None, 0
            
        try:
            value = float(self.input_field.text())
        except ValueError:
            value = 0.0
            
        # Use the filtered list to get the correct item
        selected_item = self.current_items[selected_row]
        return selected_item, value


# --- END OF CHANGE ---


