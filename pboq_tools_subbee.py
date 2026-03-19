from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QCheckBox, 
                             QPushButton, QDoubleSpinBox, QLabel, QLineEdit)
from PyQt6.QtCore import pyqtSignal

class SubcontractorTool(QWidget):
    """Widget for managing Subcontractor Rate visibility and package settings."""
    
    visibilityChanged = pyqtSignal(bool)
    stateChanged = pyqtSignal()
    openAdjudicatorRequested = pyqtSignal()
    linkBillRateRequested = pyqtSignal()
    clearSubcontractorRequested = pyqtSignal()
    assignPackageRequested = pyqtSignal(str)
    managePackagesRequested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        self.show_sub_cb = QCheckBox("Show Subcontractor Columns")
        self.show_sub_cb.toggled.connect(self.visibilityChanged.emit)
        self.show_sub_cb.toggled.connect(self.stateChanged.emit)
        
        markup_layout = QHBoxLayout()
        markup_label = QLabel("Global Markup (%):")
        self.markup_spin = QDoubleSpinBox()
        self.markup_spin.setRange(0.00, 1000.00)
        self.markup_spin.setValue(10.00)  # Default 10%
        self.markup_spin.setSuffix(" %")
        self.markup_spin.valueChanged.connect(self.stateChanged.emit)
        
        markup_layout.addWidget(markup_label)
        markup_layout.addWidget(self.markup_spin)
        markup_layout.addStretch()

        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(5)
        
        # Package Assignment
        assign_layout = QHBoxLayout()
        self.package_input = QLineEdit()
        self.package_input.setPlaceholderText("Work Package Name")
        self.assign_package_btn = QPushButton("Assign to Selected")
        self.assign_package_btn.clicked.connect(lambda: self.assignPackageRequested.emit(self.package_input.text().strip()))
        
        assign_layout.addWidget(self.package_input)
        assign_layout.addWidget(self.assign_package_btn)
        btn_layout.addLayout(assign_layout)

        # Action Row (Packages & Adjudicator)
        actions_row = QHBoxLayout()
        self.manage_packages_btn = QPushButton("Packages")
        self.manage_packages_btn.clicked.connect(self.managePackagesRequested.emit)
        
        self.adjudicator_btn = QPushButton("Adjudicator")
        self.adjudicator_btn.clicked.connect(self.openAdjudicatorRequested.emit)
        
        actions_row.addWidget(self.manage_packages_btn)
        actions_row.addWidget(self.adjudicator_btn)
        btn_layout.addLayout(actions_row)

        action_layout = QHBoxLayout()
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.clicked.connect(self.clearSubcontractorRequested.emit)
        action_layout.addWidget(self.clear_btn)

        self.link_bill_rate_btn = QPushButton("Link to Bill Rate")
        self.link_bill_rate_btn.clicked.connect(lambda: self.linkBillRateRequested.emit())
        action_layout.addWidget(self.link_bill_rate_btn)
        
        btn_layout.addLayout(action_layout)

        layout.addWidget(self.show_sub_cb)
        layout.addLayout(markup_layout)
        layout.addLayout(btn_layout)
        layout.addStretch()

    def get_state(self):
        return {
            "show_sub": self.show_sub_cb.isChecked(),
            "markup": self.markup_spin.value()
        }

    def set_state(self, state):
        if "show_sub" in state:
            self.show_sub_cb.blockSignals(True)
            self.show_sub_cb.setChecked(state["show_sub"])
            self.show_sub_cb.blockSignals(False)
        if "markup" in state:
            self.markup_spin.blockSignals(True)
            self.markup_spin.setValue(state["markup"])
            self.markup_spin.blockSignals(False)
