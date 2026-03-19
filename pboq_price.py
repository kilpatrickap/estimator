from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox
from PyQt6.QtCore import Qt, pyqtSignal
from pboq_tools_gross_rate import GrossRateTool
from pboq_tools_plug_rate import PlugRateTool

class PBOQPricePane(QWidget):
    """The side panel for Price Tools in the PBOQ viewer."""
    
    stateChanged = pyqtSignal()
    rateVisibilityChanged = pyqtSignal(bool)
    priceSORRequested = pyqtSignal(bool)
    linkBillRateRequested = pyqtSignal()
    clearPlugRequested = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self._init_ui()
        
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # 1. Price Type Selection
        type_row = QHBoxLayout()
        type_label = QLabel("Price type :")
        type_label.setStyleSheet("font-weight: 600; font-size: 8pt;")
        
        self.price_type_combo = QComboBox()
        self.price_type_combo.addItems([
            "Gross Rate", "Plug Rate", "Subcontractor Rate", 
            "Prov Sum", "PC Sum", "Attendances", 
            "Dayworks", "Preliminaries"
        ])
        self.price_type_combo.currentIndexChanged.connect(self._on_type_changed)
        self.price_type_combo.currentIndexChanged.connect(self.stateChanged)
        
        type_row.addWidget(type_label)
        type_row.addWidget(self.price_type_combo, stretch=1)
        layout.addLayout(type_row)
        
        # Add a separator line
        line = QWidget()
        line.setFixedHeight(1)
        line.setStyleSheet("background-color: #cccccc;")
        layout.addWidget(line)

        # 2. Tool Container (Sub-widgets for specific price types)
        self.tool_stack = QWidget()
        self.stack_layout = QVBoxLayout(self.tool_stack)
        self.stack_layout.setContentsMargins(0, 0, 0, 0)
        
        self.gross_rate_tool = GrossRateTool()
        self.gross_rate_tool.visibilityChanged.connect(self.rateVisibilityChanged.emit)
        self.gross_rate_tool.stateChanged.connect(self.stateChanged.emit)
        self.gross_rate_tool.priceSORRequested.connect(self.priceSORRequested.emit)
        self.gross_rate_tool.linkBillRateRequested.connect(self.linkBillRateRequested.emit)
        self.stack_layout.addWidget(self.gross_rate_tool)

        self.plug_rate_tool = PlugRateTool()
        self.plug_rate_tool.visibilityChanged.connect(self.rateVisibilityChanged.emit)
        self.plug_rate_tool.stateChanged.connect(self.stateChanged.emit)
        self.plug_rate_tool.clearPlugRequested.connect(self.clearPlugRequested.emit)
        self.plug_rate_tool.linkBillRateRequested.connect(self.linkBillRateRequested.emit)
        self.stack_layout.addWidget(self.plug_rate_tool)
        
        # Apply Balanced Compact Stylesheet
        self.setStyleSheet("""
            QGroupBox {
                margin-top: 12px;
                padding-top: 4px;
                font-weight: 600;
                font-size: 8pt;
                border: 1px solid #ccc;
                border-radius: 4px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 10px;
                padding: 0 2px;
                top: 2px;
            }
            QLabel, QComboBox, QLineEdit, QPushButton, QCheckBox, QDoubleSpinBox {
                font-size: 8pt;
                margin: 0px;
                padding: 1px;
            }
            QPushButton {
                padding: 2px 5px;
            }
        """)

        layout.addWidget(self.tool_stack)
        layout.addStretch()
        
        # Initial visibility
        self._on_type_changed()

    def _on_type_changed(self):
        text = self.price_type_combo.currentText()
        self.gross_rate_tool.setVisible(text == "Gross Rate")
        self.plug_rate_tool.setVisible(text == "Plug Rate")
        
        # Emit visibility of current selection
        self.rateVisibilityChanged.emit(self.get_rate_visibility())

    def get_rate_visibility(self):
        text = self.price_type_combo.currentText()
        if text == "Gross Rate":
            return self.gross_rate_tool.show_gross_cb.isChecked()
        elif text == "Plug Rate":
            return self.plug_rate_tool.show_plug_cb.isChecked()
        return False

    def get_state(self):
        return {
            "price_type": self.price_type_combo.currentText(),
            "gross_tool": self.gross_rate_tool.get_state(),
            "plug_tool": self.plug_rate_tool.get_state()
        }

    def set_state(self, state):
        self.blockSignals(True)
        try:
            if "price_type" in state:
                idx = self.price_type_combo.findText(state["price_type"])
                if idx >= 0:
                    self.price_type_combo.setCurrentIndex(idx)
            
            if "gross_tool" in state:
                self.gross_rate_tool.set_state(state["gross_tool"])
            
            if "plug_tool" in state:
                self.plug_rate_tool.set_state(state["plug_tool"])
            
            self._on_type_changed()
        finally:
            self.blockSignals(False)
