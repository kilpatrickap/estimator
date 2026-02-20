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

        # Header Section
        header = QFrame()
        from PyQt6.QtWidgets import QSizePolicy
        header.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        header.setStyleSheet("background-color: #f8f9fa; border-radius: 4px; border: 1px solid #e0e0e0;")
        h_layout = QVBoxLayout(header)
        h_layout.setContentsMargins(10, 5, 10, 5)
        h_layout.setSpacing(0)
        
        self.title_label = QLabel(f"{self.estimate.rate_code}")
        self.title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #2e7d32; border: none;")
        
        h_layout.addWidget(self.title_label)

        desc_status_layout = QHBoxLayout()
        desc_status_layout.setSpacing(10)
        
        self.desc_input = QTextEdit(self.estimate.project_name)
        self.desc_input.setFixedHeight(60) # Height for ~3 lines
        self.desc_input.setTabChangesFocus(True)
        self.desc_input.setAcceptRichText(False)
        self.desc_input.setStyleSheet("""
            QTextEdit {
                font-size: 14px; 
                font-weight: bold; 
                color: blue; 
                border: 1px solid #ccc; 
                border-radius: 4px; 
                padding: 4px;
                background-color: white;
            }
        """)
        
        # Save on focus out
        self.desc_input.installEventFilter(self)
        desc_status_layout.addWidget(self.desc_input, 1) # Stretch factor 1

        # Vertical Column 1: Unified Capsules (Toggle, Status, Unit)
        unit_status_column = QVBoxLayout()
        unit_status_column.setSpacing(4)
        
        # 1. Rate Type Toggle Capsule
        self.toggle_frame = QFrame()
        self.toggle_frame.setFixedSize(110, 22)
        self.toggle_frame.setStyleSheet("""
            QFrame {
                background-color: #333;
                border: 1px solid #00c896;
                border-radius: 11px;
            }
        """)
        toggle_layout = QHBoxLayout(self.toggle_frame)
        toggle_layout.setContentsMargins(1, 1, 1, 1)
        toggle_layout.setSpacing(0)
        
        self.simple_rate_btn = QPushButton("Simple")
        self.composite_rate_btn = QPushButton("Composite")
        self.simple_rate_btn.setCheckable(True)
        self.composite_rate_btn.setCheckable(True)
        self.simple_rate_btn.setChecked(self.estimate.rate_type == 'Simple')
        self.composite_rate_btn.setChecked(self.estimate.rate_type == 'Composite')
        
        self.rate_type_group = QButtonGroup(self)
        self.rate_type_group.addButton(self.simple_rate_btn)
        self.rate_type_group.addButton(self.composite_rate_btn)
        self.rate_type_group.setExclusive(True)
        
        self.simple_rate_btn.clicked.connect(self._toggle_simple)
        self.composite_rate_btn.clicked.connect(self._toggle_composite)
        
        toggle_layout.addWidget(self.simple_rate_btn)
        toggle_layout.addWidget(self.composite_rate_btn)
        unit_status_column.addWidget(self.toggle_frame, alignment=Qt.AlignmentFlag.AlignCenter)

        # 2. Status Badge Capsule
        self.status_badge = QLabel("BASE RATE")
        self.status_badge.setFixedSize(110, 22)
        self.status_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_badge.setStyleSheet("""
            QLabel {
                border-radius: 11px;
                font-size: 8px;
                font-weight: bold;
                color: #333;
                background-color: #fbc02d;
                border: none;
            }
        """)
        unit_status_column.addWidget(self.status_badge, alignment=Qt.AlignmentFlag.AlignCenter)

        # 3. Unit Capsule
        self.unit_info_label = QLabel(self.estimate.unit or "N/A")
        self.unit_info_label.setFixedSize(110, 22)
        self.unit_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.unit_info_label.setStyleSheet("""
            QLabel {
                font-size: 11px; 
                font-weight: bold; 
                color: #1565c0; 
                background-color: #e3f2fd; 
                border: 1px solid #90caf9; 
                border-radius: 11px; 
            }
        """)
        unit_status_column.addWidget(self.unit_info_label, alignment=Qt.AlignmentFlag.AlignCenter)
        desc_status_layout.addLayout(unit_status_column)
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
        self.tree.itemChanged.connect(self.on_item_changed)
        
        # Composite Table
        self.composite_table = QTableWidget()
        headers = ["Rate Code", "Description", "Unit", "Base Curr", "Net Rate", "Convert Unit", "Calculations", "New Net Rate"]
        self.composite_table.setColumnCount(len(headers))
        self.composite_table.setHorizontalHeaderLabels(headers)
        header_view2 = self.composite_table.horizontalHeader()
        header_view2.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header_view2.setStretchLastSection(True)
        self.composite_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.composite_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.composite_table.setAlternatingRowColors(True)
        self.composite_table.setRowCount(1)
        
        self.composite_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.composite_table.customContextMenuRequested.connect(self.show_composite_context_menu)
        self.composite_table.cellDoubleClicked.connect(self.edit_composite_calculation)
        
        self.tables_splitter = QSplitter(Qt.Orientation.Vertical)
        self.tables_splitter.addWidget(self.tree)
        self.tables_splitter.addWidget(self.composite_table)
        
        self.main_v_splitter.addWidget(self.tables_splitter)

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

        # Ensure correct visibility of the tables at startup
        self._update_rate_type_style()
        

    def _update_rate_type_style(self):
        """Updates the visual style of the toggle buttons based on selection."""
        active_style = """
            QPushButton { 
                background-color: #00c896; 
                color: #1a1a1a; 
                border: none; 
                border-radius: 10px; 
                font-weight: bold; 
                font-size: 9px; 
                padding: 1px;
            }
        """
        inactive_style = """
            QPushButton { 
                background-color: transparent; 
                color: #00c896; 
                border: none; 
                font-weight: bold; 
                font-size: 9px; 
                padding: 1px;
            }
            QPushButton:hover {
                color: white;
            }
        """
        
        if self.estimate.rate_type == 'Simple':
            self.simple_rate_btn.setChecked(True)
            self.composite_rate_btn.setChecked(False)
            self.simple_rate_btn.setStyleSheet(active_style)
            self.composite_rate_btn.setStyleSheet(inactive_style)
            if hasattr(self, 'composite_table'):
                self.composite_table.hide()
            if hasattr(self, 'tree'):
                self.tree.show()
        else:
            self.composite_rate_btn.setChecked(True)
            self.simple_rate_btn.setChecked(False)
            self.simple_rate_btn.setStyleSheet(inactive_style)
            self.composite_rate_btn.setStyleSheet(active_style)
            if hasattr(self, 'composite_table'):
                self.composite_table.show()
            if hasattr(self, 'tree'):
                self.tree.show()

    def _toggle_simple(self):
        if self.estimate.rate_type != 'Simple':
            if hasattr(self.estimate, 'sub_rates') and len(self.estimate.sub_rates) > 0:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(self, "Cannot Switch to Simple", 
                                    "This rate currently contains imported rates.\n\n"
                                    "Please remove all imported rates from the composite build-up before switching back to a Simple rate.")
                # Revert button states visually without triggering signals
                self.simple_rate_btn.blockSignals(True)
                self.composite_rate_btn.blockSignals(True)
                self.simple_rate_btn.setChecked(False)
                self.composite_rate_btn.setChecked(True)
                self.simple_rate_btn.blockSignals(False)
                self.composite_rate_btn.blockSignals(False)
                return
                
            self._save_state()
            self.estimate.rate_type = 'Simple'
            self._update_rate_type_style()
            self.save_changes(show_message=False)
            
    def _toggle_composite(self):
        if self.estimate.rate_type != 'Composite':
            self._save_state()
            self.estimate.rate_type = 'Composite'
            self._update_rate_type_style()
            self.save_changes(show_message=False)

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
        
        remove_action = menu.addAction("Remove Selected")
        remove_action.triggered.connect(self.remove_selected)
        
        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def show_composite_context_menu(self, pos):
        menu = QMenu(self)
        import_action = menu.addAction("Import Rate")
        import_action.triggered.connect(self.import_composite_rate)
        
        selected_indexes = self.composite_table.selectionModel().selectedRows()
        if selected_indexes:
            row = selected_indexes[0].row()
            if row < len(self.estimate.sub_rates): # Not the blank row
                menu.addSeparator()
                
                insert_action = menu.addAction("Insert Rate")
                insert_action.triggered.connect(lambda: self.insert_composite_rate(row))
                
                goto_action = menu.addAction("Go To Rate")
                goto_action.triggered.connect(lambda: self.go_to_composite_rate(row))
                
                remove_action = menu.addAction("Remove Rate")
                remove_action.triggered.connect(lambda: self.remove_composite_rate(row))
                
        menu.exec(self.composite_table.viewport().mapToGlobal(pos))

    def insert_composite_rate(self, row):
        if row >= len(self.estimate.sub_rates): return
        sub = self.estimate.sub_rates[row]
        
        # Find or create "Imported Rates" task
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
        name = f"{getattr(sub, 'rate_code', '')}: {sub.project_name}"
        
        self._save_state()
        imported_task.add_material(
            name=name,
            quantity=qty,
            unit=getattr(sub, 'converted_unit', sub.unit),
            unit_cost=calc_subtotal,
            currency=sub.currency
        )
        self.save_changes(show_message=False)
        self.refresh_view()
        self.stateChanged.emit()

    def go_to_composite_rate(self, row):
        if row < len(self.estimate.sub_rates):
            sub = self.estimate.sub_rates[row]
            rate_code = getattr(sub, 'rate_code', '')
            if rate_code and self.main_window and hasattr(self.main_window, 'show_rate_in_database'):
                self.main_window.show_rate_in_database(rate_code)

    def edit_composite_calculation(self, row, col):
        if col != 6: # Calculations column
            return
            
        if row >= len(self.estimate.sub_rates): # Blank row check
            return
            
        sub = self.estimate.sub_rates[row]
        totals = sub.calculate_totals()
        
        # Create a mock dictionary that behaves like a material item for the dialog,
        # but intercepts dictionary assignments to mutate the sub rate directly!
        class SubRateAdapterProxy(dict):
            def __setitem__(self, key, value):
                super().__setitem__(key, value)
                if key == 'qty':
                    sub.quantity = value
                elif key == 'formula':
                    sub.formula = value

        mock_item = SubRateAdapterProxy({
            'name': sub.project_name,
            'qty': getattr(sub, 'quantity', 1.0),
            'formula': getattr(sub, 'formula', None),
            'unit_cost': totals['grand_total'] 
        })
        
        if self.main_window and hasattr(self.main_window, 'open_edit_item_window'):
            self.main_window.open_edit_item_window(
                mock_item, 'material', self.estimate.currency, self, 
                custom_title=f"Convert Unit: {sub.rate_code}"
            )
        else:
            from edit_item_dialog import EditItemDialog
            dialog = EditItemDialog(mock_item, 'material', self.estimate.currency, self)
            dialog.setWindowTitle(f"Convert Unit: {sub.rate_code}")
            
            if dialog.exec():
                self._save_state()
                sub.quantity = mock_item['qty']
                sub.formula = mock_item['formula']
                self.save_changes(show_message=False)
                self.refresh_view()
                self.stateChanged.emit()

    def _update_sub_rate_unit(self, sub_estimate, new_unit):
        current = getattr(sub_estimate, 'converted_unit', sub_estimate.unit)
        if current != new_unit:
            self._save_state()
            sub_estimate.converted_unit = new_unit
            self.save_changes(show_message=False)
            
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(0, self.refresh_view)

    def import_composite_rate(self):
        dialog = RateSelectionDialog(self)
        if dialog.exec() and dialog.selected_rate_id:
            db_id = dialog.selected_rate_id
            
            # Load estimate object
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
                self._save_state()
                new_sub = copy.deepcopy(selected_estimate)
                self.estimate.add_sub_rate(new_sub)
                self.refresh_view()
                self.save_changes(show_message=False)

    def remove_composite_rate(self, index):
        if 0 <= index < len(self.estimate.sub_rates):
            reply = QMessageBox.question(
                self, 'Remove Rate',
                "Are you sure you want to remove this rate from the composite build-up?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._save_state()
                self.estimate.remove_sub_rate(index)
                self.refresh_view()
                self.save_changes(show_message=False)

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

    def toggle_highlights(self):
        """Toggles the visibility of library-sync highlights."""
        self.show_impact_highlights = not self.show_impact_highlights
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

    def edit_task(self, item):
        """Triggers in-line editing for the task description."""
        self.tree.editItem(item, 1)

    def on_item_changed(self, item, column):
        """Handles the completion of in-line editing for tasks."""
        if self.is_loading or column != 1:
            return
            
        # Only top-level items (tasks) are editable in column 1
        if item.parent():
            return
            
        task_idx = self.tree.indexOfTopLevelItem(item)
        if 0 <= task_idx < len(self.estimate.tasks):
            old_desc = self.estimate.tasks[task_idx].description
            new_desc = item.text(column).strip()
            
            if new_desc and new_desc != old_desc:
                self._save_state()
                self.estimate.tasks[task_idx].description = new_desc
                # Refresh to ensure styling and other labels are correct
                self.save_changes(show_message=False)
                self.refresh_view()
            elif not new_desc:
                # Revert if empty
                self.is_loading = True
                item.setText(column, old_desc)
                self.is_loading = False

    def handle_library_update(self, table_name, resource_name, new_val, new_curr):
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
                    if item.get(rate_key) != new_val or item.get('currency') != new_curr:
                        affected_items.append(item)

        if affected_items:
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
                    # Recalculate item total (depends on qty)
                    qty_key = 'qty' if item_type == 'material' else ('amount' if item_type == 'indirect_costs' else 'hours')
                    item['total'] = item[qty_key] * new_val
                
                # Mark as impacted for highlighting
                self.impacted_resources.add((item_type, resource_name))
                self.refresh_view()
                self.stateChanged.emit()

    def go_to_resource(self, item):
        """Navigates to the master resource in the main database."""
        if hasattr(item, 'item_type') and hasattr(item, 'item_data'):
            rtype = item.item_type
            rdata = item.item_data
            
            if hasattr(item, 'task_object') and item.task_object.description == "Imported Rates":
                name = rdata.get('name', '')
                if ':' in name:
                    rate_code = name.split(':')[0].strip()
                    if rate_code and self.main_window and hasattr(self.main_window, 'show_rate_in_database'):
                        self.main_window.show_rate_in_database(rate_code)
                        return
            
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
                 # Fallback for dialog mode
                 dialog = EditItemDialog(item.item_data, item.item_type, self.estimate.currency, self, custom_name_label=custom_name_label)
                 if custom_title:
                     dialog.setWindowTitle(custom_title)
                 if dialog.exec():
                     self.refresh_view()
                     self.stateChanged.emit()

    def save_changes(self, show_message=True):
        """Saves the modified rate build-up back to the rates database."""
        # Sync latest notes from UI FIRST (before any potential refresh_view() calls)
        self.estimate.notes = self.notes_input.toPlainText().strip()
        
        # Ensure we sync the latest adjustment factor and refresh other totals
        self._handle_factor_formatting()
        
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
            self.status_badge.setStyleSheet("QLabel { border-radius: 11px; font-size: 8px; font-weight: bold; color: white; background-color: #673ab7; border: none; }")
            self.setWindowTitle(f"Edit Rate Build-up: {self.estimate.rate_code} (ADJUSTED)")
            self.subtotal_header_label.setText("Build-up Sub-Total (Sum of Adjusted Net Rates):")
        else:
            self.status_badge.setText("BASE RATE")
            self.status_badge.setStyleSheet("QLabel { border-radius: 11px; font-size: 8px; font-weight: bold; color: #333; background-color: #fbc02d; border: none; }")
            self.setWindowTitle(f"Edit Rate Build-up: {self.estimate.rate_code}")
            self.subtotal_header_label.setText("Build-up Sub-Total (Sum of Net Rates):")

        self.subtotal_label.setText(f"{base_sym}{totals['subtotal']:,.2f}")
        self.overhead_label.setText(f"{base_sym}{totals['overhead']:,.2f}")
        self.profit_label.setText(f"{base_sym}{totals['profit']:,.2f}")
        self.total_label.setText(f"{base_sym}{totals['grand_total']:,.2f}")

        # Update dynamic labels
        if hasattr(self, 'desc_input') and not self.desc_input.hasFocus():
            self.desc_input.setPlainText(self.estimate.project_name)
        if hasattr(self, 'unit_info_label'):
            self.unit_info_label.setText(self.estimate.unit or "N/A")
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
            # Enable in-line editing for the Tasks column
            task_item.setFlags(task_item.flags() | Qt.ItemFlag.ItemIsEditable)
            
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
                    
                    item_label = f"{label_prefix}: {item[name_key]}"
                    if task.description == "Imported Rates":
                        item_label = str(item[name_key])
                    
                    child = QTreeWidgetItem(task_item, [
                        f"{i}.{sub_idx}",
                        item_label,
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
                    
                    # Highlight if impacted by library change (Color Pink)
                    if self.show_impact_highlights and (type_code, item[name_key]) in self.impacted_resources:
                        for c in range(self.tree.columnCount()):
                            from PyQt6.QtGui import QColor
                            soft_pink = QColor("#fce4ec") # Very light pink
                            child.setBackground(c, soft_pink)
                            child.setForeground(c, Qt.GlobalColor.black)

                    sub_idx += 1

        self.tree.expandAll()
        for i in range(self.tree.columnCount()):
            self.tree.resizeColumnToContents(i)
        
        self.tree.header().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.tree.header().setStretchLastSection(True)
        
        # Refresh Composite Table
        if hasattr(self, 'composite_table'):
            self.composite_table.setRowCount(0)
            
            mismatched_rates = []
            
            # Add existing sub-rates
            for sub in self.estimate.sub_rates:
                row = self.composite_table.rowCount()
                self.composite_table.insertRow(row)
                
                totals = sub.calculate_totals()
                adj_factor = getattr(sub, 'adjustment_factor', 1.0)
                
                items = [
                    QTableWidgetItem(str(getattr(sub, 'rate_code', ''))),
                    QTableWidgetItem(str(sub.project_name)),
                    QTableWidgetItem(str(sub.unit)),
                    QTableWidgetItem(str(sub.currency)),
                    QTableWidgetItem(f"{totals['subtotal']:,.2f}"),
                    None, # Convert Unit
                    QTableWidgetItem(f"{getattr(sub, 'quantity', 1.0):.2f}"), # Calculations
                    QTableWidgetItem(f"{(totals['subtotal'] * getattr(sub, 'quantity', 1.0)):,.2f}") # New Net Rate
                ]
                for col, item in enumerate(items):
                    if item:
                        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                        # We can store the object ref in the first item
                        if col == 0:
                            item.setData(Qt.ItemDataRole.UserRole, sub)
                        self.composite_table.setItem(row, col, item)
                
                # Convert Unit ComboBox
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
                    
            # Add one blank row at the end
            row = self.composite_table.rowCount()
            self.composite_table.insertRow(row)
            for col in range(self.composite_table.columnCount()):
                item = QTableWidgetItem("")
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.composite_table.setItem(row, col, item)
            
            self.composite_table.resizeColumnsToContents()
            self.composite_table.horizontalHeader().setStretchLastSection(True)
            
            if mismatched_rates and not self.mismatch_notified:
                self.mismatch_notified = True
                QMessageBox.warning(self, "Unit Mismatches Detected", 
                    f"The following imported rates have units that do not match the current rate unit ({self.estimate.unit}):\n"
                    f"{', '.join(mismatched_rates)}\n\n"
                    f"Please convert the imported rate units and review their calculations to match.")
        
        self.is_loading = False
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

class RateSelectionDialog(QDialog):
    """Dialog to select a rate build-up from the rates database."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Rate from Database")
        self.setMinimumSize(700, 400)
        self.selected_rate_id = None
        
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
        self.db_manager = DatabaseManager("construction_rates.db")
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
        rates = self.db_manager.get_rates_data()
        headers = ["Rate Code", "Description", "Unit", "Base Curr", "Net Rate", "Gross Rate"]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setRowCount(0)
        
        self.full_data = [] # To hold (db_id, row_data)
        for r, row_data in enumerate(rates):
            self.table.insertRow(r)
            self.full_data.append((row_data[0], row_data))
            
            # 0: db_id, 1: rate_code, 2: project_name, 3: unit, 4: currency, 5: net_total, 6: grand_total ...
            items = [
                row_data[1], row_data[2], row_data[3], row_data[4], 
                f"{row_data[5]:,.2f}" if row_data[5] is not None else "0.00",
                f"{row_data[6]:,.2f}" if row_data[6] is not None else "0.00"
            ]
            for c, val in enumerate(items):
                item = QTableWidgetItem(str(val))
                self.table.setItem(r, c, item)
                
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setStretchLastSection(True)

    def filter_table(self, text):
        query = text.lower()
        for row in range(self.table.rowCount()):
            match = False
            for col in range(self.table.columnCount()):
                val = self.table.item(row, col)
                if val and query in val.text().lower():
                    match = True
                    break
            self.table.setRowHidden(row, not match)

    def accept(self):
        row = self.table.currentRow()
        if row >= 0:
            self.selected_rate_id = self.full_data[row][0]
            super().accept()
        else:
            QMessageBox.warning(self, "Selection Error", "Please select a rate.")
