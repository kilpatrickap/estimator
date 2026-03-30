from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QCheckBox, QPushButton
from PyQt6.QtCore import pyqtSignal

class ProvSumTool(QWidget):
    """Widget for managing Provisional Sum visibility and settings."""
    
    visibilityChanged = pyqtSignal(bool)
    stateChanged = pyqtSignal()
    clearProvRequested = pyqtSignal()
    linkBillProvRequested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        self.show_prov_cb = QCheckBox("Show Prov Sum and Prov Sum Code")
        self.show_prov_cb.toggled.connect(self.visibilityChanged.emit)
        self.show_prov_cb.toggled.connect(self.stateChanged.emit)
        
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.clicked.connect(self.clearProvRequested.emit)
        btn_layout.addWidget(self.clear_btn)

        self.link_bill_rate_btn = QPushButton("Link to Bill Rate")
        self.link_bill_rate_btn.clicked.connect(lambda: self.linkBillProvRequested.emit())
        btn_layout.addWidget(self.link_bill_rate_btn)
        
        layout.addWidget(self.show_prov_cb)
        layout.addLayout(btn_layout)
        layout.addStretch()

    def get_state(self):
        return {"show_prov": self.show_prov_cb.isChecked()}

    def set_state(self, state):
        if "show_prov" in state:
            self.show_prov_cb.blockSignals(True)
            self.show_prov_cb.setChecked(state["show_prov"])
            self.show_prov_cb.blockSignals(False)
