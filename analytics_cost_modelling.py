# analytics_cost_modelling.py

import os
import sqlite3
import json
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QFrame, QGridLayout, QScrollArea, QGraphicsDropShadowEffect,
                             QPushButton, QComboBox, QDoubleSpinBox, QSpinBox, QSlider, 
                             QSizePolicy, QSpacerItem, QMessageBox)
from PyQt6.QtCore import Qt, QRectF, QPointF, QSize, QUrl
from PyQt6.QtGui import QColor, QPainter, QBrush, QPen, QFont, QLinearGradient, QFontMetrics, QDesktopServices

from analytics_components import get_project_currency_symbol, MetricCard

class GfaSpinBox(QSpinBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSuffix(" m²")
        
    def setText(self, text):
        try:
            val_str = text.replace(" m²", "").replace(",", "").replace(" ", "").strip()
            self.setValue(int(val_str))
        except Exception:
            pass

class BenchmarkingRangeChart(QWidget):
    """
    A custom-painted visual gauge that places the calculated cost/m² rate 
    on a comparative horizontal spectrum representing typical industry standards.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(150)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        self.simulated_rate = 0.0
        self.actual_rate = 0.0
        self.min_normal = 500.0
        self.max_normal = 1200.0
        self.currency_symbol = "$"

    def set_rates(self, simulated_rate, actual_rate, min_normal, max_normal, currency_symbol="$"):
        self.simulated_rate = simulated_rate
        self.actual_rate = actual_rate
        self.min_normal = min_normal
        self.max_normal = max_normal
        self.currency_symbol = currency_symbol
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = self.rect()
        w = rect.width()
        h = rect.height()
        
        # Margins
        margin_x = 40
        margin_y = 50
        chart_w = w - 2 * margin_x
        bar_h = 24
        bar_y = h / 2 - bar_h / 2
        
        # Calculate range bounds
        # Let's map a wider window around normal limits: [0.5 * min_normal, 1.8 * max_normal]
        scale_min = self.min_normal * 0.5
        scale_max = self.max_normal * 1.8
        if scale_max == scale_min:
            scale_max += 100.0
            
        def to_x(val):
            ratio = (val - scale_min) / (scale_max - scale_min)
            ratio = max(0.0, min(1.0, ratio))
            return margin_x + ratio * chart_w

        # Draw the spectrum bar segments
        x_start = to_x(scale_min)
        x_min_norm = to_x(self.min_normal)
        x_max_norm = to_x(self.max_normal)
        x_end = to_x(scale_max)
        
        # Segment 1: Low-Cost / Economical / High Risk (Yellow/Orange to Green)
        grad_low = QLinearGradient(QPointF(x_start, bar_y), QPointF(x_min_norm - 2, bar_y))
        grad_low.setColorAt(0, QColor("#ef6c00")) # High variance / Risk
        grad_low.setColorAt(1, QColor("#81c784")) # Competitively low cost
        painter.setBrush(QBrush(grad_low))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(QRectF(x_start, bar_y, x_min_norm - x_start - 2, bar_h), 6, 6)
        
        # Segment 2: Optimal / Competitive Budget Range (Green)
        grad_opt = QLinearGradient(QPointF(x_min_norm + 2, bar_y), QPointF(x_max_norm - 2, bar_y))
        grad_opt.setColorAt(0, QColor("#81c784"))
        grad_opt.setColorAt(0.5, QColor("#4caf50"))
        grad_opt.setColorAt(1, QColor("#81c784"))
        painter.setBrush(QBrush(grad_opt))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(QRectF(x_min_norm + 2, bar_y, x_max_norm - x_min_norm - 4, bar_h), 6, 6)
        
        # Segment 3: Premium / High Spec Range (Green to Red)
        grad_high = QLinearGradient(QPointF(x_max_norm + 2, bar_y), QPointF(x_end, bar_y))
        grad_high.setColorAt(0, QColor("#81c784"))
        grad_high.setColorAt(0.6, QColor("#e53935")) # Very high budget
        grad_high.setColorAt(1, QColor("#b71c1c")) # Extreme/Luxury
        painter.setBrush(QBrush(grad_high))
        painter.drawRoundedRect(QRectF(x_max_norm + 2, bar_y, x_end - x_max_norm - 2, bar_h), 6, 6)

        # Draw segment boundaries & division text
        painter.setFont(QFont("Inter", 8, QFont.Weight.Medium))
        painter.setPen(QPen(QColor("#64748b")))
        
        # Draw min/max markers below the bar
        painter.drawText(QRectF(x_min_norm - 60, bar_y + bar_h + 8, 120, 30), 
                         Qt.AlignmentFlag.AlignCenter, 
                         f"Min Norm\n{self.currency_symbol}{self.min_normal:,.0f}")
        painter.drawText(QRectF(x_max_norm - 60, bar_y + bar_h + 8, 120, 30), 
                         Qt.AlignmentFlag.AlignCenter, 
                         f"Max Norm\n{self.currency_symbol}{self.max_normal:,.0f}")

        # Draw scale bounds
        painter.setFont(QFont("Inter", 8, QFont.Weight.Medium))
        painter.drawText(QRectF(x_start - 30, bar_y + bar_h + 8, 60, 30), 
                         Qt.AlignmentFlag.AlignCenter, 
                         f"{self.currency_symbol}{scale_min:,.0f}")
        painter.drawText(QRectF(x_end - 30, bar_y + bar_h + 8, 60, 30), 
                         Qt.AlignmentFlag.AlignCenter, 
                         f"{self.currency_symbol}{scale_max:,.0f}")

        # Draw simulated rate indicator (top of bar)
        if self.simulated_rate > 0:
            xs = to_x(self.simulated_rate)
            # Draw interactive estimator pin
            pin_color = QColor("#1b5e20")
            painter.setPen(QPen(pin_color, 2))
            painter.drawLine(QPointF(xs, bar_y - 2), QPointF(xs, bar_y + bar_h + 2))
            
            # Draw pointer arrow
            poly = [QPointF(xs, bar_y - 2), QPointF(xs - 6, bar_y - 10), QPointF(xs + 6, bar_y - 10)]
            painter.setBrush(QBrush(pin_color))
            painter.drawPolygon(poly)
            
            # Label
            painter.setFont(QFont("Inter", 8, QFont.Weight.Bold))
            painter.setPen(QPen(pin_color))
            lbl_w = 200
            lbl_x = xs - lbl_w / 2
            lbl_x = max(8.0, min(float(w - lbl_w - 8), lbl_x))
            painter.drawText(QRectF(lbl_x, bar_y - 28, lbl_w, 18), 
                             Qt.AlignmentFlag.AlignCenter, 
                             f"SIMULATED: {self.currency_symbol}{self.simulated_rate:,.2f}/m²")

        # Draw actual project rate indicator (bottom of bar)
        if self.actual_rate > 0:
            xa = to_x(self.actual_rate)
            # Draw actual project pin
            act_color = QColor("#1e40af") # Premium Blue
            painter.setPen(QPen(act_color, 2))
            painter.drawLine(QPointF(xa, bar_y - 2), QPointF(xa, bar_y + bar_h + 2))
            
            # Draw pointer arrow pointing upwards from bottom
            poly_act = [QPointF(xa, bar_y + bar_h + 2), QPointF(xa - 6, bar_y + bar_h + 10), QPointF(xa + 6, bar_y + bar_h + 10)]
            painter.setBrush(QBrush(act_color))
            painter.drawPolygon(poly_act)
            
            # Label
            painter.setFont(QFont("Inter", 8, QFont.Weight.Bold))
            painter.setPen(QPen(act_color))
            lbl_w = 200
            lbl_x = xa - lbl_w / 2
            lbl_x = max(8.0, min(float(w - lbl_w - 8), lbl_x))
            painter.drawText(QRectF(lbl_x, bar_y + bar_h + 38, lbl_w, 18), 
                             Qt.AlignmentFlag.AlignCenter, 
                             f"ACTUAL: {self.currency_symbol}{self.actual_rate:,.2f}/m²")


class ParametricBreakdownChart(QWidget):
    """
    A custom-painted horizontal stacked bar chart showing the composition 
    of cost drivers contributing to the simulated Cost/m² rate.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(150)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.cost_drivers = [] # List of (label, amount, color)
        self.currency_symbol = "$"

    def set_data(self, cost_drivers, currency_symbol="$"):
        self.cost_drivers = cost_drivers
        self.currency_symbol = currency_symbol
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = self.rect()
        w = rect.width()
        h = rect.height()
        
        total = sum(d[1] for d in self.cost_drivers)
        if total <= 0:
            painter.setPen(QPen(QColor("#94a3b8")))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "No simulation data available")
            return
            
        margin_x = 40
        margin_y = 30
        bar_h = 32
        bar_w = w - 2 * margin_x
        bar_y = margin_y
        
        # Draw stacked bar as premium rounded pills with 4px gaps
        current_x = float(margin_x)
        active_drivers = [d for d in self.cost_drivers if d[1] > 0]
        
        for label, val, color in active_drivers:
            seg_w = (val / total) * bar_w
            
            # Adjust starting x and width to incorporate a clean 4px gap between pills
            draw_x = current_x + 2
            draw_w = max(2.0, seg_w - 4)
            
            grad = QLinearGradient(QPointF(draw_x, bar_y), QPointF(draw_x + draw_w, bar_y))
            grad.setColorAt(0, QColor(color))
            grad.setColorAt(1, QColor(color).lighter(110))
            
            painter.setBrush(QBrush(grad))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(QRectF(draw_x, bar_y, draw_w, bar_h), 6, 6)
            
            current_x += seg_w
        
        # Draw Legends & Driver Details
        legend_x = margin_x
        legend_y = bar_y + bar_h + 20
        col_w = bar_w / max(1, len(self.cost_drivers))
        
        painter.setFont(QFont("Inter", 8, QFont.Weight.Medium))
        for label, val, color in self.cost_drivers:
            if val < 0: continue
            pct = (val / total * 100) if total > 0 else 0
            
            # Indicator box
            painter.setBrush(QBrush(QColor(color)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(QRectF(legend_x, legend_y, 10, 10), 2, 2)
            
            # Labels
            painter.setPen(QPen(QColor("#1e293b")))
            painter.setFont(QFont("Inter", 8, QFont.Weight.Bold))
            painter.drawText(QPointF(legend_x + 16, legend_y + 9), f"{pct:.1f}%")
            
            painter.setPen(QPen(QColor("#64748b")))
            painter.setFont(QFont("Inter", 7, QFont.Weight.Medium))
            painter.drawText(QPointF(legend_x + 16, legend_y + 22), label)
            painter.drawText(QPointF(legend_x + 16, legend_y + 33), f"{self.currency_symbol}{val:,.1f}/m²")
            
            legend_x += col_w


class ParametricBenchmarkingAnalytic(QWidget):
    """
    Highly dynamic and premium analytic panel for Parametric Benchmarking (cost/m²).
    Contains:
      - Quick simulated rate engine based on local markets (Accra, Kumasi, etc.)
      - Real-time sliders/factors that adjust complexity, wet areas, and specifications
      - Live project total scanner that pulls base estimates and allows GFA benchmarks
      - Fully painted custom range gauges and stacked breakdown charts
      - Comprehensive QS informational panel that embeds formulas and guidelines
    """
    def __init__(self, project_dir, parent=None):
        super().__init__(parent)
        self.project_dir = project_dir
        self.pboq_folder = os.path.join(self.project_dir, "Priced BOQs")
        self.pj_db_dir = os.path.join(self.project_dir, "Project Database")
        self.currency_symbol = "$"
        self.actual_project_net = 0.0
        self._rate_cache = {}
        
        # Load Project Constants/Base Settings
        self._load_currency()
        self._scan_actual_project_cost()
        
        self._init_ui()
        self._load_state()
        self.refresh_calculations()

    def _load_currency(self):
        """Standardized currency symbol and code discovery."""
        from analytics_components import get_project_currency_info
        symbol, code = get_project_currency_info(self.project_dir)
        self.currency_symbol = symbol
        self.currency_code = code

    def _get_usd_to_active_exchange_rate(self):
        """
        Discovers the exchange rate from USD to the active currency.
        Queries the master project database's settings table for 'currency_conversion_history'.
        Sequential history transition traversal logic with standard market rate fallbacks.
        """
        from analytics_components import extract_currency_code
        if getattr(self, 'currency_code', 'USD') == "USD":
            return 1.0
            
        db_path = None
        try:
            if os.path.exists(self.pj_db_dir):
                dbs = [f for f in os.listdir(self.pj_db_dir) if f.lower().endswith('.db') and "rates" not in f.lower()]
                if dbs:
                    db_path = os.path.join(self.pj_db_dir, dbs[0])
        except Exception:
            pass
            
        if db_path and os.path.exists(db_path):
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT value FROM settings WHERE key='currency_conversion_history'")
                row = cursor.fetchone()
                conn.close()
                if row:
                    history = json.loads(row[0])
                    current_val = 1.0
                    tracked_currency = "USD"
                    
                    for h in history:
                        src = extract_currency_code(h.get('from', ''))
                        dst = extract_currency_code(h.get('to', ''))
                        val = float(h.get('rate', 1.0))
                        op = h.get('operator', '*')
                        
                        if src == tracked_currency:
                            if op == '*':
                                current_val = current_val * val
                            else:
                                current_val = current_val / val
                            tracked_currency = dst
                            
                    if tracked_currency == self.currency_code and current_val > 0:
                        return current_val
            except Exception:
                pass
                
        # Prevailing market conversion ratios fallback
        fallbacks = {
            "GHS": 15.0,
            "EUR": 0.92,
            "GBP": 0.78,
            "NGN": 1500.0,
            "ZAR": 18.0
        }
        return fallbacks.get(self.currency_code, 1.0)

    def _to_float(self, val):
        if not val: return 0.0
        if isinstance(val, (int, float)): return float(val)
        try: return float(str(val).replace(',', '').replace(' ', '').replace('₵','').replace('$','').strip())
        except: return 0.0

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

    def _get_rate_composition(self, rate_code):
        """Analyzes a rate buildup and returns (ratios, unit_net_total)."""
        if not rate_code: return None, 0.0
        if rate_code in self._rate_cache: return self._rate_cache[rate_code]

        try:
            if not os.path.exists(self.pj_db_dir): return None, 0.0, None
            dbs = [f for f in os.listdir(self.pj_db_dir) if f.lower().endswith('.db') and "rates" not in f.lower()]
            if not dbs: return None, 0.0, None
            
            db_path = os.path.join(self.pj_db_dir, dbs[0])
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Check if category column exists in estimates table
            cursor.execute("PRAGMA table_info(estimates)")
            cols = [col[1] for col in cursor.fetchall()]
            has_category = "category" in cols

            # Find the estimate ID, Net Total, and Category for this rate code
            if has_category:
                cursor.execute("SELECT id, net_total, category FROM estimates WHERE rate_code = ?", (rate_code,))
                res = cursor.fetchone()
                if not res: 
                    conn.close()
                    return None, 0.0, None
                est_id, net_total, category = res
            else:
                cursor.execute("SELECT id, net_total FROM estimates WHERE rate_code = ?", (rate_code,))
                res = cursor.fetchone()
                if not res: 
                    conn.close()
                    return None, 0.0, None
                est_id, net_total = res
                category = "Uncategorized"
            net_total = float(net_total or 0.0)
            
            comp = {'Materials': 0.0, 'Labor': 0.0, 'Equipment': 0.0, 'Plant': 0.0, 'Indirect': 0.0, 'Subcontractors': 0.0}
            
            # Query all associated resources
            try:
                cursor.execute("""
                    SELECT SUM(price * quantity) FROM estimate_materials 
                    WHERE task_id IN (SELECT id FROM tasks WHERE estimate_id = ?)
                """, (est_id,))
                comp['Materials'] = cursor.fetchone()[0] or 0.0
            except: pass
            
            try:
                cursor.execute("""
                    SELECT SUM(rate * hours) FROM estimate_labor 
                    WHERE task_id IN (SELECT id FROM tasks WHERE estimate_id = ?)
                """, (est_id,))
                comp['Labor'] = cursor.fetchone()[0] or 0.0
            except: pass
            
            try:
                cursor.execute("""
                    SELECT SUM(rate * hours) FROM estimate_equipment 
                    WHERE task_id IN (SELECT id FROM tasks WHERE estimate_id = ?)
                """, (est_id,))
                comp['Equipment'] = cursor.fetchone()[0] or 0.0
            except: pass
            
            try:
                cursor.execute("""
                    SELECT SUM(rate * hours) FROM estimate_plant 
                    WHERE task_id IN (SELECT id FROM tasks WHERE estimate_id = ?)
                """, (est_id,))
                comp['Plant'] = cursor.fetchone()[0] or 0.0
            except: pass
            
            try:
                cursor.execute("""
                    SELECT SUM(amount) FROM estimate_indirect_costs 
                    WHERE task_id IN (SELECT id FROM tasks WHERE estimate_id = ?)
                """, (est_id,))
                comp['Indirect'] = cursor.fetchone()[0] or 0.0
            except: pass
            
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

    def _scan_actual_project_cost(self):
        """
        Scans all database tables in priced BOQs folder to extract 
        the exact actual total cost for real-time benchmarking comparison.
        """
        self.actual_project_net = 0.0
        if not os.path.exists(self.pboq_folder): 
            return
            
        t_cost = 0.0
        files = [f for f in os.listdir(self.pboq_folder) if f.lower().endswith('.db')]
        
        # Retrieve overhead/profit factors
        overhead_rate = 0.0
        profit_rate = 0.0
        try:
            if os.path.exists(self.pj_db_dir):
                dbs = [f for f in os.listdir(self.pj_db_dir) if f.lower().endswith('.db') and "rates" not in f.lower()]
                if dbs:
                    db_path = os.path.join(self.pj_db_dir, dbs[0])
                    conn = sqlite3.connect(db_path)
                    cursor = conn.cursor()
                    try:
                        cursor.execute("SELECT value FROM settings WHERE key='overhead'")
                        row = cursor.fetchone()
                        if row: overhead_rate = float(row[0])
                        
                        cursor.execute("SELECT value FROM settings WHERE key='profit'")
                        row = cursor.fetchone()
                        if row: profit_rate = float(row[0])
                    except: pass
                    conn.close()
        except: pass
        
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
                    'dw': next((c for c in cols if c.lower() in ["daywork"]), None),
                    'sub_pkg': next((c for c in cols if c.lower() in ["sub_package", "subpackage", "subbeepackage"]), None),
                    'sub_name': next((c for c in cols if c.lower() in ["sub_name", "subname", "subbeename"]), None),
                    'sub_cat': next((c for c in cols if c.lower() in ["subbeecategory", "sub_category"]), None),
                    'prov_cat': next((c for c in cols if c.lower() in ["provsumcategory", "prov_sum_category"]), None),
                    'pc_cat': next((c for c in cols if c.lower() in ["pcsumcategory", "pc_sum_category"]), None)
                }
                
                query_parts = ["Sheet", f"\"{d_col}\"", f"\"{q_col}\"", f"\"{b_col}\""]
                for k in ['plug', 'plug_code', 'plug_cat', 'sub', 'gross', 'rate_code', 'prov', 'pc', 'dw', 'sub_pkg', 'sub_name', 'prov_cat', 'pc_cat', 'sub_cat']:
                    v = src_cols.get(k)
                    query_parts.append(f"\"{v}\"" if v else "''")
                
                query = f"SELECT {', '.join(query_parts)} FROM pboq_items"
                cursor.execute(query)
                rows = cursor.fetchall()

                for r in rows:
                    sheet, desc, q, b, plug, p_code, p_cat, sub, gross, r_code, prov, pc, dw, s_pkg, s_n, pr_cat, pc_c, s_cat = r
                    desc_low = (desc or "").lower()
                    
                    if "collection" in desc_low or "summary" in desc_low:
                        continue
                        
                    qty_f, bill_f = self._to_float(q), self._to_float(b)
                    if bill_f == 0 and qty_f == 0: continue
                    
                    p_val, s_val, g_val, pr_val, pc_val, d_val = [self._to_float(x) for x in [plug, sub, gross, prov, pc, dw]]
                    
                    is_prelim = (str(p_cat).lower() == "preliminaries" or "prelim" in desc_low) if p_cat or desc else False
                    is_fixed = (pr_val > 0 or pc_val > 0 or d_val > 0 or is_prelim)
                    
                    active_code = p_code if p_code and str(p_code).strip() else r_code
                    ratios, master_net_cost, master_cat = self._get_rate_composition(active_code) if active_code else (None, 0.0, None)
                    
                    # Determine source unit cost
                    if pr_val > 0: unit_cost = pr_val
                    elif pc_val > 0: unit_cost = pc_val
                    elif d_val > 0: unit_cost = d_val
                    elif master_net_cost > 0: unit_cost = master_net_cost
                    else:
                        if p_val > 0: unit_cost = p_val
                        elif s_val > 0: unit_cost = s_val
                        elif g_val > 0: unit_cost = g_val
                        else:
                            # Fallback for Prelims or items with only bill amounts
                            unit_cost = bill_f if (is_prelim or is_fixed) and bill_f > 0 and qty_f <= 1 else 0.0
                    
                    is_lump_sum = is_prelim or is_fixed
                    calc_qty = qty_f if qty_f > 0 else (1.0 if is_lump_sum and bill_f > 0 else 0.0)
                    item_cost = unit_cost * calc_qty
                    
                    t_cost += round(item_cost, 2)
                conn.close()
            except Exception as e:
                print(f"Error processing {f}: {e}")
                
        # Apply exact combined markup to get true project value
        overhead_amount = t_cost * (overhead_rate / 100.0)
        profit_amount = t_cost * (profit_rate / 100.0)
        self.actual_project_net = t_cost + overhead_amount + profit_amount

    def _init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        
        main_scroll = QScrollArea()
        main_scroll.setWidgetResizable(True)
        main_scroll.setFrameShape(QFrame.Shape.NoFrame)
        main_scroll.setStyleSheet("background-color: #fcfcfc;")
        
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(25, 25, 25, 25)
        content_layout.setSpacing(25)
        
        # 1. Header Area
        header_container = QVBoxLayout()
        header = QLabel("Cost Modelling (Cost/m²)")
        header.setStyleSheet("font-family: 'Outfit'; font-size: 26px; font-weight: 800; color: #1b5e20;")
        header_container.addWidget(header)
        line = QFrame()
        line.setFixedHeight(4)
        line.setFixedWidth(100)
        line.setStyleSheet("background-color: #43a047; border-radius: 2px;")
        header_container.addWidget(line)
        content_layout.addLayout(header_container)
        
        # 2. Main Analytics Content Grid
        main_grid = QGridLayout()
        main_grid.setSpacing(20)
        
        # Left Panel: Simulators and Inputs (40% Column Width)
        input_panel = QFrame()
        input_panel.setStyleSheet("background-color: white; border-radius: 16px; border: 1px solid #e2e8f0;")
        input_layout = QVBoxLayout(input_panel)
        input_layout.setContentsMargins(20, 20, 20, 20)
        input_layout.setSpacing(15)
        
        input_title = QLabel("Cost Model")
        input_title.setStyleSheet("font-family: 'Inter'; font-weight: 700; color: #1e293b; font-size: 15px;")
        input_layout.addWidget(input_title)
        
        # Gross Floor Area (GFA) input
        gfa_lbl_lay = QHBoxLayout()
        gfa_lbl = QLabel("Gross Floor Area (GFA):")
        gfa_lbl.setStyleSheet("font-weight: 600; color: #475569; font-size: 12px;")
        self.gfa_val_lbl = GfaSpinBox()
        self.gfa_val_lbl.setMinimum(10)
        self.gfa_val_lbl.setMaximum(1000000) # Support huge projects up to 1,000,000 m²
        self.gfa_val_lbl.setValue(150)
        self.gfa_val_lbl.setStyleSheet("""
            QSpinBox {
                font-weight: 800;
                color: #166534;
                font-size: 13px;
                font-family: 'Consolas';
                background: white;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 4px 8px;
                min-width: 100px;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                width: 16px;
                border-left: 1px solid #cbd5e1;
            }
        """)
        gfa_lbl_lay.addWidget(gfa_lbl)
        gfa_lbl_lay.addStretch()
        gfa_lbl_lay.addWidget(self.gfa_val_lbl)
        input_layout.addLayout(gfa_lbl_lay)
        
        self.gfa_slider = QSlider(Qt.Orientation.Horizontal)
        self.gfa_slider.setMinimum(10)
        self.gfa_slider.setMaximum(100000) # Increased slider upper range to 100,000 m²
        self.gfa_slider.setValue(150)
        self.gfa_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 6px;
                background: #e2e8f0;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #2e7d32;
                border: 2px solid #1b5e20;
                width: 16px;
                height: 16px;
                margin-top: -5px;
                border-radius: 8px;
            }
        """)
        self.gfa_slider.valueChanged.connect(self._on_gfa_slider_changed)
        self.gfa_val_lbl.valueChanged.connect(self._on_gfa_spin_changed)
        input_layout.addWidget(self.gfa_slider)
        
        # Building Type Dropdown
        type_lbl = QLabel("Building Type / Category:")
        type_lbl.setStyleSheet("font-weight: 600; color: #475569; font-size: 11px;")
        input_layout.addWidget(type_lbl)
        
        self.type_combo = QComboBox()
        self.type_combo.addItems([
            "Residential House",
            "Commercial Office",
            "Retail / Showroom",
            "Industrial / Warehouse",
            "Extension / Add-on"
        ])
        self.type_combo.currentIndexChanged.connect(self.refresh_calculations)
        self.type_combo.setStyleSheet("padding: 8px; border-radius: 6px; border: 1px solid #cbd5e1; background: white; font-family: 'Inter'; font-size: 11px;")
        input_layout.addWidget(self.type_combo)
        
        # Target Region Dropdown
        region_lbl = QLabel("Target Location / Region:")
        region_lbl.setStyleSheet("font-weight: 600; color: #475569; font-size: 11px;")
        input_layout.addWidget(region_lbl)
        
        self.region_combo = QComboBox()
        self.region_combo.addItems([
            "Greater Accra (Standard Rate 100%)",
            "Ashanti - Kumasi (Rate 90%)",
            "Western - Takoradi (Rate 95%)",
            "Eastern - Koforidua (Rate 85%)",
            "Northern - Tamale (Rate 80%)"
        ])
        self.region_combo.currentIndexChanged.connect(self.refresh_calculations)
        self.region_combo.setStyleSheet("padding: 8px; border-radius: 6px; border: 1px solid #cbd5e1; background: white; font-family: 'Inter'; font-size: 11px;")
        input_layout.addWidget(self.region_combo)
        
        # Specification Quality Selector
        spec_lbl = QLabel("Quality of Specification:")
        spec_lbl.setStyleSheet("font-weight: 600; color: #475569; font-size: 11px;")
        input_layout.addWidget(spec_lbl)
        
        self.spec_combo = QComboBox()
        self.spec_combo.addItems([
            "Standard Finishes (Basic)",
            "Medium Finishes (Modern Comfort)",
            "Premium Finishes (High Spec)",
            "High-End Luxury Finishes (Double Rate)"
        ])
        self.spec_combo.setCurrentIndex(1) # Default: Medium
        self.spec_combo.currentIndexChanged.connect(self.refresh_calculations)
        self.spec_combo.setStyleSheet("padding: 8px; border-radius: 6px; border: 1px solid #cbd5e1; background: white; font-family: 'Inter'; font-size: 11px;")
        input_layout.addWidget(self.spec_combo)
        
        # Building Complexity Factor
        comp_lbl_lay = QHBoxLayout()
        comp_lbl = QLabel("Building Footprint Complexity:")
        comp_lbl.setStyleSheet("font-weight: 600; color: #475569; font-size: 11px;")
        self.comp_val_lbl = QLabel("Moderate (1.15x)")
        self.comp_val_lbl.setStyleSheet("font-weight: 700; color: #1e293b; font-size: 11px;")
        comp_lbl_lay.addWidget(comp_lbl)
        comp_lbl_lay.addStretch()
        comp_lbl_lay.addWidget(self.comp_val_lbl)
        input_layout.addLayout(comp_lbl_lay)
        
        self.comp_combo = QComboBox()
        self.comp_combo.addItems([
            "Simple Footprint (Square / Rectangle)",
            "Moderate Complexity (Offset footprint)",
            "High Complexity (Multi-angled perimeters)"
        ])
        self.comp_combo.setCurrentIndex(1)
        self.comp_combo.currentIndexChanged.connect(self._on_complexity_changed)
        self.comp_combo.setStyleSheet("padding: 8px; border-radius: 6px; border: 1px solid #cbd5e1; background: white; font-family: 'Inter'; font-size: 11px;")
        input_layout.addWidget(self.comp_combo)
        
        # Wet Area Count Spinbox (Bathrooms, Kitchens)
        wet_lbl_lay = QHBoxLayout()
        wet_lbl = QLabel("Wet Areas count (Bathrooms/Kitchens):")
        wet_lbl.setStyleSheet("font-weight: 600; color: #475569; font-size: 11px;")
        wet_lbl_lay.addWidget(wet_lbl)
        
        self.wet_spin = QSpinBox()
        self.wet_spin.setMinimum(0)
        self.wet_spin.setMaximum(50)
        self.wet_spin.setValue(3)
        self.wet_spin.valueChanged.connect(self.refresh_calculations)
        self.wet_spin.setStyleSheet("padding: 5px; border-radius: 6px; border: 1px solid #cbd5e1; font-family: 'Consolas'; font-size: 11px;")
        wet_lbl_lay.addWidget(self.wet_spin)
        input_layout.addLayout(wet_lbl_lay)
        
        # Site Conditions Dropdown
        site_lbl = QLabel("Groundwork & Site Conditions:")
        site_lbl.setStyleSheet("font-weight: 600; color: #475569; font-size: 11px;")
        input_layout.addWidget(site_lbl)
        
        self.site_combo = QComboBox()
        self.site_combo.addItems([
            "Easy/Flat (Standard soil)",
            "Moderate (Difficult soil/slight slope)",
            "Hard/Steep (Heavy retaining walls required)"
        ])
        self.site_combo.currentIndexChanged.connect(self.refresh_calculations)
        self.site_combo.setStyleSheet("padding: 8px; border-radius: 6px; border: 1px solid #cbd5e1; background: white; font-family: 'Inter'; font-size: 11px;")
        input_layout.addWidget(self.site_combo)
        

        
        main_grid.addWidget(input_panel, 0, 0, 2, 1)
        
        # Right Panel Top: Dynamic KPI Cards (2 Columns)
        kpi_parent = QWidget()
        kpi_lay = QHBoxLayout(kpi_parent)
        kpi_lay.setContentsMargins(0, 0, 0, 0)
        kpi_lay.setSpacing(15)
        
        self.card_sim_rate = MetricCard("Simulated Cost / m²", "0.00", "Based on scenario settings", color="#2e7d32")
        self.card_sim_total = MetricCard("Simulated Total Cost", "0.00", "Base construction budget", color="#1b5e20")
        self.card_act_rate = MetricCard("Actual Project / m²", "N/A", "Priced BOQ rate", color="#1e40af")
        
        kpi_lay.addWidget(self.card_sim_rate)
        kpi_lay.addWidget(self.card_sim_total)
        kpi_lay.addWidget(self.card_act_rate)
        
        # Right Panel Bottom: Dynamic Custom Painted Graphical Charts
        charts_frame = QFrame()
        charts_frame.setStyleSheet("background-color: white; border-radius: 16px; border: 1px solid #e2e8f0;")
        charts_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        charts_lay = QVBoxLayout(charts_frame)
        charts_lay.setContentsMargins(20, 20, 20, 20)
        charts_lay.setSpacing(10)
        
        chart_sec_title = QLabel("Benchmarking Analysis & Cost Drivers")
        chart_sec_title.setStyleSheet("font-family: 'Inter'; font-weight: 700; color: #1e293b; font-size: 15px;")
        charts_lay.addWidget(chart_sec_title)
        
        # 1. Range Chart
        charts_lay.addWidget(QLabel("<b>Standard Comparative Benchmarking Scale:</b>", styleSheet="font-size: 11px; color: #64748b;"))
        self.range_chart = BenchmarkingRangeChart()
        charts_lay.addWidget(self.range_chart)
        
        # 2. Driver Breakdown Chart
        charts_lay.addWidget(QLabel("<b>Simulated Cost-Driver Breakdown ($/m²):</b>", styleSheet="font-size: 11px; color: #64748b; margin-top: 10px;"))
        self.breakdown_chart = ParametricBreakdownChart()
        charts_lay.addWidget(self.breakdown_chart)
        
        # Combine right elements into a vertical layout aligned top
        right_panel_lay = QVBoxLayout()
        right_panel_lay.setContentsMargins(0, 0, 0, 0)
        right_panel_lay.setSpacing(20)
        right_panel_lay.addWidget(kpi_parent)
        right_panel_lay.addWidget(charts_frame)
        
        main_grid.addLayout(right_panel_lay, 0, 1, 2, 1)
        content_layout.addLayout(main_grid)
        
        # 3. Informational & Educational Card Section (Formula Guide)
        # 3. Informational & Educational Card Section (Formula Guide)
        edu_card = QFrame()
        edu_card.setObjectName("edu_card")
        edu_card.setStyleSheet("""
            #edu_card {
                background-color: #f8fafc;
                border-radius: 12px;
                border: 1px solid #e2e8f0;
            }
            QLabel {
                border: none;
                background: transparent;
            }
        """)
        edu_layout = QVBoxLayout(edu_card)
        edu_layout.setContentsMargins(15, 12, 15, 12)
        edu_layout.setSpacing(10)
        
        edu_title_lay = QHBoxLayout()
        edu_title = QLabel("Guide to calculate Cost/m²")
        edu_title.setStyleSheet("font-family: 'Outfit'; font-weight: bold; color: #0f172a; font-size: 14px;")
        edu_title_lay.addWidget(edu_title)
        edu_title_lay.addStretch()
        edu_layout.addLayout(edu_title_lay)
        
        formula_box = QFrame()
        formula_box.setObjectName("formula_box")
        formula_box.setStyleSheet("#formula_box { background-color: #ffffff; border-radius: 8px; border: 1px solid #e2e8f0; padding: 6px; }")
        formula_lay = QVBoxLayout(formula_box)
        formula_lay.setContentsMargins(5, 5, 5, 5)
        
        formula_math = QLabel("Cost per m² = Total Construction Cost / Gross Floor Area (GFA)")
        formula_math.setStyleSheet("font-family: 'Consolas'; font-weight: 700; color: #166534; font-size: 11px;")
        formula_math.setAlignment(Qt.AlignmentFlag.AlignCenter)
        formula_lay.addWidget(formula_math)
        edu_layout.addWidget(formula_box)
        
        body_lay = QHBoxLayout()
        body_lay.setSpacing(15)
        
        col1_layout = QVBoxLayout()
        col1_layout.setSpacing(5)
        
        c1_t = QLabel("<b>Definitions & Scope</b>")
        c1_t.setStyleSheet("font-size: 11px; color: #0f172a;")
        col1_layout.addWidget(c1_t)
        
        c1_desc = QLabel(
            "<b>Total Construction Cost:</b> Includes structural work, secondary works, and standard finishes. "
            "Excludes land purchase and site utility servicing.<br/>"
            "<b>Gross Floor Area (GFA):</b> Total area of all floors measured to the outside face of external walls."
        )
        c1_desc.setWordWrap(True)
        c1_desc.setStyleSheet("color: #475569; font-size: 10px; line-height: 1.3;")
        col1_layout.addWidget(c1_desc)
        
        c1_uses = QLabel("<b>Common Uses in Estimating</b>")
        c1_uses.setStyleSheet("font-size: 11px; color: #0f172a; margin-top: 2px;")
        col1_layout.addWidget(c1_uses)
        
        c1_uses_desc = QLabel(
            "• <b>Feasibility & Budgeting:</b> Scaled early-stage pricing before detailed designs exist.<br/>"
            "• <b>Comparison:</b> Benchmark contractor quotes against historical project data."
        )
        c1_uses_desc.setWordWrap(True)
        c1_uses_desc.setStyleSheet("color: #475569; font-size: 10px; line-height: 1.3;")
        col1_layout.addWidget(c1_uses_desc)
        
        col2_layout = QVBoxLayout()
        col2_layout.setSpacing(5)
        
        c2_t = QLabel("<b>Key Variables That Distort Cost/m²</b>")
        c2_t.setStyleSheet("font-size: 11px; color: #c2410c;")
        col2_layout.addWidget(c2_t)
        
        c2_desc = QLabel(
            "Flat rates can distort expectations. Costs vary based on the following:<br/>"
            "• <b>Room Function:</b> Wet areas (bathrooms/kitchens) cost more due to piping and tiling.<br/>"
            "• <b>Complexity:</b> Multi-angled perimeters increase forming and structural demands.<br/>"
            "• <b>Specification:</b> High-end finishes easily double or triple basic structural rates.<br/>"
            "• <b>Site Conditions:</b> Groundwork and steep slopes add costs independent of floor area."
        )
        c2_desc.setWordWrap(True)
        c2_desc.setStyleSheet("color: #475569; font-size: 10px; line-height: 1.3;")
        col2_layout.addWidget(c2_desc)
        
        body_lay.addLayout(col1_layout, 1)
        body_lay.addLayout(col2_layout, 1)
        edu_layout.addLayout(body_lay)
        
        # Source Citation & PDF Open Section
        source_box = QFrame()
        source_box.setObjectName("source_box")
        source_box.setStyleSheet("""
            #source_box {
                background-color: #f1f5f9;
                border-radius: 8px;
                border: 1px solid #e2e8f0;
                padding: 8px;
                margin-top: 4px;
            }
        """)
        source_lay = QHBoxLayout(source_box)
        source_lay.setContentsMargins(10, 4, 10, 4)
        source_lay.setSpacing(10)
        
        cite_icon = QLabel("📖")
        cite_icon.setStyleSheet("font-size: 16px;")
        
        cite_txt = QLabel(
            "<b>Reference Source:</b> "
            "<b>AECOM Africa Property & Construction Cost Guide 2025</b>."
        )
        cite_txt.setStyleSheet("color: #334155; font-size: 10px; font-family: 'Inter';")
        cite_txt.setWordWrap(True)
        
        self.open_pdf_btn = QPushButton("📄 Open AECOM Cost Guide 2025")
        self.open_pdf_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_pdf_btn.clicked.connect(self.open_aecom_guide)
        self.open_pdf_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e40af;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 12px;
                font-weight: bold;
                font-size: 10px;
                font-family: 'Inter';
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
            QPushButton:pressed {
                background-color: #1e3a8a;
            }
        """)
        
        source_lay.addWidget(cite_icon)
        source_lay.addWidget(cite_txt, 1)
        source_lay.addWidget(self.open_pdf_btn)
        
        edu_layout.addWidget(source_box)
        
        content_layout.addWidget(edu_card)
        content_layout.addStretch()
        
        main_scroll.setWidget(content_widget)
        root_layout.addWidget(main_scroll)

    def _on_gfa_slider_changed(self, value):
        self.gfa_val_lbl.blockSignals(True)
        self.gfa_val_lbl.setValue(value)
        self.gfa_val_lbl.blockSignals(False)
        self.refresh_calculations()

    def _on_gfa_spin_changed(self, value):
        self.gfa_slider.blockSignals(True)
        self.gfa_slider.setValue(min(value, self.gfa_slider.maximum()))
        self.gfa_slider.blockSignals(False)
        self.refresh_calculations()

    def _on_complexity_changed(self, index):
        factors = ["Simple (1.00x)", "Moderate (1.15x)", "High (1.35x)"]
        self.comp_val_lbl.setText(factors[index])
        self.refresh_calculations()

    def refresh_data(self):
        """Re-scans databases and updates graphs/metric cards."""
        self._load_currency()
        self._scan_actual_project_cost()
        self.refresh_calculations()

    def refresh_calculations(self):
        """
        Main calculation engine that translates slider options 
        and inputs into beautiful visual cost models in real time.
        """
        gfa = float(self.gfa_val_lbl.value())
        
        # 1. Base Rates for target types ( Accra baseline )
        base_rates = {
            "Residential House": 750.0,
            "Commercial Office": 1200.0,
            "Retail / Showroom": 950.0,
            "Industrial / Warehouse": 500.0,
            "Extension / Add-on": 800.0
        }
        b_type = self.type_combo.currentText()
        exchange_rate = self._get_usd_to_active_exchange_rate()
        base_rate = base_rates.get(b_type, 750.0) * exchange_rate
        
        # 2. Regional Factors
        region_idx = self.region_combo.currentIndex()
        region_factors = [1.0, 0.90, 0.95, 0.85, 0.80]
        region_factor = region_factors[region_idx]
        
        # 3. Quality Specifications Multipliers
        spec_idx = self.spec_combo.currentIndex()
        spec_multipliers = [1.0, 1.30, 1.80, 2.50]
        spec_mult = spec_multipliers[spec_idx]
        
        # 4. Complexity Multipliers
        comp_idx = self.comp_combo.currentIndex()
        comp_multipliers = [1.0, 1.15, 1.35]
        comp_mult = comp_multipliers[comp_idx]
        
        # 5. Site Conditions Surcharge Multipliers
        site_idx = self.site_combo.currentIndex()
        site_multipliers = [1.0, 1.12, 1.25]
        site_mult = site_multipliers[site_idx]
        
        # 6. Wet Area Plumbing Premium
        # Premiums scale with specification choice
        wet_premiums = [8000.0, 12000.0, 20000.0, 35000.0]
        wet_prem_rate = wet_premiums[spec_idx] * exchange_rate
        wet_count = float(self.wet_spin.value())
        total_wet_cost = wet_count * wet_prem_rate
        
        # Calculate cost driver components per m²
        dr_base = base_rate * region_factor
        dr_spec = dr_base * (spec_mult - 1.0)
        dr_comp = (dr_base * spec_mult) * (comp_mult - 1.0)
        dr_site = (dr_base * spec_mult * comp_mult) * (site_mult - 1.0)
        dr_wet = total_wet_cost / gfa
        
        simulated_rate = dr_base + dr_spec + dr_comp + dr_site + dr_wet
        simulated_total = simulated_rate * gfa
        
        # Update Simulated KPI Cards
        self.card_sim_rate.update_value(
            f"{self.currency_symbol}{simulated_rate:,.2f}",
            f"Calculated average rate"
        )
        self.card_sim_total.update_value(
            f"{self.currency_symbol}{simulated_total:,.2f}",
            f"Estimated budget for {int(gfa)} m²"
        )
        
        # Actual Project KPI Card Calculation
        actual_gfa = gfa
        if self.actual_project_net > 0 and actual_gfa > 0:
            actual_rate = self.actual_project_net / actual_gfa
            self.card_act_rate.update_value(
                f"{self.currency_symbol}{actual_rate:,.2f}",
                f"Across all BOQs ({self.currency_symbol}{self.actual_project_net:,.1f} total)"
            )
        else:
            actual_rate = 0.0
            self.card_act_rate.update_value("N/A", "Project not yet priced")
            
        # Standard Comparative range bounds for the spectrum bar
        min_normal = base_rate * region_factor * 0.8
        max_normal = base_rate * region_factor * 1.5
        
        # Set range spectrum charts
        self.range_chart.set_rates(simulated_rate, actual_rate, min_normal, max_normal, self.currency_symbol)
        
        # Update driver breakdown
        self.breakdown_chart.set_data([
            ("Base Frame", dr_base, "#2e7d32"),
            ("Spec Quality", dr_spec, "#0277bd"),
            ("Complexity", dr_comp, "#ef6c00"),
            ("Site/Ground", dr_site, "#546e7a"),
            ("Wet Areas", dr_wet, "#6a1b9a")
        ], self.currency_symbol)

        self._save_state()

    def _save_state(self):
        """Persists scenario estimator slider and selector values to project states folder."""
        state_dir = os.path.join(self.project_dir, "PBOQ States")
        os.makedirs(state_dir, exist_ok=True)
        state_file = os.path.join(state_dir, "parametric_state.json")
        
        state = {
            "gfa": self.gfa_val_lbl.value(),
            "building_type_idx": self.type_combo.currentIndex(),
            "region_idx": self.region_combo.currentIndex(),
            "spec_idx": self.spec_combo.currentIndex(),
            "complexity_idx": self.comp_combo.currentIndex(),
            "wet_areas": self.wet_spin.value(),
            "site_conditions_idx": self.site_combo.currentIndex()
        }
        
        try:
            with open(state_file, 'w') as f:
                json.dump(state, f)
        except Exception as e:
            print(f"Error saving parametric benchmarking state: {e}")

    def _load_state(self):
        """Loads persisted scenario estimator settings from project states folder."""
        state_file = os.path.join(self.project_dir, "PBOQ States", "parametric_state.json")
        if not os.path.exists(state_file):
            return
            
        try:
            with open(state_file, 'r') as f:
                state = json.load(f)
                
            # Temporarily block signals to avoid triggering multiple intermediate calculation updates
            self.gfa_slider.blockSignals(True)
            self.type_combo.blockSignals(True)
            self.region_combo.blockSignals(True)
            self.spec_combo.blockSignals(True)
            self.comp_combo.blockSignals(True)
            self.wet_spin.blockSignals(True)
            self.site_combo.blockSignals(True)
            
            if "gfa" in state:
                self.gfa_slider.setValue(state["gfa"])
                self.gfa_val_lbl.setText(f"{state['gfa']} m²")
            if "building_type_idx" in state:
                self.type_combo.setCurrentIndex(state["building_type_idx"])
            if "region_idx" in state:
                self.region_combo.setCurrentIndex(state["region_idx"])
            if "spec_idx" in state:
                self.spec_combo.setCurrentIndex(state["spec_idx"])
            if "complexity_idx" in state:
                self.comp_combo.setCurrentIndex(state["complexity_idx"])
                factors = ["Simple (1.00x)", "Moderate (1.15x)", "High (1.35x)"]
                self.comp_val_lbl.setText(factors[state["complexity_idx"]])
            if "wet_areas" in state:
                self.wet_spin.setValue(state["wet_areas"])
            if "site_conditions_idx" in state:
                self.site_combo.setCurrentIndex(state["site_conditions_idx"])
                
        except Exception as e:
            print(f"Error loading parametric benchmarking state: {e}")
        finally:
            self.gfa_slider.blockSignals(False)
            self.type_combo.blockSignals(False)
            self.region_combo.blockSignals(False)
            self.spec_combo.blockSignals(False)
            self.comp_combo.blockSignals(False)
            self.wet_spin.blockSignals(False)
            self.site_combo.blockSignals(False)

    def open_aecom_guide(self):
        """Attempts to open the AECOM Africa Cost Guide 2025 PDF using the default system viewer."""
        possible_paths = [
            # Workspace & Project Root directories
            os.path.join(self.project_dir, "aecom_africa_cost_guide_2025.pdf"),
            os.path.join(self.project_dir, "aecom_cost_guide_2025.pdf"),
            os.path.join(os.path.dirname(self.project_dir), "aecom_africa_cost_guide_2025.pdf"),
            os.path.join(os.path.dirname(self.project_dir), "aecom_cost_guide_2025.pdf"),
            # User folders
            r"C:\Users\Consar-Kilpatrick\Desktop\aecom_africa_cost_guide_2025.pdf",
            r"C:\Users\Consar-Kilpatrick\Downloads\aecom_africa_cost_guide_2025.pdf",
            os.path.expanduser(r"~\Desktop\aecom_africa_cost_guide_2025.pdf"),
            os.path.expanduser(r"~\Downloads\aecom_africa_cost_guide_2025.pdf")
        ]
        
        found_path = None
        for p in possible_paths:
            if os.path.exists(p):
                found_path = p
                break
                
        if found_path:
            success = QDesktopServices.openUrl(QUrl.fromLocalFile(found_path))
            if not success:
                QMessageBox.warning(
                    self, 
                    "Failed to Open File", 
                    f"Found the file at:\n{found_path}\n\nBut the system default viewer failed to open it. Please open it manually."
                )
        else:
            QMessageBox.critical(
                self,
                "File Not Found",
                "Could not locate the AECOM Africa Cost Guide 2025 PDF in standard locations.\n\n"
                "Please ensure 'aecom_africa_cost_guide_2025.pdf' or 'aecom_cost_guide_2025.pdf' is placed in your project folder, Desktop, or Downloads folder."
            )
