from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter, QBrush, QColor, QLinearGradient, QPen, QFont
from PyQt6.QtCore import Qt, QRectF

class DashboardChart(QWidget):
    def __init__(self, data=None, parent=None):
        super().__init__(parent)
        self.data = data or [] # List of tuples (Label, Value)
        self.setMinimumHeight(200)
        self.setStyleSheet("background-color: white; border-radius: 10px; border: 1px solid #e0e0e0;")
        
    def set_data(self, data):
        self.data = data
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background
        painter.setBrush(QBrush(QColor("white")))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self.rect(), 10, 10)

        if not self.data:
            painter.setPen(QColor("#7f8c8d"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No Data Available")
            return

        # Dimensions
        margin = 30
        w = self.width() - 2 * margin
        h = self.height() - 2 * margin
        
        # Max value for scaling
        try:
            max_val = max(d[1] for d in self.data) * 1.2 # Add 20% headroom
        except ValueError:
            max_val = 100

        if max_val == 0: max_val = 100

        bar_width = w / len(self.data) * 0.6
        spacing = w / len(self.data) * 0.4
        
        # Draw Bars
        painter.setFont(QFont("Segoe UI", 8))
        
        for i, (label, value) in enumerate(self.data):
            x = margin + i * (bar_width + spacing) + spacing / 2
            bar_h = (value / max_val) * h
            y = margin + h - bar_h
            
            # Bar Gradient
            gradient = QLinearGradient(x, y, x, y + bar_h)
            gradient.setColorAt(0, QColor("#2e7d32")) # Dark Green
            gradient.setColorAt(1, QColor("#66bb6a")) # Light Green
            
            painter.setBrush(gradient)
            painter.setPen(Qt.PenStyle.NoPen)
            rect = QRectF(x, y, bar_width, bar_h)
            painter.drawRoundedRect(rect, 4, 4)
            
            # Value Label
            painter.setPen(QColor("#2c3e50"))
            painter.drawText(QRectF(x - 5, y - 20, bar_width + 10, 20), 
                           Qt.AlignmentFlag.AlignCenter, f"{value/1000:.1f}k" if value >= 1000 else str(int(value)))
            
            # X-Axis Label
            painter.setPen(QColor("#7f8c8d"))
            painter.drawText(QRectF(x - 10, margin + h + 5, bar_width + 20, 20), 
                           Qt.AlignmentFlag.AlignCenter, label)
            
        # Title
        painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        painter.setPen(QColor("#2c3e50"))
        painter.drawText(QRectF(margin, 5, w, 20), Qt.AlignmentFlag.AlignLeft, "Recent Estimate Values")
