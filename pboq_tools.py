from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout, 
                             QComboBox, QCheckBox, QPushButton, QDoubleSpinBox, QLineEdit, 
                             QLabel, QScrollArea)
from PyQt6.QtCore import Qt, pyqtSignal

class PBOQToolsPane(QWidget):
    """The side panel for PBOQ tools like Column Mapping, Extend, Collect, and Summary."""
    
    # Signals for state changes and button clicks
    stateChanged = pyqtSignal()
    clearGrossRequested = pyqtSignal()
    extendRequested = pyqtSignal()
    clearBillRequested = pyqtSignal()
    collectRequested = pyqtSignal()
    populateRequested = pyqtSignal()
    summarizeRequested = pyqtSignal()
    columnHeadersRequested = pyqtSignal()
    wrapTextToggled = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
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
        container_layout.setSpacing(10)

        # 1. Column Mapping
        col_group = QGroupBox("Column Mapping")
        col_layout = QFormLayout(col_group)
        self.cb_ref = QComboBox()
        self.cb_desc = QComboBox()
        self.cb_qty = QComboBox()
        self.cb_unit = QComboBox()
        self.cb_bill_rate = QComboBox()
        self.cb_bill_amount = QComboBox()
        self.cb_rate = QComboBox()
        self.cb_rate_code = QComboBox()
        
        col_layout.addRow("Ref / Item No:", self.cb_ref)
        col_layout.addRow("Description:", self.cb_desc)
        col_layout.addRow("Quantity:", self.cb_qty)
        col_layout.addRow("Unit:", self.cb_unit)
        col_layout.addRow("Bill Rate:", self.cb_bill_rate)
        col_layout.addRow("Bill Amount:", self.cb_bill_amount)
        col_layout.addRow("Gross Rate:", self.cb_rate)
        col_layout.addRow("Rate Code:", self.cb_rate_code)
        
        # Connect signals
        for cb in [self.cb_ref, self.cb_desc, self.cb_qty, self.cb_unit, 
                   self.cb_bill_rate, self.cb_bill_amount, self.cb_rate, self.cb_rate_code]:
            cb.currentIndexChanged.connect(self.stateChanged)
            cb.currentIndexChanged.connect(self.columnHeadersRequested)
        
        container_layout.addWidget(col_group)

        # 2. Format
        format_group = QGroupBox("Format")
        format_layout = QVBoxLayout(format_group)
        self.wrap_text_btn = QPushButton("Wrap Text")
        self.wrap_text_btn.setCheckable(True)
        self.wrap_text_btn.clicked.connect(lambda checked: self.wrapTextToggled.emit(checked))
        self.wrap_text_btn.clicked.connect(self.stateChanged)
        
        self.clear_all_btn = QPushButton("Clear Gross & Code")
        self.clear_all_btn.clicked.connect(self.clearGrossRequested)
        
        btn_row = QHBoxLayout()
        btn_row.addWidget(self.wrap_text_btn)
        btn_row.addWidget(self.clear_all_btn)
        format_layout.addLayout(btn_row)
        container_layout.addWidget(format_group)

        # 3. Extend
        extend_group = QGroupBox("Extend")
        extend_layout = QVBoxLayout(extend_group)
        
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
        self.clear_bill_btn = QPushButton("Clear")
        self.clear_bill_btn.clicked.connect(self.clearBillRequested)
        extend_btns.addWidget(self.extend_btn)
        extend_btns.addWidget(self.clear_bill_btn)
        extend_layout.addLayout(extend_btns)
        container_layout.addWidget(extend_group)

        # 4. Collect
        collect_group = QGroupBox("Collect")
        collect_layout = QVBoxLayout(collect_group)
        
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
        
        collect_layout.addWidget(QLabel("Collection Target (Case Sensitive) :"))
        self.collection_target_bar = QLineEdit()
        self.collection_target_bar.setPlaceholderText("e.g. COLLECTION")
        self.collection_target_bar.textChanged.connect(self.stateChanged)
        collect_layout.addWidget(self.collection_target_bar)
        
        self.populate_btn = QPushButton("Populate")
        self.populate_btn.clicked.connect(self.populateRequested)
        collect_layout.addWidget(self.populate_btn)
        container_layout.addWidget(collect_group)

        # 5. Summary
        summary_group = QGroupBox("Summary")
        summary_layout = QVBoxLayout(summary_group)
        
        summary_layout.addWidget(QLabel("Summarize Collections (Case Sensitive) :"))
        
        s_check_row = QHBoxLayout()
        self.summary_desc_cb = QCheckBox("Description")
        self.summary_amount_cb = QCheckBox("Bill Amount")
        self.summary_desc_cb.setChecked(True)
        self.summary_desc_cb.toggled.connect(self.stateChanged)
        self.summary_amount_cb.toggled.connect(self.stateChanged)
        s_check_row.addWidget(self.summary_desc_cb)
        s_check_row.addWidget(self.summary_amount_cb)
        summary_layout.addLayout(s_check_row)
        
        self.summary_target_bar = QLineEdit()
        self.summary_target_bar.setPlaceholderText("CARRIED TO SUMMARY")
        self.summary_target_bar.textChanged.connect(self.stateChanged)
        summary_layout.addWidget(self.summary_target_bar)
        
        self.summarize_btn = QPushButton("Summarize")
        self.summarize_btn.clicked.connect(self.summarizeRequested)
        summary_layout.addWidget(self.summarize_btn)
        container_layout.addWidget(summary_group)

        container_layout.addStretch()
        scroll_area.setWidget(container)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll_area)

    def populate_column_combos(self, num_columns):
        explicit_columns = [f"Column {i}" for i in range(num_columns)]
        for cb in [self.cb_ref, self.cb_desc, self.cb_qty, self.cb_unit, 
                   self.cb_bill_rate, self.cb_bill_amount, self.cb_rate, self.cb_rate_code]:
            cb.blockSignals(True)
            cb.clear()
            cb.addItem("-- Select Column --")
            cb.addItems(explicit_columns)
            cb.blockSignals(False)

    def get_mappings(self):
        return {
            'ref': self.cb_ref.currentIndex() - 1,
            'desc': self.cb_desc.currentIndex() - 1,
            'qty': self.cb_qty.currentIndex() - 1,
            'unit': self.cb_unit.currentIndex() - 1,
            'bill_rate': self.cb_bill_rate.currentIndex() - 1,
            'bill_amount': self.cb_bill_amount.currentIndex() - 1,
            'rate': self.cb_rate.currentIndex() - 1,
            'rate_code': self.cb_rate_code.currentIndex() - 1
        }
    
    def set_mappings(self, data):
        mapping_keys = {
            'ref': self.cb_ref,
            'desc': self.cb_desc,
            'qty': self.cb_qty,
            'unit': self.cb_unit,
            'bill_rate': self.cb_bill_rate,
            'bill_amount': self.cb_bill_amount,
            'rate': self.cb_rate,
            'rate_code': self.cb_rate_code
        }
        for key, cb in mapping_keys.items():
            if key in data:
                cb.blockSignals(True)
                cb.setCurrentIndex(data[key] + 1)
                cb.blockSignals(False)
