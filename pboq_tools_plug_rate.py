from PyQt6.QtWidgets import QWidget, QVBoxLayout, QCheckBox, QPushButton
from PyQt6.QtCore import pyqtSignal

class PlugRateTool(QWidget):
    """Widget for managing Plug Rate visibility and settings."""
    
    visibilityChanged = pyqtSignal(bool)
    stateChanged = pyqtSignal()
    clearPlugRequested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        self.show_plug_cb = QCheckBox("Show Plug Rate and Plug Code")
        self.show_plug_cb.toggled.connect(self.visibilityChanged.emit)
        self.show_plug_cb.toggled.connect(self.stateChanged.emit)
        
        self.clear_btn = QPushButton("Clear Plug Rate and Code")
        self.clear_btn.clicked.connect(self.clearPlugRequested.emit)
        
        layout.addWidget(self.show_plug_cb)
        layout.addWidget(self.clear_btn)
        layout.addStretch()

    def get_state(self):
        return {"show_plug": self.show_plug_cb.isChecked()}

    def set_state(self, state):
        if "show_plug" in state:
            self.show_plug_cb.blockSignals(True)
            self.show_plug_cb.setChecked(state["show_plug"])
            self.show_plug_cb.blockSignals(False)
