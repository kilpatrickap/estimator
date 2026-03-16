from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox
from PyQt6.QtCore import Qt

class PBOQPricePane(QWidget):
    """The side panel for Price Tools in the PBOQ viewer."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self._init_ui()
        
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(10)
        
        # 1. Price Type Selection
        type_row = QHBoxLayout()
        type_label = QLabel("Price type :")
        type_label.setStyleSheet("font-weight: bold;")
        
        self.price_type_combo = QComboBox()
        self.price_type_combo.addItems([
            "Gross Rate", "Plugged Rate", "Subcontractor Rate", 
            "Prov Sum", "PC Sum", "Attendances", 
            "Dayworks", "Preliminaries"
        ])
        
        type_row.addWidget(type_label)
        type_row.addWidget(self.price_type_combo, stretch=1)
        layout.addLayout(type_row)
        
        # Add a separator line
        line = QWidget()
        line.setFixedHeight(1)
        line.setStyleSheet("background-color: #cccccc;")
        layout.addWidget(line)

        layout.addStretch()
