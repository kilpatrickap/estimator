from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QCheckBox, QPushButton
from PyQt6.QtCore import pyqtSignal

class GrossRateTool(QWidget):
    """Widget for managing Gross Rate visibility and settings."""
    
    visibilityChanged = pyqtSignal(bool)
    stateChanged = pyqtSignal()
    priceSOPRequested = pyqtSignal(bool) # True for Price, False for Revert
    linkBillRateRequested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        self.show_gross_cb = QCheckBox("Show Gross Rate and Gross Code")
        self.show_gross_cb.toggled.connect(self.visibilityChanged.emit)
        self.show_gross_cb.toggled.connect(self.stateChanged.emit)
        
        layout.addWidget(self.show_gross_cb)
        
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        self.price_sop_btn = QPushButton("Price with SOP")
        self.price_sop_btn.clicked.connect(self._on_price_sop_clicked)
        btn_layout.addWidget(self.price_sop_btn)
        
        self.link_bill_rate_btn = QPushButton("Link to Bill Rate")
        self.link_bill_rate_btn.clicked.connect(lambda: self.linkBillRateRequested.emit())
        btn_layout.addWidget(self.link_bill_rate_btn)
        
        layout.addLayout(btn_layout)
        
        layout.addStretch()

    def _on_price_sop_clicked(self):
        if self.price_sop_btn.text() == "Price with SOP":
            self.price_sop_btn.setText("Revert Price")
            self.priceSOPRequested.emit(True)
        else:
            self.price_sop_btn.setText("Price with SOP")
            self.priceSOPRequested.emit(False)

    def get_state(self):
        return {"show_gross": self.show_gross_cb.isChecked()}

    def set_state(self, state):
        if "show_gross" in state:
            self.show_gross_cb.blockSignals(True)
            self.show_gross_cb.setChecked(state["show_gross"])
            self.show_gross_cb.blockSignals(False)
