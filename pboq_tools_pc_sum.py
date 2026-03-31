from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QCheckBox, QPushButton
from PyQt6.QtCore import pyqtSignal

class PCSumTool(QWidget):
    """Widget for managing PC Sum visibility and settings."""
    
    visibilityChanged = pyqtSignal(bool)
    stateChanged = pyqtSignal()
    clearPCRequested = pyqtSignal()
    linkBillPCRequested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        self.show_pc_cb = QCheckBox("Show PC Sum and PC Code")
        self.show_pc_cb.toggled.connect(self.visibilityChanged.emit)
        self.show_pc_cb.toggled.connect(self.stateChanged.emit)
        
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.clicked.connect(self.clearPCRequested.emit)
        btn_layout.addWidget(self.clear_btn)

        self.link_bill_rate_btn = QPushButton("Link Item to Bill Amount")
        self.link_bill_rate_btn.clicked.connect(lambda: self.linkBillPCRequested.emit())
        btn_layout.addWidget(self.link_bill_rate_btn)
        
        layout.addWidget(self.show_pc_cb)
        layout.addLayout(btn_layout)
        layout.addStretch()

    def get_state(self):
        return {"show_pc": self.show_pc_cb.isChecked()}

    def set_state(self, state):
        if "show_pc" in state:
            self.show_pc_cb.blockSignals(True)
            self.show_pc_cb.setChecked(state["show_pc"])
            self.show_pc_cb.blockSignals(False)
