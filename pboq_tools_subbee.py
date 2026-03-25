from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QCheckBox, 
                             QPushButton, QDoubleSpinBox, QLabel, QLineEdit, QGridLayout)
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
    openDirectoryRequested = pyqtSignal()

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
        
        self.show_cb = self.show_sub_cb # Keep for old references? No, let's just clean up.
        
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(5)
        
        # Package Assignment
        assign_layout = QHBoxLayout()
        assign_layout.setSpacing(10)
        self.package_input = QLineEdit()
        self.package_input.setPlaceholderText("Work Package Name")
        self.assign_package_btn = QPushButton("Assign to Selected")
        self.assign_package_btn.clicked.connect(lambda: self.assignPackageRequested.emit(self.package_input.text().strip()))
        
        assign_layout.addWidget(self.package_input)
        assign_layout.addWidget(self.assign_package_btn)
        btn_layout.addLayout(assign_layout)

        # Action Grid (Orderly 2x2 Layout for primary actions)
        grid_layout = QGridLayout()
        grid_layout.setSpacing(5)
        
        self.manage_packages_btn = QPushButton("Packages")
        self.manage_packages_btn.clicked.connect(self.managePackagesRequested.emit)
        
        self.adjudicator_btn = QPushButton("Adjudicator")
        self.adjudicator_btn.clicked.connect(self.openAdjudicatorRequested.emit)
        
        self.directory_btn = QPushButton("Directory")
        self.directory_btn.clicked.connect(self.openDirectoryRequested.emit)
        
        self.link_bill_rate_btn = QPushButton("Link to Bill Rate")
        self.link_bill_rate_btn.clicked.connect(lambda: self.linkBillRateRequested.emit())

        # Row 0: Packages & Adjudicator
        grid_layout.addWidget(self.manage_packages_btn, 0, 0)
        grid_layout.addWidget(self.adjudicator_btn, 0, 1)
        
        # Row 1: Directory (under Packages) & Link (under Adjudicator)
        grid_layout.addWidget(self.directory_btn, 1, 0)
        grid_layout.addWidget(self.link_bill_rate_btn, 1, 1)
        
        # Row 2: Clear (under Directory)
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.clicked.connect(self.clearSubcontractorRequested.emit)
        grid_layout.addWidget(self.clear_btn, 2, 0)
        
        btn_layout.addLayout(grid_layout)

        layout.addWidget(self.show_sub_cb)
        layout.addLayout(btn_layout)
        layout.addStretch()

    def get_state(self):
        return {
            "show_sub": self.show_sub_cb.isChecked()
        }

    def set_state(self, state):
        if "show_sub" in state:
            self.show_sub_cb.blockSignals(True)
            self.show_sub_cb.setChecked(state["show_sub"])
            self.show_sub_cb.blockSignals(False)
