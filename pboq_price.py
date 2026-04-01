from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox
from PyQt6.QtCore import Qt, pyqtSignal
from pboq_tools_gross_rate import GrossRateTool
from pboq_tools_plug_rate import PlugRateTool
from pboq_tools_prov_sum import ProvSumTool
from pboq_tools_pc_sum import PCSumTool
from pboq_tools_daywork import DayworkTool
from pboq_tools_subbee import SubcontractorTool

class PBOQPricePane(QWidget):
    """The side panel for Price Tools in the PBOQ viewer."""
    
    stateChanged = pyqtSignal()
    rateVisibilityChanged = pyqtSignal(bool)
    priceSORRequested = pyqtSignal(bool)
    linkBillRateRequested = pyqtSignal()
    clearPlugRequested = pyqtSignal()
    clearProvRequested = pyqtSignal()
    linkBillProvRequested = pyqtSignal()
    clearPCRequested = pyqtSignal()
    linkBillPCRequested = pyqtSignal()
    clearDayworkRequested = pyqtSignal()
    linkBillDayworkRequested = pyqtSignal()
    openAdjudicatorRequested = pyqtSignal()
    clearSubcontractorRequested = pyqtSignal()
    assignPackageRequested = pyqtSignal(str)
    managePackagesRequested = pyqtSignal()
    openDirectoryRequested = pyqtSignal()
    updatePCCalcRequested = pyqtSignal()
    updateDayworkCalcRequested = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self.setFixedWidth(290)
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
            "Prov Sum", "PC Sum", "Dayworks"
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
        self.plug_rate_tool.link_bill_rate_btn.clicked.connect(lambda: self.linkBillRateRequested.emit())
        self.stack_layout.addWidget(self.plug_rate_tool)
        
        self.prov_sum_tool = ProvSumTool()
        self.prov_sum_tool.visibilityChanged.connect(self.rateVisibilityChanged.emit)
        self.prov_sum_tool.stateChanged.connect(self.stateChanged.emit)
        self.prov_sum_tool.clearProvRequested.connect(self.clearProvRequested.emit)
        self.prov_sum_tool.linkBillProvRequested.connect(self.linkBillProvRequested.emit)
        self.stack_layout.addWidget(self.prov_sum_tool)
        
        self.pc_sum_tool = PCSumTool()
        self.pc_sum_tool.visibilityChanged.connect(self.rateVisibilityChanged.emit)
        self.pc_sum_tool.stateChanged.connect(self.stateChanged.emit)
        self.pc_sum_tool.clearPCRequested.connect(self.clearPCRequested.emit)
        self.pc_sum_tool.linkBillPCRequested.connect(self.linkBillPCRequested.emit)
        self.pc_sum_tool.updateCalculationsRequested.connect(self.updatePCCalcRequested.emit)
        self.stack_layout.addWidget(self.pc_sum_tool)

        self.dw_tool = DayworkTool()
        self.dw_tool.visibilityChanged.connect(self.rateVisibilityChanged.emit)
        self.dw_tool.stateChanged.connect(self.stateChanged.emit)
        self.dw_tool.clearDayworkRequested.connect(self.clearDayworkRequested.emit)
        self.dw_tool.linkBillDayworkRequested.connect(self.linkBillDayworkRequested.emit)
        self.dw_tool.updateCalculationsRequested.connect(self.updateDayworkCalcRequested.emit)
        self.stack_layout.addWidget(self.dw_tool)
        
        self.sub_tool = SubcontractorTool()
        self.sub_tool.visibilityChanged.connect(self.rateVisibilityChanged.emit)
        self.sub_tool.stateChanged.connect(self.stateChanged.emit)
        self.sub_tool.linkBillRateRequested.connect(self.linkBillRateRequested.emit)
        self.sub_tool.openAdjudicatorRequested.connect(self.openAdjudicatorRequested.emit)
        self.sub_tool.openDirectoryRequested.connect(self.openDirectoryRequested.emit)
        self.sub_tool.clearSubcontractorRequested.connect(self.clearSubcontractorRequested.emit)
        self.sub_tool.assignPackageRequested.connect(self.assignPackageRequested.emit)
        self.sub_tool.managePackagesRequested.connect(self.managePackagesRequested.emit)
        self.stack_layout.addWidget(self.sub_tool)
        
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
        self.prov_sum_tool.setVisible(text == "Prov Sum")
        self.pc_sum_tool.setVisible(text == "PC Sum")
        self.dw_tool.setVisible(text == "Dayworks")
        self.sub_tool.setVisible(text == "Subcontractor Rate")
        
        # Emit visibility of current selection
        self.rateVisibilityChanged.emit(self.get_rate_visibility())

    def get_rate_visibility(self):
        text = self.price_type_combo.currentText()
        if text == "Gross Rate":
            return self.gross_rate_tool.show_gross_cb.isChecked()
        elif text == "Plug Rate":
            return self.plug_rate_tool.show_plug_cb.isChecked()
        elif text == "Prov Sum":
            return self.prov_sum_tool.show_prov_cb.isChecked()
        elif text == "PC Sum":
            return self.pc_sum_tool.show_pc_cb.isChecked()
        elif text == "Dayworks":
            return self.dw_tool.show_dw_cb.isChecked()
        elif text == "Subcontractor Rate":
            return self.sub_tool.show_sub_cb.isChecked()
        return False

    def get_state(self):
        return {
            "price_type": self.price_type_combo.currentText(),
            "gross_tool": self.gross_rate_tool.get_state(),
            "plug_tool": self.plug_rate_tool.get_state(),
            "prov_tool": self.prov_sum_tool.get_state(),
            "pc_tool": self.pc_sum_tool.get_state(),
            "dw_tool": self.dw_tool.get_state(),
            "sub_tool": self.sub_tool.get_state()
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
            if "prov_tool" in state:
                self.prov_sum_tool.set_state(state["prov_tool"])
            if "pc_tool" in state:
                self.pc_sum_tool.set_state(state["pc_tool"])
            if "dw_tool" in state:
                self.dw_tool.set_state(state["dw_tool"])
            if "sub_tool" in state:
                self.sub_tool.set_state(state["sub_tool"])
            
            self._on_type_changed()
        finally:
            self.blockSignals(False)
