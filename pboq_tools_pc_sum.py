from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QCheckBox, QPushButton, QGroupBox, QFormLayout, QLineEdit
from PyQt6.QtCore import pyqtSignal

class PCSumTool(QWidget):
    """Widget for managing PC Sum visibility and settings."""
    
    visibilityChanged = pyqtSignal(bool)
    stateChanged = pyqtSignal()
    clearPCRequested = pyqtSignal()
    linkBillPCRequested = pyqtSignal()
    updateCalculationsRequested = pyqtSignal()

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

        # Profit and Attendances Group
        pa_group = QGroupBox("Profit and Attendances")
        pa_layout = QFormLayout(pa_group)
        pa_layout.setContentsMargins(5, 5, 5, 5)
        pa_layout.setSpacing(5)

        self.profit_input = QLineEdit()
        self.profit_input.setPlaceholderText("1.00%")
        self.profit_input.editingFinished.connect(self._format_percentage_input)
        pa_layout.addRow("Profit (%): ", self.profit_input)

        self.gen_attendance_input = QLineEdit()
        self.gen_attendance_input.setPlaceholderText("1.00%")
        self.gen_attendance_input.editingFinished.connect(self._format_percentage_input)
        pa_layout.addRow("General Attendance (%): ", self.gen_attendance_input)

        self.spec_attendance_input = QLineEdit()
        self.spec_attendance_input.setPlaceholderText("1.00%")
        self.spec_attendance_input.editingFinished.connect(self._format_percentage_input)
        pa_layout.addRow("Special Attendance (%): ", self.spec_attendance_input)

        self.update_btn = QPushButton("Update and Calculate")
        self.update_btn.clicked.connect(self.updateCalculationsRequested.emit)
        pa_layout.addRow(self.update_btn)

        layout.addWidget(pa_group)
        
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
            "show_pc": self.show_pc_cb.isChecked(),
            "profit": self.profit_input.text(),
            "gen_attendance": self.gen_attendance_input.text(),
            "spec_attendance": self.spec_attendance_input.text()
        }

    def set_state(self, state):
        if "show_pc" in state:
            self.show_pc_cb.blockSignals(True)
            self.show_pc_cb.setChecked(state["show_pc"])
            self.show_pc_cb.blockSignals(False)
        
        if "profit" in state:
            self.profit_input.setText(state["profit"])
        if "gen_attendance" in state:
            self.gen_attendance_input.setText(state["gen_attendance"])
        if "spec_attendance" in state:
            self.spec_attendance_input.setText(state["spec_attendance"])

