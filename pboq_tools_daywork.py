from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QCheckBox, QPushButton, QGroupBox, QFormLayout, QLineEdit
from PyQt6.QtCore import pyqtSignal

class DayworkTool(QWidget):
    """Widget for managing Daywork visibility and global percentage settings."""
    
    visibilityChanged = pyqtSignal(bool)
    stateChanged = pyqtSignal()
    clearDayworkRequested = pyqtSignal()
    linkBillDayworkRequested = pyqtSignal()
    updateCalculationsRequested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        self.show_dw_cb = QCheckBox("Show Daywork and Code")
        self.show_dw_cb.toggled.connect(self.visibilityChanged.emit)
        self.show_dw_cb.toggled.connect(self.stateChanged.emit)
        
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.clicked.connect(self.clearDayworkRequested.emit)
        btn_layout.addWidget(self.clear_btn)

        self.link_bill_rate_btn = QPushButton("Link Item to Bill Amount")
        self.link_bill_rate_btn.clicked.connect(lambda: self.linkBillDayworkRequested.emit())
        btn_layout.addWidget(self.link_bill_rate_btn)
        
        layout.addWidget(self.show_dw_cb)
        layout.addLayout(btn_layout)

        # Dayworks Group
        dw_group = QGroupBox("Dayworks")
        dw_layout = QFormLayout(dw_group)
        dw_layout.setContentsMargins(5, 5, 5, 5)
        dw_layout.setSpacing(5)

        self.mat_input = QLineEdit()
        self.mat_input.setPlaceholderText("15.00%")
        self.mat_input.editingFinished.connect(self._format_percentage_input)
        dw_layout.addRow("Materials (%): ", self.mat_input)

        self.lab_input = QLineEdit()
        self.lab_input.setPlaceholderText("10.00%")
        self.lab_input.editingFinished.connect(self._format_percentage_input)
        dw_layout.addRow("Labour (%): ", self.lab_input)

        self.plt_input = QLineEdit()
        self.plt_input.setPlaceholderText("5.00%")
        self.plt_input.editingFinished.connect(self._format_percentage_input)
        dw_layout.addRow("Plant (%): ", self.plt_input)

        self.update_btn = QPushButton("Update and Calculate")
        self.update_btn.clicked.connect(self.updateCalculationsRequested.emit)
        dw_layout.addRow(self.update_btn)

        layout.addWidget(dw_group)
        
        layout.addStretch()

    def _format_percentage_input(self):
        sender = self.sender()
        if not isinstance(sender, QLineEdit):
            return
        
        text = sender.text().strip()
        if not text:
            return
            
        # Extract numeric part
        clean_text = text.replace('(', '').replace(')', '').replace('%', '').strip()
        try:
            val = float(clean_text)
            sender.setText(f"{val:.2f}%")
            self.stateChanged.emit()
        except ValueError:
            pass

    def get_state(self):
        return {
            "show_dw": self.show_dw_cb.isChecked(),
            "mat_percent": self.mat_input.text(),
            "lab_percent": self.lab_input.text(),
            "plt_percent": self.plt_input.text()
        }

    def set_state(self, state):
        if "show_dw" in state:
            self.show_dw_cb.blockSignals(True)
            self.show_dw_cb.setChecked(state["show_dw"])
            self.show_dw_cb.blockSignals(False)
        
        if "mat_percent" in state:
            self.mat_input.setText(state["mat_percent"])
        if "lab_percent" in state:
            self.lab_input.setText(state["lab_percent"])
        if "plt_percent" in state:
            self.plt_input.setText(state["plt_percent"])
