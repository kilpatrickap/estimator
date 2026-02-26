from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, 
                             QPushButton, QComboBox, QLineEdit, QTextEdit, 
                             QButtonGroup)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QDoubleValidator

from database import DatabaseManager

class RateBuildupHeaderWidget(QWidget):
    """Encapsulates the Header and Toolbar sections of the Rate Build-up Dialog."""
    
    # Signals emitted when the user makes changes in the UI
    descriptionChanged = pyqtSignal()
    rateTypeChanged = pyqtSignal()
    categoryChanged = pyqtSignal(str)
    baseCurrencyChanged = pyqtSignal(str)
    unitChanged = pyqtSignal(str)
    adjustmentFactorChanged = pyqtSignal()
    exchangeRatesRequested = pyqtSignal()

    def __init__(self, estimate_object, parent=None):
        super().__init__(parent)
        self.estimate = estimate_object
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        # Breadcrumbs
        breadcrumb_text = "Estimate"
        if hasattr(self.estimate, 'project_name') and self.estimate.project_name:
            breadcrumb_text += f" &gt; <b>{self.estimate.project_name}</b>"
        
        breadcrumb_lbl = QLabel(breadcrumb_text)
        breadcrumb_lbl.setStyleSheet("color: #777; font-size: 11px;")
        layout.addWidget(breadcrumb_lbl)

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
        self.desc_input.setFixedHeight(60)
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
        # Install event filter to catch focus out
        self.desc_input.installEventFilter(self)
        desc_status_layout.addWidget(self.desc_input, 1)

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
        self.simple_rate_btn.setChecked(getattr(self.estimate, 'rate_type', 'Simple') == 'Simple')
        self.composite_rate_btn.setChecked(getattr(self.estimate, 'rate_type', 'Simple') == 'Composite')
        
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

        # Category Selector
        toolbar.addWidget(QLabel("Category:"))
        self.category_combo = QComboBox()
        
        db_m = DatabaseManager()
        self.categories = list(db_m.get_category_prefixes_dict().keys())
        
        self.category_combo.addItems(self.categories)
        curr_category = getattr(self.estimate, 'category', 'Miscellaneous')
        if curr_category in self.categories:
            self.category_combo.setCurrentText(curr_category)
        self.category_combo.currentTextChanged.connect(self._on_category_changed)
        toolbar.addWidget(self.category_combo)
        
        # Base Currency Selector
        toolbar.addWidget(QLabel("Base Currency:"))
        self.currency_combo = QComboBox()
        self.currencies = ["USD ($)", "EUR (€)", "GBP (£)", "JPY (¥)", "CAD ($)", "GHS (₵)", "CNY (¥)", "INR (₹)"]
        self.currency_combo.addItems(self.currencies)
        self.currency_combo.setCurrentText(self.estimate.currency)
        self.currency_combo.currentTextChanged.connect(self._on_currency_changed)
        toolbar.addWidget(self.currency_combo)

        ex_rate_btn = QPushButton("Exchange Rates")
        ex_rate_btn.clicked.connect(self.exchangeRatesRequested.emit)
        toolbar.addWidget(ex_rate_btn)
        toolbar.addStretch()

        # Adjustment Factor
        toolbar.addWidget(QLabel("Adjustment Factor:"))
        self.adjstmt_factor_input = QLineEdit()
        self.adjstmt_factor_input.setFixedWidth(60)
        factor_validator = QDoubleValidator(0.00, 99.99, 2)
        factor_validator.setNotation(QDoubleValidator.Notation.StandardNotation)
        self.adjstmt_factor_input.setValidator(factor_validator)
        
        adj_factor = getattr(self.estimate, 'adjustment_factor', 1.0)
        if adj_factor == 1.0:
            self.adjstmt_factor_input.setText("N/A")
        else:
            self.adjstmt_factor_input.setText(f"{adj_factor:.2f}")
            
        self.adjstmt_factor_input.editingFinished.connect(self._on_factor_changed)
        toolbar.addWidget(self.adjstmt_factor_input)
        
        # Unit Selection
        toolbar.addWidget(QLabel("Unit:"))
        self.unit_combo = QComboBox()
        self.units = ["m", "m2", "m3", "kg", "t", "Item"]
        self.unit_combo.addItems(self.units)
        self.unit_combo.setEditable(True)
        self.unit_combo.setFixedWidth(80)
        
        curr_unit = self.estimate.unit or "Item"
        idx = self.unit_combo.findText(curr_unit)
        if idx >= 0:
            self.unit_combo.setCurrentIndex(idx)
        else:
            self.unit_combo.setEditText(curr_unit)
            
        self.unit_combo.currentTextChanged.connect(self._on_unit_changed)
        toolbar.addWidget(self.unit_combo)
        
        layout.addLayout(toolbar)
        
        self.update_rate_type_style()

    def update_rate_type_style(self):
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
        
        rate_type = getattr(self.estimate, 'rate_type', 'Simple')
        if rate_type == 'Simple':
            self.simple_rate_btn.setChecked(True)
            self.composite_rate_btn.setChecked(False)
            self.simple_rate_btn.setStyleSheet(active_style)
            self.composite_rate_btn.setStyleSheet(inactive_style)
        else:
            self.composite_rate_btn.setChecked(True)
            self.simple_rate_btn.setChecked(False)
            self.simple_rate_btn.setStyleSheet(inactive_style)
            self.composite_rate_btn.setStyleSheet(active_style)

    def _toggle_simple(self):
        if getattr(self.estimate, 'rate_type', 'Simple') != 'Simple':
            self.rateTypeChanged.emit()

    def _toggle_composite(self):
        if getattr(self.estimate, 'rate_type', 'Simple') != 'Composite':
            # Allow the parent to handle saving of state and validation
            # (In RateBuildUpDialog, it modifies the model and updates the views)
            self.rateTypeChanged.emit()

    def _on_factor_changed(self):
        self.adjustmentFactorChanged.emit()

    def _on_unit_changed(self, new_unit):
        self.unitChanged.emit(new_unit)

    def _on_currency_changed(self, new_currency):
        self.baseCurrencyChanged.emit(new_currency)

    def _on_category_changed(self, new_category):
        self.categoryChanged.emit(new_category)

    def eventFilter(self, obj, event):
        from PyQt6.QtCore import QEvent
        if obj == self.desc_input and event.type() == QEvent.Type.FocusOut:
            self.descriptionChanged.emit()
        return super().eventFilter(obj, event)
        
    def refresh_ui(self):
        """Called by parent when the estimate object might have been entirely replaced (e.g. undo/redo)"""
        self.title_label.setText(f"{self.estimate.rate_code}")
        self.desc_input.setText(self.estimate.project_name)
        self.unit_info_label.setText(self.estimate.unit or "N/A")
        
        idx = self.unit_combo.findText(self.estimate.unit or "Item")
        if idx >= 0:
            self.unit_combo.setCurrentIndex(idx)
        else:
            self.unit_combo.setEditText(self.estimate.unit or "Item")
            
        self.currency_combo.setCurrentText(self.estimate.currency)
        self.category_combo.setCurrentText(getattr(self.estimate, 'category', 'Miscellaneous'))
        
        adj_factor = getattr(self.estimate, 'adjustment_factor', 1.0)
        if adj_factor == 1.0:
            self.adjstmt_factor_input.setText("N/A")
        else:
            self.adjstmt_factor_input.setText(f"{adj_factor:.2f}")
            
        self.update_rate_type_style()
