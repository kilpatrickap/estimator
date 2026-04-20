from PyQt6.QtWidgets import (QFrame, QVBoxLayout, QLabel, QGraphicsDropShadowEffect)
from PyQt6.QtGui import QColor

class MetricCard(QFrame):
    """A premium, styled card for displaying KPI headline metrics."""
    def __init__(self, title, value, subtext="", color="#2e7d32", parent=None):
        super().__init__(parent)
        self.setFixedSize(240, 110)
        self.setObjectName("MetricCard")
        
        # Enhanced Styling
        self.setStyleSheet(f"""
            QFrame#MetricCard {{
                background-color: white;
                border-radius: 12px;
                border: 1px solid #e0e0e0;
            }}
        """)
        
        # Shadow Effect
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(15)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 40))
        self.setGraphicsEffect(shadow)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(5)
        
        self.title_label = QLabel(title.upper())
        self.title_label.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 11px; letter-spacing: 1px;")
        
        self.value_label = QLabel(value)
        self.value_label.setStyleSheet("color: #212121; font-weight: 800; font-size: 20px;")
        self.value_label.setWordWrap(True)
        
        self.subtext_label = QLabel(subtext)
        self.subtext_label.setStyleSheet("color: #757575; font-size: 12px;")
        
        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)
        layout.addStretch()
        layout.addWidget(self.subtext_label)

    def update_value(self, value, subtext=None):
        self.value_label.setText(value)
        if subtext is not None:
            self.subtext_label.setText(subtext)
