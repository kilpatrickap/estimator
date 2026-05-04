import os
import sqlite3
import json
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QFrame, QGridLayout, QScrollArea, QSpacerItem, QSizePolicy)
from PyQt6.QtCore import Qt, QRectF, QPointF, QSize
from PyQt6.QtGui import QColor, QPainter, QBrush, QPen, QFont, QLinearGradient, QFontMetrics

from analytics_components import MetricCard, SelectionFrame
from pboq_logic import PBOQLogic

class MetricRow(QFrame):
    def __init__(self, name, bid, cost, margin, is_total=False, parent=None):
        super().__init__(parent)
        bg = "#f1f8e9" if is_total else "#ffffff"
        border = "#2e7d32" if is_total else "#e2e8f0"
        self.setStyleSheet(f"""
            QFrame {{ background-color: {bg}; border-radius: 8px; border: 1px solid {border}; }}
            QFrame:hover {{ background-color: #f8fafc; border: 1px solid #cbd5e1; }}
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 8, 15, 8)
        layout.setSpacing(15)

        # Name
        name_lbl = QLabel(name)
        weight = "800" if is_total else "600"
        name_lbl.setStyleSheet(f"font-family: 'Inter'; font-weight: {weight}; color: #1e293b; font-size: 13px;")
        layout.addWidget(name_lbl, 5)

        # Bid Pill
        bid_pill = QFrame()
        bid_pill.setStyleSheet("background-color: #f0fdf4; border-radius: 4px; padding: 2px 8px;")
        bp_layout = QHBoxLayout(bid_pill)
        bp_layout.setContentsMargins(5, 2, 5, 2)
        bid_val = QLabel(f"$ {bid:,.2f}")
        bid_val.setStyleSheet("font-family: 'Consolas'; font-weight: 700; color: #166534; font-size: 13px;")
        bp_layout.addWidget(bid_val)
        layout.addWidget(bid_pill, 2)

        # Cost Pill
        cost_pill = QFrame()
        cost_pill.setStyleSheet("background-color: #eff6ff; border-radius: 4px; padding: 2px 8px;")
        cp_layout = QHBoxLayout(cost_pill)
        cp_layout.setContentsMargins(5, 2, 5, 2)
        cost_val = QLabel(f"$ {cost:,.2f}")
        cost_val.setStyleSheet("font-family: 'Consolas'; font-weight: 700; color: #1e40af; font-size: 13px;")
        cp_layout.addWidget(cost_val)
        layout.addWidget(cost_pill, 2)

        # Margin Badge
        m_color = "#ea580c" if margin > 0 else "#991b1b"
        m_bg = "#fff7ed" if margin > 0 else "#fef2f2"
        margin_lbl = QLabel(f"{margin:.1f}% Margin")
        margin_lbl.setStyleSheet(f"background-color: {m_bg}; color: {m_color}; border-radius: 4px; padding: 2px 8px; font-weight: 800; font-size: 11px;")
        margin_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(margin_lbl, 2)

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
    """The 'CFO' Hub: Optimized and Responsive reporting with deep project integration."""
    def __init__(self, project_dir, parent=None):
        super().__init__(parent)
        self.project_dir = project_dir
        self.pboq_folder = os.path.join(self.project_dir, "Priced BOQs")
        self.pj_db_dir = os.path.join(self.project_dir, "Project Database")
        self.currency_symbol = "$" 
        self.overhead_rate = 0.0
        self.profit_rate = 0.0
        self._selected_row = None
        self._rate_cache = {} # Cache for rate buildup compositions
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
        
        # 1. Metric Cards
        metrics_parent = QWidget()
        self.metrics_flow = QHBoxLayout(metrics_parent)
        self.metrics_flow.setContentsMargins(0, 0, 0, 0)
        self.metrics_flow.setSpacing(20)
        
        self.card_total_bid = MetricCard("Total Bid Value", "0.00", "Gross amount to client", color="#1b5e20")
        self.card_total_cost = MetricCard("Total Net Cost", "0.00", "Base resource cost", color="#0277bd")
        self.card_margin = MetricCard("Profit Margin (%)", "0.00%", "Project profitability", color="#ef6c00")
        self.card_overhead = MetricCard("Overhead (%)", "0.00%", "Business operating cost", color="#546e7a")
        
        self.metrics_flow.addWidget(self.card_total_bid)
        self.metrics_flow.addWidget(self.card_total_cost)
        self.metrics_flow.addWidget(self.card_margin)
        self.metrics_flow.addWidget(self.card_overhead)
        self.metrics_flow.addStretch()
        self.content_layout.addWidget(metrics_parent)
        
        # 2. Charts Row
        charts_grid = QGridLayout()
        charts_grid.setSpacing(20)
        
        self.donut_chart = DonutChart("Resources")
        donut_frame = self._create_card_frame("Estimated Cost Breakdown (Deep Drill-down)", self.donut_chart)
        charts_grid.addWidget(donut_frame, 0, 0)
        
        self.pareto_chart = ParetoBarChart("Pareto")
        pareto_frame = self._create_card_frame("Pareto Analysis: Top 10 Value Drivers", self.pareto_chart)
        charts_grid.addWidget(pareto_frame, 0, 1)
        
        self.bridge_chart = WaterfallChart("Bridge")
        bridge_frame = self._create_card_frame("Net-to-Gross Financial Bridge", self.bridge_chart)
        charts_grid.addWidget(bridge_frame, 1, 0, 1, 2)
        
        self.content_layout.addLayout(charts_grid)
        
        # 3. Sectional Table
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

        # 4. Categorical Table
        cat_table_frame = QFrame()
        cat_table_frame.setStyleSheet("background-color: white; border-radius: 16px; border: 1px solid #e2e8f0;")
        cat_table_layout = QVBoxLayout(cat_table_frame)
        cat_table_layout.setContentsMargins(25, 25, 25, 25)
        
        cat_tbl_lbl = QLabel("<b style='font-size: 16px; font-family: Inter; color: #1e293b;'>Categorical Detail & Margin Analysis</b>")
        cat_table_layout.addWidget(cat_tbl_lbl)
        
        self.cat_table_scroll = QScrollArea()
        self.cat_table_scroll.setWidgetResizable(True)
        self.cat_table_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.cat_table_scroll.setMinimumHeight(400)
        self.cat_table_container = QWidget()
        self.cat_table_list = QVBoxLayout(self.cat_table_container)
        self.cat_table_list.setSpacing(5)
        self.cat_table_list.setContentsMargins(0, 10, 0, 10)
        self.cat_table_list.addStretch()
        self.cat_table_scroll.setWidget(self.cat_table_container)
        cat_table_layout.addWidget(self.cat_table_scroll)
        self.content_layout.addWidget(cat_table_frame)
        
        # Finish content widget
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

    def _load_project_settings(self):
        """Loads currency, overhead, and profit settings from the master database."""
        self.currency_symbol = "$" 
        self.overhead_rate = 0.0
        self.profit_rate = 0.0
        
        try:
            if os.path.exists(self.pj_db_dir):
                dbs = [f for f in os.listdir(self.pj_db_dir) if f.lower().endswith('.db') and "rates" not in f.lower()]
                if dbs:
                    db_path = os.path.join(self.pj_db_dir, dbs[0])
                    conn = sqlite3.connect(db_path)
                    cursor = conn.cursor()
                    
                    # 1. Load Currency
                    try:
                        cursor.execute("SELECT value FROM settings WHERE key='currency'")
                        row = cursor.fetchone()
                        if row:
                            curr_str = row[0]
                            if '(' in curr_str:
                                self.currency_symbol = curr_str.split('(')[-1].strip(')') + " "
                            else:
                                self.currency_symbol = curr_str + " "
                    except: pass
                    
                    # 2. Load Overhead & Profit rates
                    try:
                        cursor.execute("SELECT value FROM settings WHERE key='overhead'")
                        row = cursor.fetchone()
                        if row: self.overhead_rate = float(row[0])
                        
                        cursor.execute("SELECT value FROM settings WHERE key='profit'")
                        row = cursor.fetchone()
                        if row: self.profit_rate = float(row[0])
                    except: pass
                    
                    conn.close()
        except: pass

    def _get_rate_composition(self, rate_code):
        """Analyzes a rate buildup and returns (ratios, unit_net_total)."""
        if not rate_code: return None, 0.0
        if rate_code in self._rate_cache: return self._rate_cache[rate_code]

        try:
            dbs = [f for f in os.listdir(self.pj_db_dir) if f.lower().endswith('.db') and "rates" not in f.lower()]
            if not dbs: return None, 0.0
            
            db_path = os.path.join(self.pj_db_dir, dbs[0])
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Find the estimate ID, Net Total, and Category for this rate code
            cursor.execute("SELECT id, net_total, category FROM estimates WHERE rate_code = ?", (rate_code,))
            res = cursor.fetchone()
            if not res: 
                conn.close()
                return None, 0.0, None
            
            est_id, net_total, category = res
            net_total = float(net_total or 0.0)
            
            comp = {'Materials': 0.0, 'Labor': 0.0, 'Equipment': 0.0, 'Plant': 0.0, 'Indirect': 0.0, 'Subcontractors': 0.0}
            
            # Query all associated resources
            cursor.execute("""
                SELECT SUM(price * quantity) FROM estimate_materials 
                WHERE task_id IN (SELECT id FROM tasks WHERE estimate_id = ?)
            """, (est_id,))
            comp['Materials'] = cursor.fetchone()[0] or 0.0
            
            cursor.execute("""
                SELECT SUM(rate * hours) FROM estimate_labor 
                WHERE task_id IN (SELECT id FROM tasks WHERE estimate_id = ?)
            """, (est_id,))
            comp['Labor'] = cursor.fetchone()[0] or 0.0
            
            cursor.execute("""
                SELECT SUM(rate * hours) FROM estimate_equipment 
                WHERE task_id IN (SELECT id FROM tasks WHERE estimate_id = ?)
            """, (est_id,))
            comp['Equipment'] = cursor.fetchone()[0] or 0.0
            
            cursor.execute("""
                SELECT SUM(rate * hours) FROM estimate_plant 
                WHERE task_id IN (SELECT id FROM tasks WHERE estimate_id = ?)
            """, (est_id,))
            comp['Plant'] = cursor.fetchone()[0] or 0.0
            
            cursor.execute("""
                SELECT SUM(amount) FROM estimate_indirect_costs 
                WHERE task_id IN (SELECT id FROM tasks WHERE estimate_id = ?)
            """, (est_id,))
            comp['Indirect'] = cursor.fetchone()[0] or 0.0
            
            # Subcontractors in buildup (Join with quotes to get rates)
            try:
                cursor.execute("""
                    SELECT SUM(esr.quantity * sq.rate) 
                    FROM estimate_sub_rates esr
                    JOIN subcontractor_quotes sq ON esr.sub_rate_id = sq.id
                    WHERE esr.estimate_id = ?
                """, (est_id,))
                comp['Subcontractors'] = cursor.fetchone()[0] or 0.0
            except: pass
            
            total = sum(comp.values())
            ratios = None
            if total > 0:
                ratios = {k: v / total for k, v in comp.items()}
            
            self._rate_cache[rate_code] = (ratios, net_total, category)
            conn.close()
            return ratios, net_total, category
        except: pass
        return None, 0.0, None

    def _get_pboq_mapping(self, db_filename):
        """Loads column mapping from PBOQ States if available."""
        mapping_file = os.path.join(self.project_dir, "PBOQ States", db_filename + ".json")
        if os.path.exists(mapping_file):
            try:
                with open(mapping_file, 'r') as f:
                    data = json.load(f)
                    return data.get('mappings', {})
            except: pass
        return {}

    def refresh_data(self):
        self._load_project_settings()
        if not os.path.exists(self.pboq_folder): 
            return
        
        t_bid, t_cost = 0.0, 0.0
        dist = {'Materials': 0.0, 'Labor': 0.0, 'Equipment': 0.0, 'Plant': 0.0, 'Subcontractors': 0.0, 'Risk': 0.0}
        all_items, sections = [], []
        c_agg = {} # Categorical aggregate (Project Wide)

        files = [f for f in os.listdir(self.pboq_folder) if f.lower().endswith('.db')]

        for f in files:
                
            db_path = os.path.join(self.pboq_folder, f)
            mapping = self._get_pboq_mapping(f)
            
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info(pboq_items)")
                cols = [info[1] for info in cursor.fetchall()]
                
                b_idx = mapping.get('bill_amount')
                q_idx = mapping.get('qty')
                d_idx = mapping.get('desc')
                
                b_col = cols[b_idx + 1] if b_idx is not None and (b_idx + 1) < len(cols) else next((c for c in cols if c.lower() in ["bill amount", "billamount"]), None)
                q_col = cols[q_idx + 1] if q_idx is not None and (q_idx + 1) < len(cols) else next((c for c in cols if c.lower() in ["quantity", "qty"]), None)
                d_col = cols[d_idx + 1] if d_idx is not None and (d_idx + 1) < len(cols) else next((c for c in cols if c.lower() in ["description", "desc"]), None)
                
                if not b_col or not q_col: continue

                src_cols = {
                    'plug': next((c for c in cols if c.lower() in ["plugrate", "plug_rate"]), None),
                    'plug_code': next((c for c in cols if c.lower() in ["plugcode", "plug_code"]), None),
                    'plug_cat': next((c for c in cols if c.lower() in ["plugcategory", "plug_category"]), None),
                    'sub': next((c for c in cols if c.lower() in ["subbeerate", "sub_rate"]), None),
                    'gross': next((c for c in cols if c.lower() in ["grossrate", "gross_rate"]), None),
                    'rate_code': next((c for c in cols if c.lower() in ["rate code", "ratecode"]), None),
                    'prov': next((c for c in cols if c.lower() in ["provsum", "prov_sum"]), None),
                    'pc': next((c for c in cols if c.lower() in ["pcsum", "pc_sum"]), None),
                    'dw': next((c for c in cols if c.lower() in ["daywork"]), None)
                }
                
                query_parts = ["Sheet", f"\"{d_col}\"", f"\"{q_col}\"", f"\"{b_col}\""]
                for k in ['plug', 'plug_code', 'plug_cat', 'sub', 'gross', 'rate_code', 'prov', 'pc', 'dw']:
                    v = src_cols.get(k)
                    query_parts.append(f"\"{v}\"" if v else "0")
                
                query = f"SELECT {', '.join(query_parts)} FROM pboq_items"
                cursor.execute(query)
                rows = cursor.fetchall()
                s_agg = {} # Sectional aggregate (Per File)

                for r in rows:
                    sheet, desc, q, b, plug, p_code, p_cat, sub, gross, r_code, prov, pc, dw = r
                    desc_low = (desc or "").lower()
                    
                    if "collection" in desc_low or "summary" in desc_low:
                        continue
                        
                    qty_f, bill_f = self._to_float(q), self._to_float(b)
                    if bill_f == 0 and qty_f == 0: continue
                    
                    p_val, s_val, g_val, pr_val, pc_val, d_val = [self._to_float(x) for x in [plug, sub, gross, prov, pc, dw]]
                    
                    # 1. CORE FIX: Pricing Category based detection
                    # Check if the item is explicitly categorized as Preliminaries
                    is_prelim = (str(p_cat).lower() == "preliminaries") if p_cat else False
                    
                    active_code = p_code if p_code and str(p_code).strip() else r_code
                    ratios, master_net_cost, master_cat = self._get_rate_composition(active_code) if active_code else (None, 0.0, None)
                    
                    # Determine Final Category
                    category = "Uncategorized"
                    if is_prelim: category = "Preliminaries"
                    elif p_cat and str(p_cat).strip(): category = str(p_cat).strip()
                    elif master_cat and str(master_cat).strip(): category = str(master_cat).strip()
                    
                    # Determine the source unit cost. 
                    if master_net_cost > 0:
                        unit_cost = master_net_cost
                    else:
                        # Fallback to BOQ rates if no master link
                        if p_val > 0: unit_cost = p_val
                        elif s_val > 0: unit_cost = s_val
                        elif g_val > 0: unit_cost = g_val
                        elif d_val > 0: unit_cost = d_val
                        else: 
                            # If it's a prelim item with a bill amount but no rate, 
                            # treat it as a lump sum cost (Indirect)
                            unit_cost = bill_f if is_prelim and bill_f > 0 and qty_f <= 1 else 0.0
                    
                    # Ensure qty is at least 1 for lump sums in prelims
                    calc_qty = qty_f if qty_f > 0 else (1.0 if is_prelim and bill_f > 0 else 0.0)
                    item_cost = unit_cost * calc_qty
                    
                    # 2. Resource distribution
                    if is_prelim:
                        dist['Risk'] += item_cost # Preliminaries are Indirect Costs
                    elif ratios:
                        dist['Materials'] += item_cost * ratios.get('Materials', 0.0)
                        dist['Labor'] += item_cost * ratios.get('Labor', 0.0)
                        dist['Plant'] += item_cost * ratios.get('Plant', 0.0)
                        dist['Equipment'] += item_cost * ratios.get('Equipment', 0.0)
                        dist['Subcontractors'] += item_cost * ratios.get('Subcontractors', 0.0)
                        dist['Risk'] += item_cost * ratios.get('Indirect', 0.0)
                    else:
                        # Default categorizations
                        if p_val > 0: dist['Materials'] += item_cost
                        elif s_val > 0: dist['Subcontractors'] += item_cost
                        elif g_val > 0: dist['Labor'] += item_cost
                        elif d_val > 0: dist['Labor'] += item_cost
                        elif pr_val > 0 or pc_val > 0: dist['Risk'] += item_cost

                    t_bid += bill_f
                    t_cost += item_cost
                    all_items.append((desc or "Unnamed", bill_f))
                    if sheet not in s_agg: s_agg[sheet] = [0.0, 0.0]
                    s_agg[sheet][0] += bill_f
                    s_agg[sheet][1] += item_cost
                    
                    if category not in c_agg: c_agg[category] = [0.0, 0.0]
                    c_agg[category][0] += bill_f
                    c_agg[category][1] += item_cost
                    
                for s, v in s_agg.items():
                    sections.append({'name': f"{f.replace('.db','')} : {s}", 'bid': v[0], 'cost': v[1]})
                conn.close()
            except Exception as e:
                print(f"Error processing {f}: {e}")

        # Metrics
        self.card_total_bid.update_value(f"{self.currency_symbol}{t_bid:,.2f}")
        self.card_total_cost.update_value(f"{self.currency_symbol}{t_cost:,.2f}")
        
        # Calculate Overhead and Profit split
        markup_total = t_bid - t_cost
        
        # Calculate actual Overhead component
        # Overhead is calculated on Cost according to project standards
        overhead_amount = t_cost * (self.overhead_rate / 100)
        actual_overhead_pct = (overhead_amount / t_bid * 100) if t_bid > 0 else 0
        
        # Profit is the remaining spread
        profit_amount = markup_total - overhead_amount
        actual_profit_pct = (profit_amount / t_bid * 100) if t_bid > 0 else 0
        
        self.card_margin.update_value(f"{actual_profit_pct:.2f}%")
        self.card_overhead.update_value(f"{actual_overhead_pct:.2f}%")
        
        # Donut (Using exact ratios from buildups)
        self.donut_chart.set_data([
            ("Materials", dist['Materials'], "#2e7d32"),
            ("Labor", dist['Labor'], "#0277bd"),
            ("Plant/Equip", dist['Plant'] + dist['Equipment'], "#fbc02d"),
            ("Sub-Contract", dist['Subcontractors'], "#7e57c2"),
            ("Indirect", dist['Risk'], "#c62828")
        ])
        
        # Pareto
        top_10 = sorted(all_items, key=lambda x: x[1], reverse=True)[:10]
        self.pareto_chart.set_data([(d, v, "#43a047") for d, v in top_10])
        
        self.bridge_chart.set_data([
            ("Base Cost", t_cost, "#0277bd"),
            ("Overhead", overhead_amount, "#546e7a"),
            ("Profit", profit_amount, "#ef6c00"),
            ("Final Bid", t_bid, "#1b5e20")
        ])

        # 5. Populate Tables
        self._clear_table(self.table_list)
        sections.sort(key=lambda x: x['bid'], reverse=True)
        s_total_bid, s_total_cost = 0.0, 0.0
        for s in sections: 
            self._add_table_row(self.table_list, s)
            s_total_bid += s['bid']
            s_total_cost += s['cost']
        
        # Add Sectional Total Row
        if sections:
            self._add_table_row(self.table_list, {'name': 'TOTAL PROJECT SUMMARY', 'bid': s_total_bid, 'cost': s_total_cost}, is_total=True)
        
        self._clear_table(self.cat_table_list)
        cat_list = [{'name': k, 'bid': v[0], 'cost': v[1]} for k, v in c_agg.items()]
        cat_list.sort(key=lambda x: x['bid'], reverse=True)
        c_total_bid, c_total_cost = 0.0, 0.0
        for c in cat_list: 
            self._add_table_row(self.cat_table_list, c)
            c_total_bid += c['bid']
            c_total_cost += c['cost']

        # Add Categorical Total Row
        if cat_list:
            self._add_table_row(self.cat_table_list, {'name': 'TOTAL CATEGORICAL SUMMARY', 'bid': c_total_bid, 'cost': c_total_cost}, is_total=True)
        
    def _to_float(self, val):
        if not val: return 0.0
        if isinstance(val, (int, float)): return float(val)
        try: return float(str(val).replace(',', '').replace(' ', '').replace('₵','').replace('$','').strip())
        except: return 0.0

    def _clear_table(self, layout):
        while layout.count() > 1:
            it = layout.takeAt(0)
            if it.widget(): it.widget().deleteLater()

    def _add_table_row(self, layout, data, is_total=False):
        bid, cost = data.get('bid', 0.0), data.get('cost', 0.0)
        margin = ((bid - cost) / bid * 100) if bid > 0 else 0
        r = MetricRow(data.get('name', 'Unknown'), bid, cost, margin, is_total=is_total)
        layout.insertWidget(layout.count() - 1, r)

