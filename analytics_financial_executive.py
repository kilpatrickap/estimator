import os
import sqlite3
import json
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QFrame, QGridLayout, QScrollArea, QSpacerItem, QSizePolicy)
from PyQt6.QtCore import Qt, QRectF, QPointF, QSize
from PyQt6.QtGui import QColor, QPainter, QBrush, QPen, QFont, QLinearGradient, QFontMetrics

from analytics_components import MetricCard, SelectionFrame
from pboq_logic import PBOQLogic

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
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "No Cost Data")
            return

        # Split space: Left 60% for chart, Right 40% for legend
        chart_w = rect.width() * 0.55
        side = min(chart_w, rect.height()) - 60
        chart_rect = QRectF(30, (rect.height() - side) / 2, side, side)
        
        start_angle = 90 * 16 # Start at top
        for label, value, color in self.data:
            if value <= 0: continue
            span_angle = int((value / total) * 360 * 16)
            painter.setBrush(QBrush(QColor(color)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawPie(chart_rect, start_angle, span_angle)
            start_angle += span_angle

        # Donut hole
        hole_size = side * 0.72
        hole_rect = QRectF(chart_rect.center().x() - hole_size/2, chart_rect.center().y() - hole_size/2, hole_size, hole_size)
        painter.setBrush(QBrush(QColor("white")))
        painter.drawEllipse(hole_rect)
        
        # Center Text
        painter.setPen(QPen(QColor("#333")))
        painter.setFont(QFont("Outfit", 9, QFont.Weight.Bold))
        fm = QFontMetrics(painter.font())
        inner_text = "COST\nMIX"
        painter.drawText(hole_rect, Qt.AlignmentFlag.AlignCenter, inner_text)

        # Legend on Right
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
            
            # Smart Truncation for legend
            metrics = QFontMetrics(painter.font())
            avail_w = rect.width() - legend_x - 15
            elided = metrics.elidedText(label_text, Qt.TextElideMode.ElideRight, avail_w)
            
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

        # Adaptive Margin
        margin_left = min(220, rect.width() * 0.38)
        margin_right = 65
        
        max_val = max(d[1] for d in self.data if d[1] > 0)
        chart_top = 40
        bar_h = 18
        gap = 10
        
        painter.setFont(QFont("Inter", 8))
        metrics = QFontMetrics(painter.font())
        
        for i, (label, value, color) in enumerate(self.data):
            y = chart_top + i * (bar_h + gap)
            if y + bar_h > rect.height(): break
            
            # Elide label to fit margin
            elided_label = metrics.elidedText(label, Qt.TextElideMode.ElideRight, int(margin_left - 20))
            painter.setPen(QPen(QColor("#444")))
            painter.drawText(QRectF(10, y, margin_left - 20, bar_h), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, elided_label)
            
            # Track
            track_w = rect.width() - margin_left - margin_right
            painter.setBrush(QBrush(QColor("#f2f2f2")))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(QRectF(margin_left, y, track_w, bar_h), 4, 4)
            
            # Value Bar
            val_w = (value / max_val * track_w) if max_val > 0 else 0
            grad = QLinearGradient(QPointF(margin_left, y), QPointF(margin_left + val_w, y))
            grad.setColorAt(0, QColor(color))
            grad.setColorAt(1, QColor(color).lighter(115))
            painter.setBrush(QBrush(grad))
            painter.drawRoundedRect(QRectF(margin_left, y, val_w, bar_h), 4, 4)
            
            # Numeric Label
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

        margin_y = 60
        margin_x = 60
        chart_h = rect.height() - margin_y * 1.8
        chart_w = rect.width() - 2 * margin_x
        
        col_count = len(self.data)
        col_w = min(120, (chart_w / col_count) * 0.7)
        spacing = chart_w / col_count
        
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
                
                # Connector
                painter.setPen(QPen(QColor("#ccc"), 1, Qt.PenStyle.DashLine))
                painter.drawLine(int(x_start - (spacing - col_w)/2), int(margin_y + chart_h - start_h), int(x_start), int(margin_y + chart_h - start_h))
                
                current_sum += val

            # Draw Bar
            grad = QLinearGradient(QPointF(x_start, y), QPointF(x_start, y + h))
            grad.setColorAt(0, QColor(color))
            grad.setColorAt(1, QColor(color).darker(110))
            painter.setBrush(QBrush(grad))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(bar_rect, 5, 5)
            
            # Bottom Label
            painter.setPen(QPen(QColor("#444")))
            painter.setFont(QFont("Inter", 8, QFont.Weight.Bold))
            painter.drawText(QRectF(center_x - 40, margin_y + chart_h + 10, 80, 20), Qt.AlignmentFlag.AlignCenter, label)
            
            # Top Value
            val_txt = f"{val/1000:,.1f}k" if val >= 1000 else f"{val:,.0f}"
            painter.setFont(QFont("Inter", 8))
            painter.drawText(QRectF(center_x - 40, y - 22, 80, 20), Qt.AlignmentFlag.AlignCenter, val_txt)

class FinancialExecutiveAnalytic(QWidget):
    """The 'CFO' Hub: Optimized and Responsive reporting."""
    def __init__(self, project_dir, parent=None):
        super().__init__(parent)
        self.project_dir = project_dir
        self.pboq_folder = os.path.join(self.project_dir, "Priced BOQs")
        self.currency_symbol = "$" 
        self._selected_row = None
        self._init_ui()
        self.refresh_data()

    def _init_ui(self):
        # Use a main layout to house the scroll area
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setStyleSheet("background-color: #fcfcfc;")
        
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(25, 25, 25, 25)
        self.content_layout.setSpacing(25)
        
        # Header
        header_container = QVBoxLayout()
        header = QLabel("Financial & Executive Reporting")
        header.setStyleSheet("font-family: 'Outfit'; font-size: 26px; font-weight: 800; color: #1b5e20;")
        header_container.addWidget(header)
        line = QFrame()
        line.setFixedHeight(4)
        line.setFixedWidth(100)
        line.setStyleSheet("background-color: #43a047; border-radius: 2px;")
        header_container.addWidget(line)
        self.content_layout.addLayout(header_container)
        
        # 1. Metric Cards (Fluid Flow)
        metrics_parent = QWidget()
        self.metrics_flow = QHBoxLayout(metrics_parent)
        self.metrics_flow.setContentsMargins(0, 0, 0, 0)
        self.metrics_flow.setSpacing(20)
        
        self.card_total_bid = MetricCard("Total Bid Value", "0.00", "Gross amount to client", color="#1b5e20")
        self.card_total_cost = MetricCard("Total Net Cost", "0.00", "Base resource cost", color="#0277bd")
        self.card_margin = MetricCard("Profit Margin (%)", "0.00%", "Profitability index", color="#ef6c00")
        
        self.metrics_flow.addWidget(self.card_total_bid)
        self.metrics_flow.addWidget(self.card_total_cost)
        self.metrics_flow.addWidget(self.card_margin)
        self.metrics_flow.addStretch()
        self.content_layout.addWidget(metrics_parent)
        
        # 2. Charts Row (Responsive Grid)
        charts_grid = QGridLayout()
        charts_grid.setSpacing(20)
        
        # Resource Mix
        self.donut_chart = DonutChart("Resources")
        donut_frame = self._create_card_frame("Estimated Cost Breakdown", self.donut_chart)
        charts_grid.addWidget(donut_frame, 0, 0)
        
        # Pareto
        self.pareto_chart = ParetoBarChart("Pareto")
        pareto_frame = self._create_card_frame("Pareto Analysis: Top 10 Value Drivers", self.pareto_chart)
        charts_grid.addWidget(pareto_frame, 0, 1)
        
        # Bridge
        self.bridge_chart = WaterfallChart("Bridge")
        bridge_frame = self._create_card_frame("Net-to-Gross Financial Bridge", self.bridge_chart)
        charts_grid.addWidget(bridge_frame, 1, 0, 1, 2)
        
        self.content_layout.addLayout(charts_grid)
        
        # 3. Enhanced Sectional Table
        table_frame = QFrame()
        table_frame.setStyleSheet("background-color: white; border-radius: 16px; border: 1px solid #e2e8f0;")
        table_layout = QVBoxLayout(table_frame)
        table_layout.setContentsMargins(25, 25, 25, 25)
        
        tbl_lbl = QLabel("<b style='font-size: 16px; font-family: Inter; color: #1e293b;'>Sectional Detail & Margin Analysis</b>")
        table_layout.addWidget(tbl_lbl)
        
        self.table_scroll = QScrollArea()
        self.table_scroll.setWidgetResizable(True)
        self.table_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.table_scroll.setMinimumHeight(400)
        self.table_container = QWidget()
        self.table_list = QVBoxLayout(self.table_container)
        self.table_list.setSpacing(5)
        self.table_list.setContentsMargins(0, 10, 0, 10)
        self.table_list.addStretch()
        self.table_scroll.setWidget(self.table_container)
        table_layout.addWidget(self.table_scroll)
        
        self.content_layout.addWidget(table_frame)
        
        self.scroll_area.setWidget(self.content_widget)
        root_layout.addWidget(self.scroll_area)

    def _create_card_frame(self, title, chart):
        f = QFrame()
        f.setStyleSheet("background-color: white; border-radius: 16px; border: 1px solid #e2e8f0;")
        l = QVBoxLayout(f)
        l.setContentsMargins(20, 20, 20, 20)
        lbl = QLabel(f"<span style='font-family: Inter; font-weight: bold; color: #475569; font-size: 13px;'>{title}</span>")
        l.addWidget(lbl)
        l.addWidget(chart)
        return f

    def _load_currency(self):
        self.currency_symbol = "$" 
        try:
            pj_db_dir = os.path.join(self.project_dir, "Project Database")
            if os.path.exists(pj_db_dir):
                dbs = [f for f in os.listdir(pj_db_dir) if f.lower().endswith('.db')]
                if dbs:
                    db_path = os.path.join(pj_db_dir, dbs[0])
                    conn = sqlite3.connect(db_path)
                    cursor = conn.cursor()
                    cursor.execute("SELECT value FROM settings WHERE key='currency'")
                    row = cursor.fetchone()
                    if row:
                        val = row[0]
                        if '(' in val: self.currency_symbol = val.split('(')[-1].strip(')') + " "
                        else: self.currency_symbol = val + " "
                    conn.close()
        except: pass

    def refresh_data(self):
        self._load_currency()
        if not os.path.exists(self.pboq_folder): return
        
        t_bid, t_cost = 0.0, 0.0
        dist = {'Materials': 0.0, 'Labor': 0.0, 'Subcontractors': 0.0, 'Risk': 0.0}
        all_items, sections = [], []

        for f in os.listdir(self.pboq_folder):
            if f.lower().endswith('.db'):
                db_path = os.path.join(self.pboq_folder, f)
                try:
                    conn = sqlite3.connect(db_path)
                    cursor = conn.cursor()
                    cursor.execute("PRAGMA table_info(pboq_items)")
                    cols = [info[1] for info in cursor.fetchall()]
                    
                    b_col = next((c for c in cols if c.lower() in ["bill amount", "billamount"]), None)
                    q_col = next((c for c in cols if c.lower() in ["quantity", "qty"]), None)
                    d_col = next((c for c in cols if c.lower() in ["description", "desc"]), None)
                    if not b_col or not q_col: continue

                    sr = ["PlugRate", "SubbeeRate", "GrossRate", "ProvSum", "PCSum", "Daywork"]
                    query = f"SELECT Sheet, \"{d_col}\", \"{q_col}\", \"{b_col}\""
                    for s in sr: query += f", \"{s}\"" if s in cols else ", 0"
                    query += " FROM pboq_items"
                    
                    cursor.execute(query)
                    rows = cursor.fetchall()
                    s_agg = {}

                    for r in rows:
                        sheet, desc, q, b, plug, sub, gross, prov, pc, dw = r
                        qty_f, bill_f = self._to_float(q), self._to_float(b)
                        if bill_f == 0: continue
                        
                        item_cost = 0.0
                        p, s, g, pr, pc_val, d_val = [self._to_float(x) for x in [plug, sub, gross, prov, pc, dw]]
                        
                        if p > 0: 
                            item_cost = p * qty_f
                            dist['Materials'] += item_cost
                        elif s > 0:
                            item_cost = s * qty_f
                            dist['Subcontractors'] += item_cost
                        elif g > 0:
                            item_cost = g * qty_f
                            dist['Labor'] += item_cost
                        elif pr > 0 or pc_val > 0:
                            item_cost = (pr + pc_val) * qty_f
                            dist['Risk'] += item_cost
                        elif d_val > 0:
                            dist['Labor'] += (d_val * qty_f)

                        t_bid += bill_f
                        t_cost += item_cost
                        all_items.append((desc or "Unnamed", bill_f))
                        if sheet not in s_agg: s_agg[sheet] = [0.0, 0.0]
                        s_agg[sheet][0] += bill_f
                        s_agg[sheet][1] += item_cost
                        
                    for s, v in s_agg.items():
                        sections.append({'name': f"{f.replace('.db','')} : {s}", 'bid': v[0], 'cost': v[1]})
                    conn.close()
                except Exception: pass

        # Metrics
        self.card_total_bid.update_value(f"{self.currency_symbol}{t_bid:,.2f}")
        self.card_total_cost.update_value(f"{self.currency_symbol}{t_cost:,.2f}")
        m = ((t_bid - t_cost) / t_bid * 100) if t_bid > 0 else 0
        self.card_margin.update_value(f"{m:.2f}%")
        
        # Donut & Pareto
        self.donut_chart.set_data([
            ("Materials", dist['Materials'], "#2e7d32"),
            ("Labor", dist['Labor'], "#0277bd"),
            ("Sub-Contract", dist['Subcontractors'], "#7e57c2"),
            ("Risk", dist['Risk'], "#c62828")
        ])
        top_10 = sorted(all_items, key=lambda x: x[1], reverse=True)[:10]
        self.pareto_chart.set_data([(d, v, "#43a047") for d, v in top_10])
        
        # Bridge
        self.bridge_chart.set_data([
            ("Base Cost", t_cost, "#0277bd"),
            ("Markup", t_bid - t_cost, "#ef6c00"),
            ("Final Bid", t_bid, "#1b5e20")
        ])
        
        self._clear_table()
        for s in sections: self._add_table_row(s)

    def _to_float(self, val):
        if not val: return 0.0
        try: return float(str(val).replace(',', '').replace(' ', '').replace('₵','').replace('$','').strip())
        except: return 0.0

    def _clear_table(self):
        while self.table_list.count() > 1:
            it = self.table_list.takeAt(0)
            if it.widget(): it.widget().deleteLater()

    def _add_table_row(self, data):
        row = SelectionFrame()
        row.setObjectName("TableRow")
        row.setStyleSheet("""
            QFrame#TableRow { 
                background-color: transparent; 
                border-radius: 6px; 
                border: 1px solid transparent; 
            }
            QFrame#TableRow:hover { 
                background-color: #f5f5f5; 
            }
            QFrame#TableRow[selected="true"] {
                background-color: #e8f5e9;
                border: 1px solid #2e7d32;
            }
        """)
        row.setProperty("selected", "false")
        
        l = QHBoxLayout(row)
        l.setContentsMargins(10, 4, 10, 4)
        l.setSpacing(12)
        
        # 1. Name Container (Pill Style)
        name_container = QFrame()
        name_container.setStyleSheet("background-color: #f1f3f4; border-radius: 4px; padding: 2px;")
        name_container.setMinimumWidth(500)
        nc_layout = QHBoxLayout(name_container)
        nc_layout.setContentsMargins(8, 2, 8, 2)
        
        name = QLabel(data['name'])
        name.setStyleSheet("font-weight: 600; color: #3c4043; font-size: 8.5pt; border: none; background: transparent;")
        nc_layout.addWidget(name)
        
        # 2. Bid Pill
        bid_container = QFrame()
        bid_container.setStyleSheet("background-color: #e8f5e9; border-radius: 4px; min-width: 160px;")
        bc_layout = QHBoxLayout(bid_container)
        bc_layout.setContentsMargins(8, 2, 8, 2)
        
        bid = QLabel(f"{self.currency_symbol}{data['bid']:,.2f}")
        bid.setStyleSheet("font-weight: 700; color: #1b5e20; font-size: 9pt; font-family: 'Consolas'; border: none;")
        bc_layout.addWidget(bid)
        
        # 3. Cost Pill
        cost_container = QFrame()
        cost_container.setStyleSheet("background-color: #e3f2fd; border-radius: 4px; min-width: 160px;")
        cc_layout = QHBoxLayout(cost_container)
        cc_layout.setContentsMargins(8, 2, 8, 2)
        
        cost = QLabel(f"{self.currency_symbol}{data['cost']:,.2f}")
        cost.setStyleSheet("font-weight: 700; color: #0277bd; font-size: 9pt; font-family: 'Consolas'; border: none;")
        cc_layout.addWidget(cost)
        
        # 4. Margin Pill
        mv = ((data['bid'] - data['cost']) / data['bid'] * 100) if data['bid'] > 0 else 0
        c_bg = "#f1f8e9" if mv > 15 else ("#fff8e1" if mv > 5 else "#ffebee")
        c_fg = "#2e7d32" if mv > 15 else ("#f57f17" if mv > 5 else "#c62828")
        
        margin_container = QFrame()
        margin_container.setStyleSheet(f"background-color: {c_bg}; border-radius: 4px; min-width: 100px;")
        mc_layout = QHBoxLayout(margin_container)
        mc_layout.setContentsMargins(8, 2, 8, 2)
        
        margin = QLabel(f"{mv:.1f}% Margin")
        margin.setStyleSheet(f"font-weight: 800; color: {c_fg}; font-size: 8.5pt; font-family: 'Inter'; border: none;")
        margin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mc_layout.addWidget(margin)
        
        l.addWidget(name_container, 6)
        l.addWidget(bid_container, 2)
        l.addWidget(cost_container, 2)
        l.addWidget(margin_container, 1)
        l.addStretch(1)
        
        def on_click():
            if self._selected_row:
                self._selected_row.setProperty("selected", "false")
                self._selected_row.style().unpolish(self._selected_row)
                self._selected_row.style().polish(self._selected_row)
            
            row.setProperty("selected", "true")
            row.style().unpolish(row)
            row.style().polish(row)
            self._selected_row = row
            
        row.clicked.connect(on_click)
        
        self.table_list.insertWidget(self.table_list.count() - 1, row)
