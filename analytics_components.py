from PyQt6.QtWidgets import (QFrame, QVBoxLayout, QLabel, QGraphicsDropShadowEffect, QWidget, QSizePolicy, QHBoxLayout)
from PyQt6.QtGui import QColor, QPainter, QBrush, QPen, QFont, QFontMetrics, QLinearGradient
from PyQt6.QtCore import pyqtSignal, Qt, QRectF, QPointF, QSize

class SelectionFrame(QFrame):
    """A frame that emits a clicked signal, used for row selection in analytics tables."""
    clicked = pyqtSignal()
    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)

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

class ChartWidget(QWidget):
    """Base class for responsive custom charts."""
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.title = title
        self.data = [] # List of (label, value, color)
        self.setMinimumHeight(280)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

    def set_data(self, data):
        self.data = data
        self.update()

class DonutChart(ChartWidget):
    """A responsive donut chart with side legend."""
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = self.rect()
        total = sum(d[1] for d in self.data if d[1] > 0)
        
        if total == 0:
            painter.setPen(QColor("#999"))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "No Data")
            return

        chart_w = rect.width() * 0.55
        side = min(chart_w, rect.height()) - 60
        chart_rect = QRectF(30, (rect.height() - side) / 2, side, side)
        
        start_angle = 90 * 16
        for label, value, color in self.data:
            if value <= 0: continue
            span_angle = int((value / total) * 360 * 16)
            painter.setBrush(QBrush(QColor(color)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawPie(chart_rect, start_angle, span_angle)
            start_angle += span_angle

        hole_size = side * 0.72
        hole_rect = QRectF(chart_rect.center().x() - hole_size/2, chart_rect.center().y() - hole_size/2, hole_size, hole_size)
        painter.setBrush(QBrush(QColor("white")))
        painter.drawEllipse(hole_rect)
        
        painter.setPen(QPen(QColor("#333")))
        painter.setFont(QFont("Inter", 9, QFont.Weight.Bold))
        painter.drawText(hole_rect, Qt.AlignmentFlag.AlignCenter, "MIX")

        legend_x = int(chart_w + 10)
        legend_y = int((rect.height() - (len(self.data) * 25)) / 2)
        painter.setFont(QFont("Inter", 8, QFont.Weight.Medium))
        
        for label, value, color in self.data:
            if value < 0: continue
            painter.setBrush(QBrush(QColor(color)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(legend_x, legend_y, 12, 12, 3, 3)
            
            painter.setPen(QPen(QColor("#555")))
            pct = (value / total * 100) if total > 0 else 0
            label_text = f"{label} ({pct:.1f}%)"
            metrics = QFontMetrics(painter.font())
            elided = metrics.elidedText(label_text, Qt.TextElideMode.ElideRight, rect.width() - legend_x - 15)
            painter.drawText(legend_x + 20, legend_y + 10, elided)
            legend_y += 25

class ParetoBarChart(ChartWidget):
    """A horizontal bar chart with adaptive margins and elided text."""
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        if not self.data:
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "Awaiting Data...")
            return

        margin_left = min(220, rect.width() * 0.38)
        margin_right = 65
        max_val = max(d[1] for d in self.data if d[1] > 0)
        chart_top, bar_h, gap = 40, 18, 10
        painter.setFont(QFont("Inter", 8))
        metrics = QFontMetrics(painter.font())
        
        for i, (label, value, color) in enumerate(self.data):
            y = chart_top + i * (bar_h + gap)
            if y + bar_h > rect.height(): break
            elided_label = metrics.elidedText(label, Qt.TextElideMode.ElideRight, int(margin_left - 20))
            painter.setPen(QPen(QColor("#444")))
            painter.drawText(QRectF(10, y, margin_left - 20, bar_h), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, elided_label)
            
            track_w = rect.width() - margin_left - margin_right
            painter.setBrush(QBrush(QColor("#f2f2f2")))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(QRectF(margin_left, y, track_w, bar_h), 4, 4)
            
            val_w = (value / max_val * track_w) if max_val > 0 else 0
            grad = QLinearGradient(QPointF(margin_left, y), QPointF(margin_left + val_w, y))
            grad.setColorAt(0, QColor(color))
            grad.setColorAt(1, QColor(color).lighter(115))
            painter.setBrush(QBrush(grad))
            painter.drawRoundedRect(QRectF(margin_left, y, val_w, bar_h), 4, 4)
            
            painter.setPen(QPen(QColor("#1b5e20")))
            val_txt = f"{value/1000:,.1f}k" if value >= 1000 else f"{value:,.0f}"
            painter.drawText(QRectF(margin_left + val_w + 8, y, margin_right, bar_h), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, val_txt)

class WaterfallChart(ChartWidget):
    """Responsive Waterfall chart with label protection."""
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        if not self.data: return
        total_v = self.data[-1][1]
        if total_v <= 0: return
        margin_y, margin_x = 60, 60
        chart_h, chart_w = rect.height() - margin_y * 1.8, rect.width() - 2 * margin_x
        col_count = len(self.data)
        col_w, spacing = min(120, (chart_w / col_count) * 0.7), chart_w / col_count
        current_sum = 0
        painter.setFont(QFont("Inter", 8))
        for i, (label, val, color) in enumerate(self.data):
            center_x = margin_x + i * spacing + (spacing / 2)
            x_start = center_x - (col_w / 2)
            is_total = (i == 0 or i == col_count - 1)
            h = (val / total_v) * chart_h
            if is_total:
                y = margin_y + chart_h - h
                bar_rect = QRectF(x_start, y, col_w, h)
                if i == 0: current_sum = val
            else:
                start_h = (current_sum / total_v) * chart_h
                y = margin_y + chart_h - start_h - h
                bar_rect = QRectF(x_start, y, col_w, h)
                painter.setPen(QPen(QColor("#ccc"), 1, Qt.PenStyle.DashLine))
                painter.drawLine(int(x_start - (spacing - col_w)/2), int(margin_y + chart_h - start_h), int(x_start), int(margin_y + chart_h - start_h))
                current_sum += val
            grad = QLinearGradient(QPointF(x_start, y), QPointF(x_start, y + h))
            grad.setColorAt(0, QColor(color)); grad.setColorAt(1, QColor(color).darker(110))
            painter.setBrush(QBrush(grad)); painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(bar_rect, 4, 4)
            painter.setPen(QPen(QColor("#333")))
            painter.drawText(QRectF(x_start - 20, margin_y + chart_h + 10, col_w + 40, 20), Qt.AlignmentFlag.AlignCenter, label)
