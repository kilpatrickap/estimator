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
        self.currency_symbol = "$"
        self.setMinimumHeight(280)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

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
        pos_values = [d[1] for d in self.data if d[1] > 0]
        if not pos_values:
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "No Pricing Data")
            return
        max_val = max(pos_values)
        chart_top, bar_h, gap = 40, 18, 10
        painter.setFont(QFont("Inter", 8))
        metrics = QFontMetrics(painter.font())
        
        for i, (label, value, color) in enumerate(self.data):
            y = chart_top + i * (bar_h + gap)
            if y + bar_h > rect.height(): break
            elided_label = metrics.elidedText(label, Qt.TextElideMode.ElideRight, int(margin_left - 20))
            painter.setPen(QPen(QColor("#444")))
            painter.drawText(QRectF(10, y, margin_left - 20, bar_h), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, elided_label)
            
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
            
            painter.setPen(QPen(QColor("#1e293b")))
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
            
            # Draw Bar
            grad = QLinearGradient(QPointF(x_start, y), QPointF(x_start, y + h))
            grad.setColorAt(0, QColor(color)); grad.setColorAt(1, QColor(color).darker(110))
            painter.setBrush(QBrush(grad)); painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(bar_rect, 4, 4)
            
            # Bottom Label
            painter.setPen(QPen(QColor("#333")))
            painter.setFont(QFont("Inter", 8, QFont.Weight.Bold))
            painter.drawText(QRectF(x_start - 20, margin_y + chart_h + 10, col_w + 40, 20), Qt.AlignmentFlag.AlignCenter, label)
            
            # Top Value Figure
            painter.setPen(QPen(QColor("#1e293b")))
            painter.setFont(QFont("Inter", 8, QFont.Weight.Bold))
            val_txt = f"{self.currency_symbol}{val:,.2f}"
            painter.drawText(QRectF(x_start - 60, y - 22, col_w + 120, 20), Qt.AlignmentFlag.AlignCenter, val_txt)

class TrendLineChart(ChartWidget):
    """A responsive line chart showing historical trends across projects."""
    def __init__(self, title, parent=None):
        super().__init__(title, parent)
        self.points = [] # List of (label, value)
        self.setMouseTracking(True)
        self.hover_idx = -1

    def set_data(self, data):
        self.points = data
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        
        if not self.points:
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "Select an item to view trend")
            return

        margin_y, margin_x = 50, 60
        chart_h = rect.height() - margin_y * 2
        chart_w = rect.width() - margin_x * 2
        
        vals = [p[1] for p in self.points]
        min_v, max_v = min(vals) * 0.9, max(vals) * 1.1
        if max_v == min_v: max_v += 1
        
        def to_y(v): return margin_y + chart_h - ((v - min_v) / (max_v - min_v) * chart_h)
        def to_x(i): return margin_x + (i * (chart_w / (len(self.points) - 1))) if len(self.points) > 1 else margin_x + chart_w / 2

        # 1. Draw Grid Lines & Y-Axis Labels
        for i in range(5):
            y = margin_y + (i * chart_h / 4)
            # Grid Line (Light Gray)
            painter.setPen(QPen(QColor("#e2e8f0"), 1))
            painter.drawLine(margin_x, int(y), margin_x + chart_w, int(y))
            
            # Y-Axis Label (Green)
            painter.setPen(QPen(QColor("#166534"), 1))
            painter.setFont(QFont("Inter", 8, QFont.Weight.Bold))
            val = max_v - (i * (max_v - min_v) / 4)
            painter.drawText(margin_x - 58, int(y + 5), f"{self.currency_symbol}{val:,.0f}")

        # 2. Draw Line
        path_pen = QPen(QColor("#2e7d32"), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(path_pen)
        
        for i in range(len(self.points) - 1):
            p1 = QPointF(to_x(i), to_y(self.points[i][1]))
            p2 = QPointF(to_x(i+1), to_y(self.points[i+1][1]))
            painter.drawLine(p1, p2)

        # 3. Draw Points
        for i, (label, val) in enumerate(self.points):
            px, py = to_x(i), to_y(val)
            
            # Area Fill under curve
            if i < len(self.points) - 1:
                next_val = self.points[i+1][1]
                nx, ny = to_x(i+1), to_y(next_val)
                poly = [QPointF(px, py), QPointF(nx, ny), QPointF(nx, margin_y + chart_h), QPointF(px, margin_y + chart_h)]
                grad = QLinearGradient(0, py, 0, margin_y + chart_h)
                grad.setColorAt(0, QColor(46, 125, 50, 40))
                grad.setColorAt(1, QColor(46, 125, 50, 0))
                painter.setBrush(grad)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawPolygon(poly)

            # Dot
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor("#1b5e20")))
            painter.drawEllipse(QPointF(px, py), 5, 5)
            
            # Highlight if hovered
            if i == self.hover_idx:
                painter.setBrush(QBrush(QColor(255, 255, 255, 200)))
                painter.setPen(QPen(QColor("#1b5e20"), 2))
                painter.drawEllipse(QPointF(px, py), 8, 8)

            # Label (Project Name)
            painter.setPen(QPen(QColor("#64748b")))
            painter.setFont(QFont("Inter", 7, QFont.Weight.Medium))
            metrics = QFontMetrics(painter.font())
            elided = metrics.elidedText(label, Qt.TextElideMode.ElideRight, 80)
            
            painter.save()
            painter.translate(px, margin_y + chart_h + 10)
            painter.rotate(45)
            painter.drawText(0, 0, elided)
            painter.restore()

    def mouseMoveEvent(self, event):
        pos = event.position()
        margin_x = 60
        chart_w = self.width() - margin_x * 2
        
        if not self.points: return
        
        spacing = chart_w / (len(self.points) - 1) if len(self.points) > 1 else chart_w
        idx = round((pos.x() - margin_x) / spacing)
        idx = max(0, min(idx, len(self.points) - 1))
        
        if idx != self.hover_idx:
            self.hover_idx = idx
            label, val = self.points[idx]
            self.setToolTip(f"Project: {label}\nRate: {self.currency_symbol}{val:,.2f}")
            self.update()
        super().mouseMoveEvent(event)
