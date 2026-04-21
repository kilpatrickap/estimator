from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout, 
                             QComboBox, QCheckBox, QPushButton, QDoubleSpinBox, QLineEdit, 
                             QLabel, QScrollArea)
from PyQt6.QtCore import Qt, pyqtSignal
import pboq_constants as const

class PBOQToolsPane(QWidget):
    """The side panel for PBOQ tools like Column Mapping, Extend, Collect, and Summary."""
    
    # Signals for state changes and button clicks
    stateChanged = pyqtSignal()
    clearGrossRequested = pyqtSignal()
    extendRequested = pyqtSignal()
    revertRequested = pyqtSignal()
    recalculateRequested = pyqtSignal()
    clearBillRequested = pyqtSignal()
    collectRequested = pyqtSignal()
    columnHeadersRequested = pyqtSignal()
    wrapTextToggled = pyqtSignal(bool)
    alignTextLeftToggled = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(290)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(5)

        # 1. Column Mapping
        col_group = QGroupBox("Column Mapping")
        col_layout = QFormLayout(col_group)
        col_layout.setSpacing(1)
        col_layout.setContentsMargins(2, 2, 2, 2)
        self.cb_ref = QComboBox()
        self.cb_desc = QComboBox()
        self.cb_qty = QComboBox()
        self.cb_unit = QComboBox()
        self.cb_bill_rate = QComboBox()
        self.cb_bill_amount = QComboBox()
        self.cb_rate = QComboBox()
        self.cb_rate_code = QComboBox()
        self.cb_plug_rate = QComboBox()
        self.cb_plug_code = QComboBox()
        self.cb_prov_sum = QComboBox()
        self.cb_prov_sum_code = QComboBox()
        self.cb_pc_sum = QComboBox()
        self.cb_pc_sum_code = QComboBox()
        self.cb_daywork = QComboBox()
        self.cb_daywork_code = QComboBox()
        self.cb_sub_package = QComboBox()
        self.cb_sub_name = QComboBox()
        self.cb_sub_rate = QComboBox()
        self.cb_sub_markup = QComboBox()
        self.cb_sub_category = QComboBox()
        self.cb_sub_code = QComboBox()
        
        col_layout.addRow("Ref/Item:", self.cb_ref)
        col_layout.addRow("Description:", self.cb_desc)
        col_layout.addRow("Quantity:", self.cb_qty)
        col_layout.addRow("Unit:", self.cb_unit)
        
        # Hide standard columns from user mapping
        for cb in [self.cb_bill_rate, self.cb_bill_amount, self.cb_rate, self.cb_rate_code,
                   self.cb_plug_rate, self.cb_plug_code, self.cb_prov_sum, self.cb_prov_sum_code,
                   self.cb_pc_sum, self.cb_pc_sum_code,
                   self.cb_daywork, self.cb_daywork_code,
                   self.cb_sub_package, 
                   self.cb_sub_name, self.cb_sub_rate, self.cb_sub_markup,
                   self.cb_sub_category, self.cb_sub_code]:
            cb.hide()
        
        # Connect signals
        for cb in [self.cb_ref, self.cb_desc, self.cb_qty, self.cb_unit, 
                   self.cb_bill_rate, self.cb_bill_amount, 
                   self.cb_rate, self.cb_rate_code, self.cb_plug_rate, self.cb_plug_code,
                   self.cb_prov_sum, self.cb_prov_sum_code,
                   self.cb_pc_sum, self.cb_pc_sum_code,
                   self.cb_daywork, self.cb_daywork_code,
                   self.cb_sub_package, self.cb_sub_name, self.cb_sub_rate, self.cb_sub_markup,
                   self.cb_sub_category, self.cb_sub_code]:
            cb.currentIndexChanged.connect(self.stateChanged)
            cb.currentIndexChanged.connect(self.columnHeadersRequested)
            cb.currentIndexChanged.connect(self.update_extend_labels)
        
        container_layout.addWidget(col_group)

        # 2. Format
        format_group = QGroupBox("Format")
        format_layout = QVBoxLayout(format_group)
        format_layout.setSpacing(1)
        format_layout.setContentsMargins(2, 2, 2, 2)
        self.wrap_text_btn = QPushButton("Wrap Text")
        self.wrap_text_btn.setCheckable(True)
        self.wrap_text_btn.clicked.connect(lambda checked: self.wrapTextToggled.emit(checked))
        self.wrap_text_btn.clicked.connect(self.stateChanged)
        
        self.align_left_btn = QPushButton("Left Align Text")
        self.align_left_btn.setCheckable(True)
        self.align_left_btn.clicked.connect(lambda checked: self.alignTextLeftToggled.emit(checked))
        self.align_left_btn.clicked.connect(self.stateChanged)

        self.clear_all_btn = QPushButton("Clear Gross & Code")
        self.clear_all_btn.clicked.connect(self.clearGrossRequested)
        
        row1 = QHBoxLayout()
        row1.addWidget(self.wrap_text_btn)
        row1.addWidget(self.align_left_btn)
        format_layout.addLayout(row1)
        format_layout.addWidget(self.clear_all_btn)
        container_layout.addWidget(format_group)

        # 3. Extend
        extend_group = QGroupBox("Extend")
        extend_layout = QVBoxLayout(extend_group)
        extend_layout.setSpacing(1)
        extend_layout.setContentsMargins(2, 2, 2, 2)
        
        self.extend_cb0 = QCheckBox("Column 0")
        self.extend_cb1 = QCheckBox("Column 1")
        self.extend_cb2 = QCheckBox("Column 2")
        self.extend_cb3 = QCheckBox("Column 3")
        
        for cb in [self.extend_cb0, self.extend_cb1, self.extend_cb2, self.extend_cb3]:
            cb.toggled.connect(self.stateChanged)
            extend_layout.addWidget(cb)
            
        dummy_row = QHBoxLayout()
        dummy_row.addWidget(QLabel("Dummy Rate :"))
        self.dummy_rate_spin = QDoubleSpinBox()
        self.dummy_rate_spin.setRange(0.00, 999999.00)
        self.dummy_rate_spin.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        self.dummy_rate_spin.valueChanged.connect(self.stateChanged)
        dummy_row.addWidget(self.dummy_rate_spin)
        extend_layout.addLayout(dummy_row)
        
        extend_btns = QHBoxLayout()
        self.extend_btn = QPushButton("Extend")
        self.extend_btn.clicked.connect(self.extendRequested)
        self.revert_btn = QPushButton("Revert")
        self.revert_btn.clicked.connect(self.revertRequested)
        self.recalc_btn = QPushButton("Recalc")
        self.recalc_btn.clicked.connect(self.recalculateRequested)
        self.clear_bill_btn = QPushButton("Clear")
        self.clear_bill_btn.clicked.connect(self.clearBillRequested)
        extend_btns.addWidget(self.extend_btn)
        extend_btns.addWidget(self.revert_btn)
        extend_btns.addWidget(self.recalc_btn)
        extend_btns.addWidget(self.clear_bill_btn)
        extend_layout.addLayout(extend_btns)
        container_layout.addWidget(extend_group)

        # 4. Collect
        collect_group = QGroupBox("Collect")
        collect_layout = QVBoxLayout(collect_group)
        collect_layout.setSpacing(1)
        collect_layout.setContentsMargins(2, 2, 2, 2)
        
        kw_row = QHBoxLayout()
        kw_row.addWidget(QLabel("Keywords :"))
        self.collect_search_bar = QLineEdit()
        self.collect_search_bar.textChanged.connect(self.stateChanged)
        kw_row.addWidget(self.collect_search_bar)
        collect_layout.addLayout(kw_row)
        
        check_row = QHBoxLayout()
        self.collect_desc_cb = QCheckBox("Description")
        self.collect_amount_cb = QCheckBox("Bill Amount")
        self.collect_desc_cb.setChecked(True)
        self.collect_amount_cb.setChecked(True)
        self.collect_desc_cb.toggled.connect(self.stateChanged)
        self.collect_amount_cb.toggled.connect(self.stateChanged)
        check_row.addWidget(self.collect_desc_cb)
        check_row.addWidget(self.collect_amount_cb)
        collect_layout.addLayout(check_row)
        
        self.collect_btn = QPushButton("Collect")
        self.collect_btn.clicked.connect(self.collectRequested)
        collect_layout.addWidget(self.collect_btn)
        container_layout.addWidget(collect_group)


        
        # 6. Freeze Tools
        self.freeze_btn = QPushButton("Freeze Tools")
        self.freeze_btn.setCheckable(True)
        self.freeze_btn.clicked.connect(self._toggle_freeze)
        # Style will be handled by styles.qss initially (green/yellow)
        self.freeze_btn.setContentsMargins(0, 5, 0, 0) # Just add some spacing
        container_layout.addWidget(self.freeze_btn)

        # Apply Balanced Compact Stylesheet
        self.setStyleSheet("""
            QGroupBox {
                margin-top: 12px;
                padding-top: 4px;
                font-weight: 600;
                font-size: 8pt;
                border: 1px solid #ccc;
                border-radius: 4px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 10px;
                padding: 0 2px;
                top: 2px;
            }
            QLabel, QComboBox, QLineEdit, QPushButton, QCheckBox, QDoubleSpinBox {
                font-size: 8pt;
                margin: 0px;
                padding: 1px;
            }
            QPushButton {
                padding: 2px 5px;
            }
        """)

        container_layout.addStretch()
        self.update_extend_labels()
        scroll_area.setWidget(container)
        
        layout.addWidget(scroll_area)

    def populate_column_combos(self, column_names):
        combos = [self.cb_ref, self.cb_desc, self.cb_qty, self.cb_unit, 
                  self.cb_bill_rate, self.cb_bill_amount, 
                  self.cb_rate, self.cb_rate_code, self.cb_plug_rate, self.cb_plug_code,
                  self.cb_prov_sum, self.cb_prov_sum_code,
                  self.cb_pc_sum, self.cb_pc_sum_code,
                  self.cb_daywork, self.cb_daywork_code,
                  self.cb_sub_package, self.cb_sub_name, self.cb_sub_rate, self.cb_sub_markup,
                  self.cb_sub_category, self.cb_sub_code]
        
        for cb in combos:
            cb.blockSignals(True)
            cb.clear()
            cb.addItem("-- Select Column --")
            cb.addItems(column_names)
            
        # Standard Smart-Detection (Role to DB column name mapping)
        smart_map = {
            self.cb_rate: "GrossRate",
            self.cb_rate_code: "RateCode",
            self.cb_plug_rate: "PlugRate",
            self.cb_plug_code: "PlugCode",
            self.cb_prov_sum: "ProvSum",
            self.cb_prov_sum_code: "ProvSumCode",
            self.cb_pc_sum: "PCSum",
            self.cb_pc_sum_code: "PCSumCode",
            self.cb_daywork: "Daywork",
            self.cb_daywork_code: "DayworkCode",
            self.cb_sub_package: "SubbeePackage",
            self.cb_sub_name: "SubbeeName",
            self.cb_sub_rate: "SubbeeRate",
            self.cb_sub_markup: "SubbeeMarkup",
            self.cb_sub_category: "SubbeeCategory",
            self.cb_sub_code: "SubbeeCode"
        }
        
        for cb, db_name in smart_map.items():
            # 1. Try Exact match first
            idx = cb.findText(db_name, Qt.MatchFlag.MatchExactly)
            if idx >= 0:
                cb.setCurrentIndex(idx)
                continue
                
            # 2. Try Fuzzy match (case-insensitive, ignore spaces/underscores)
            clean_db = db_name.lower().replace(" ", "").replace("_", "")
            for i in range(1, cb.count()):
                clean_item = cb.itemText(i).lower().replace(" ", "").replace("_", "")
                if clean_item == clean_db:
                    cb.setCurrentIndex(i)
                    break
        
        # Fallback for Bill Rate/Amount if not already set (look for common indices 4,5 if they are "Column X")
        if self.cb_bill_rate.currentIndex() <= 0 and len(column_names) > 4:
            if "Column 4" in column_names: self.cb_bill_rate.setCurrentIndex(column_names.index("Column 4") + 1)
        if self.cb_bill_amount.currentIndex() <= 0 and len(column_names) > 5:
            if "Column 5" in column_names: self.cb_bill_amount.setCurrentIndex(column_names.index("Column 5") + 1)

        for cb in combos:
            cb.blockSignals(False)

    def get_mappings(self):
        """Returns the current column mappings based on UI selections."""
        m = {
            'ref': self.cb_ref.currentIndex() - 1,
            'desc': self.cb_desc.currentIndex() - 1,
            'qty': self.cb_qty.currentIndex() - 1,
            'unit': self.cb_unit.currentIndex() - 1,
            'bill_rate': self.cb_bill_rate.currentIndex() - 1,
            'bill_amount': self.cb_bill_amount.currentIndex() - 1,
            'rate': self.cb_rate.currentIndex() - 1,
            'rate_code': self.cb_rate_code.currentIndex() - 1,
            'plug_rate': self.cb_plug_rate.currentIndex() - 1,
            'plug_code': self.cb_plug_code.currentIndex() - 1,
            'prov_sum': self.cb_prov_sum.currentIndex() - 1,
            'prov_sum_code': self.cb_prov_sum_code.currentIndex() - 1,
            'pc_sum': self.cb_pc_sum.currentIndex() - 1,
            'pc_sum_code': self.cb_pc_sum_code.currentIndex() - 1,
            'daywork': self.cb_daywork.currentIndex() - 1,
            'daywork_code': self.cb_daywork_code.currentIndex() - 1,
            'sub_package': self.cb_sub_package.currentIndex() - 1,
            'sub_name': self.cb_sub_name.currentIndex() - 1,
            'sub_rate': self.cb_sub_rate.currentIndex() - 1,
            'sub_markup': self.cb_sub_markup.currentIndex() - 1,
            'sub_category': self.cb_sub_category.currentIndex() - 1,
            'sub_code': self.cb_sub_code.currentIndex() - 1
        }
        return m
    
    def set_mappings(self, data):
        # Only restore user-configurable columns. Auto-detected columns
        # (rates, subbee, etc.) are set by populate_column_combos and must
        # NOT be overridden by stale saved state values.
        mapping_keys = {
            'ref': self.cb_ref,
            'desc': self.cb_desc,
            'qty': self.cb_qty,
            'unit': self.cb_unit,
        }
        for key, cb in mapping_keys.items():
            if key in data:
                cb.blockSignals(True)
                cb.setCurrentIndex(data[key] + 1)
                cb.blockSignals(False)
        self.update_extend_labels()

    def update_extend_labels(self):
        """Updates Extend group checkbox labels based on current column mappings."""
        m = self.get_mappings()
        
        # Priority: map physical column index to its assigned logical role name
        roles = {
            m['ref']: "Ref/Item",
            m['desc']: "Description",
            m['qty']: "Quantity",
            m['unit']: "Unit"
        }
        
        self.extend_cb0.setText(roles.get(0, "Column 0"))
        self.extend_cb1.setText(roles.get(1, "Column 1"))
        self.extend_cb2.setText(roles.get(2, "Column 2"))
        self.extend_cb3.setText(roles.get(3, "Column 3"))

    def get_tools_state(self):
        """Returns the full state of all tools for persistence."""
        return {
            'mappings': self.get_mappings(),
            'extend_cb0': self.extend_cb0.isChecked(),
            'extend_cb1': self.extend_cb1.isChecked(),
            'extend_cb2': self.extend_cb2.isChecked(),
            'extend_cb3': self.extend_cb3.isChecked(),
            'dummy_rate': self.dummy_rate_spin.value(),
            'collect_kw': self.collect_search_bar.text(),
            'collect_desc': self.collect_desc_cb.isChecked(),
            'collect_amount': self.collect_amount_cb.isChecked(),
            'wrap_text': self.wrap_text_btn.isChecked(),
            'align_left': self.align_left_btn.isChecked(),
            'frozen': self.freeze_btn.isChecked(),
            'collect_revert': self.collect_btn.text() == "Revert"
        }

    def set_tools_state(self, state):
        """Restores the state of all tools from a dictionary."""
        if 'mappings' in state: self.set_mappings(state['mappings'])
        
        # Block signals to avoid redundant saves while loading
        self.blockSignals(True)
        try:
            if 'extend_cb0' in state: self.extend_cb0.setChecked(state['extend_cb0'])
            if 'extend_cb1' in state: self.extend_cb1.setChecked(state['extend_cb1'])
            if 'extend_cb2' in state: self.extend_cb2.setChecked(state['extend_cb2'])
            if 'extend_cb3' in state: self.extend_cb3.setChecked(state['extend_cb3'])
            if 'dummy_rate' in state: self.dummy_rate_spin.setValue(state['dummy_rate'])
            if 'collect_kw' in state: self.collect_search_bar.setText(state['collect_kw'])
            if 'collect_desc' in state: self.collect_desc_cb.setChecked(state['collect_desc'])
            if 'collect_amount' in state: self.collect_amount_cb.setChecked(state['collect_amount'])
            if 'wrap_text' in state: self.wrap_text_btn.setChecked(state['wrap_text'])
            if 'align_left' in state: self.align_left_btn.setChecked(state['align_left'])
            if 'frozen' in state:
                self.freeze_btn.setChecked(state['frozen'])
                self._toggle_freeze(state['frozen'])
            if state.get('collect_revert'):
                self.collect_btn.setText("Revert")
            else:
                self.collect_btn.setText("Collect")
        finally:
            self.blockSignals(False)
        
        self.update_extend_labels()

    def _toggle_freeze(self, frozen):
        """Freezes/Unfreezes all tool inputs to prevent accidental changes."""
        if frozen:
            self.freeze_btn.setText("Un-Freeze Tools")
            self.freeze_btn.setStyleSheet(f"background-color: {const.COLOR_FREEZE_GRAY.name()}; color: #555555; font-weight: bold;")
        else:
            self.freeze_btn.setText("Freeze Tools")
            # Clear stylesheet to revert to styles.qss defaults
            self.freeze_btn.setStyleSheet("")
        
        # Determine items to disable
        # We want to disable almost everything EXCEPT the freeze button itself
        widgets_to_toggle = [
            self.cb_ref, self.cb_desc, self.cb_qty, self.cb_unit, 
            self.cb_bill_rate, self.cb_bill_amount, 
            self.cb_rate, self.cb_rate_code, self.cb_plug_rate, self.cb_plug_code,
            self.cb_prov_sum, self.cb_prov_sum_code,
            self.cb_sub_package, self.cb_sub_name, self.cb_sub_rate, self.cb_sub_markup,
            self.wrap_text_btn, self.align_left_btn, self.clear_all_btn,
            self.extend_cb0, self.extend_cb1, self.extend_cb2, self.extend_cb3,
            self.dummy_rate_spin, self.extend_btn, self.revert_btn, self.recalc_btn, self.clear_bill_btn,
            self.collect_search_bar, self.collect_desc_cb, self.collect_amount_cb,
            self.collect_btn
        ]
        
        for w in widgets_to_toggle:
            w.setEnabled(not frozen)
            
        self.stateChanged.emit()
