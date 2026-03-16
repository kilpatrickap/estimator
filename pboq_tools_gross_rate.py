from PyQt6.QtWidgets import QWidget, QVBoxLayout, QCheckBox
from PyQt6.QtCore import pyqtSignal

class GrossRateTool(QWidget):
    """Widget for managing Gross Rate visibility and settings."""
    
    visibilityChanged = pyqtSignal(bool)
    stateChanged = pyqtSignal()

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
        layout.addStretch()

    def get_state(self):
        return {"show_gross": self.show_gross_cb.isChecked()}

    def set_state(self, state):
        if "show_gross" in state:
            self.show_gross_cb.blockSignals(True)
            self.show_gross_cb.setChecked(state["show_gross"])
            self.show_gross_cb.blockSignals(False)
