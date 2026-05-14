import os
import sqlite3
import json
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QFrame, QGridLayout, QScrollArea, QSpacerItem, QSizePolicy)
from PyQt6.QtCore import Qt, QRectF, QPointF, pyqtSignal, QSize
from PyQt6.QtGui import QColor, QPainter, QBrush, QPen, QFont, QLinearGradient, QFontMetrics

from analytics_components import get_project_currency_symbol, MetricCard, SelectionFrame, ChartWidget, DonutChart, ParetoBarChart, WaterfallChart
from pboq_logic import PBOQLogic

class MetricRow(QFrame):
    clicked = pyqtSignal(object) # Custom signal that sends the row instance

    def __init__(self, name, bid, cost, margin, currency_symbol="$", is_total=False, parent=None):
        super().__init__(parent)
        self.currency_symbol = currency_symbol
        self.is_total = is_total
        self.is_selected = False
        self.bg_base = "#f1f8e9" if is_total else "#ffffff"
        self.border_base = "#2e7d32" if is_total else "#e2e8f0"
        self._update_style()
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 8, 15, 8)
        layout.setSpacing(15)

        # Name
        name_lbl = QLabel(name)
        weight = "800" if is_total else "600"
        name_lbl.setStyleSheet(f"font-family: 'Inter'; font-weight: {weight}; color: #1e293b; font-size: 13px; border: none;")
        name_lbl.setToolTip(name) 
        name_lbl.setWordWrap(True)
        layout.addWidget(name_lbl, 6) 

        # Bid Pill
        p_border = "#166534" if not is_total else "none"
        bid_pill = QFrame()
        bid_pill.setStyleSheet(f"background-color: #f0fdf4; border-radius: 4px; border: 1px solid {p_border};")
        bp_layout = QHBoxLayout(bid_pill)
        bp_layout.setContentsMargins(5, 2, 5, 2)
        bid_val = QLabel(f"{self.currency_symbol} {bid:,.2f}")
        bid_val.setStyleSheet("font-family: 'Consolas'; font-weight: 700; color: #166534; font-size: 13px; border: none;")
        bp_layout.addWidget(bid_val)
        layout.addWidget(bid_pill, 2)

        # Cost Pill
        c_border = "#1e40af" if not is_total else "none"
        cost_pill = QFrame()
        cost_pill.setStyleSheet(f"background-color: #eff6ff; border-radius: 4px; border: 1px solid {c_border};")
        cp_layout = QHBoxLayout(cost_pill)
        cp_layout.setContentsMargins(5, 2, 5, 2)
        cost_val = QLabel(f"{self.currency_symbol} {cost:,.2f}")
        cost_val.setStyleSheet("font-family: 'Consolas'; font-weight: 700; color: #1e40af; font-size: 13px; border: none;")
        cp_layout.addWidget(cost_val)
        layout.addWidget(cost_pill, 2)

        # Profit Pill
        profit = bid - cost
        pr_border = "#b45309" if not is_total else "none"
        profit_pill = QFrame()
        profit_pill.setStyleSheet(f"background-color: #fffbeb; border-radius: 4px; border: 1px solid {pr_border};")
        pp_layout = QHBoxLayout(profit_pill)
        pp_layout.setContentsMargins(5, 2, 5, 2)
        profit_val = QLabel(f"{self.currency_symbol} {profit:,.2f}")
        profit_val.setStyleSheet("font-family: 'Consolas'; font-weight: 700; color: #b45309; font-size: 13px; border: none;")
        profit_val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pp_layout.addWidget(profit_val)
        layout.addWidget(profit_pill, 2)

        # Margin Badge
        m_color = "#ea580c" if margin > 0 else "#991b1b"
        m_bg = "#fff7ed" if margin > 0 else "#fef2f2"
        margin_lbl = QLabel(f"{margin:.1f}% Margin")
        margin_lbl.setStyleSheet(f"background-color: {m_bg}; color: {m_color}; border-radius: 4px; padding: 2px 8px; font-weight: 800; font-size: 11px; border: none;")
        margin_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(margin_lbl, 2)

    def _update_style(self):
        bg = "#fffde7" if self.is_selected else ("#f1f8e9" if self.is_total else "#ffffff")
        border = "#fbc02d" if self.is_selected else ("#2e7d32" if self.is_total else "#e2e8f0")
        hover_bg = "#ecfdf5" if not self.is_total else bg
        
        self.setStyleSheet(f"""
            MetricRow {{ background-color: {bg}; border-radius: 8px; border: 1px solid {border}; }}
            MetricRow:hover {{ background-color: {hover_bg}; border: 1px solid #2e7d32; }}
        """)

    def set_selected(self, selected):
        if self.is_total: return
        self.is_selected = selected
        self._update_style()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self)
        super().mousePressEvent(event)

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

        # 5. Sub-Contractor Analysis Table
        sub_table_frame = QFrame()
        sub_table_frame.setStyleSheet("background-color: white; border-radius: 16px; border: 1px solid #e2e8f0;")
        sub_table_layout = QVBoxLayout(sub_table_frame)
        sub_table_layout.setContentsMargins(25, 25, 25, 25)
        
        sub_tbl_lbl = QLabel("<b style='font-size: 16px; font-family: Inter; color: #1e293b;'>Sub-Contractor Analysis</b>")
        sub_table_layout.addWidget(sub_tbl_lbl)
        
        self.sub_table_scroll = QScrollArea()
        self.sub_table_scroll.setWidgetResizable(True)
        self.sub_table_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.sub_table_scroll.setMinimumHeight(400)
        self.sub_table_container = QWidget()
        self.sub_table_list = QVBoxLayout(self.sub_table_container)
        self.sub_table_list.setSpacing(5)
        self.sub_table_list.setContentsMargins(0, 10, 0, 10)
        self.sub_table_list.addStretch()
        self.sub_table_scroll.setWidget(self.sub_table_container)
        sub_table_layout.addWidget(self.sub_table_scroll)
        self.content_layout.addWidget(sub_table_frame)
        
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
                    
                    # 1. Load Currency using standardized helper
                    self.currency_symbol = get_project_currency_symbol(self.project_dir) + " "
                    
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
        
        t_bid, t_cost, t_fixed_cost = 0.0, 0.0, 0.0
        dist = {'Materials': 0.0, 'Labor': 0.0, 'Equipment': 0.0, 'Plant': 0.0, 'Subcontractors': 0.0, 'Risk': 0.0}
        all_items, sections = [], []
        c_agg = {} # Categorical aggregate (Project Wide)
        sub_agg = {} # Subcontractor aggregate (Project Wide)

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
                s_agg = {} # Sectional aggregate (Per File)

                for r in rows:
                    sheet, desc, q, b, plug, p_code, p_cat, sub, gross, r_code, prov, pc, dw, s_pkg, s_n, pr_cat, pc_c, s_cat = r
                    desc_low = (desc or "").lower()
                    
                    if "collection" in desc_low or "summary" in desc_low:
                        continue
                        
                    qty_f, bill_f = self._to_float(q), self._to_float(b)
                    if bill_f == 0 and qty_f == 0: continue
                    
                    p_val, s_val, g_val, pr_val, pc_val, d_val = [self._to_float(x) for x in [plug, sub, gross, prov, pc, dw]]
                    
                    # 1. CORE FIX: Pricing Category based detection
                    # Check if the item is explicitly categorized as Preliminaries
                    is_prelim = (str(p_cat).lower() == "preliminaries" or "prelim" in desc_low) if p_cat or desc else False
                    is_fixed = (pr_val > 0 or pc_val > 0 or d_val > 0 or is_prelim)
                    
                    active_code = p_code if p_code and str(p_code).strip() else r_code
                    ratios, master_net_cost, master_cat = self._get_rate_composition(active_code) if active_code else (None, 0.0, None)
                    
                    # Determine Final Category
                    category = "Uncategorized"
                    if is_prelim: 
                        category = "Preliminaries"
                    elif p_cat and str(p_cat).strip() and str(p_cat).strip() != "''": 
                        category = str(p_cat).strip()
                    elif pr_cat and str(pr_cat).strip() and str(pr_cat).strip() != "''": 
                        category = str(pr_cat).strip()
                    elif pc_c and str(pc_c).strip() and str(pc_c).strip() != "''": 
                        category = str(pc_c).strip()
                    elif s_cat and str(s_cat).strip() and str(s_cat).strip() != "''":
                        category = str(s_cat).strip()
                    elif master_cat and str(master_cat).strip(): 
                        category = str(master_cat).strip()
                    
                    # Subcontractor Categorization Override
                    sub_ratio = 0.0
                    if ratios:
                        sub_ratio = ratios.get('Subcontractors', 0.0)
                    elif s_val > 0:
                        sub_ratio = 1.0
                    
                    if sub_ratio > 0.8 and s_pkg and str(s_pkg).strip() and str(s_pkg).strip() != "''":
                        category = f"Sub-Contract: {category}: {str(s_pkg).strip()}"
                    
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
                    
                    # Ensure qty is at least 1 for lump sums
                    is_lump_sum = is_prelim or is_fixed
                    calc_qty = qty_f if qty_f > 0 else (1.0 if is_lump_sum and bill_f > 0 else 0.0)
                    item_cost = unit_cost * calc_qty
                    
                    # 2. Resource distribution
                    if is_prelim:
                        dist['Risk'] += item_cost
                    elif ratios:
                        dist['Materials'] += item_cost * ratios.get('Materials', 0.0)
                        dist['Labor'] += item_cost * ratios.get('Labor', 0.0)
                        dist['Plant'] += item_cost * ratios.get('Plant', 0.0)
                        dist['Equipment'] += item_cost * ratios.get('Equipment', 0.0)
                        dist['Subcontractors'] += item_cost * ratios.get('Subcontractors', 0.0)
                        dist['Risk'] += item_cost * ratios.get('Indirect', 0.0)
                    else:
                        if p_val > 0: dist['Materials'] += item_cost
                        elif s_val > 0: dist['Subcontractors'] += item_cost
                        elif g_val > 0: dist['Labor'] += item_cost
                        elif d_val > 0: dist['Labor'] += item_cost
                        elif is_fixed: dist['Risk'] += item_cost

                    t_bid += round(bill_f, 2)
                    t_cost += round(item_cost, 2)
                    if is_fixed:
                        t_fixed_cost += round(item_cost, 2)
                    if not is_prelim:
                        all_items.append((desc or "Unnamed", bill_f))
                    if sheet not in s_agg: s_agg[sheet] = [0.0, 0.0]
                    s_agg[sheet][0] += bill_f
                    s_agg[sheet][1] += item_cost
                    
                    if category not in c_agg: c_agg[category] = [0.0, 0.0]
                    c_agg[category][0] += bill_f
                    c_agg[category][1] += item_cost

                    
                    # Subcontractor Analysis Aggregation
                    if sub_ratio > 0:
                        pkg_key = str(s_pkg).strip() or "General Sub"
                        sub_key = f"{pkg_key} ({str(s_n).strip() or 'Unknown Sub'})"
                        if sub_key not in sub_agg: sub_agg[sub_key] = [0.0, 0.0]
                        sub_agg[sub_key][0] += bill_f * sub_ratio
                        sub_agg[sub_key][1] += item_cost * sub_ratio
                    
                for s, v in s_agg.items():
                    clean_name = f.replace('.db', '').replace('PBOQ_', '')
                    sections.append({'name': f"{clean_name} : {s}", 'bid': v[0], 'cost': v[1]})
                conn.close()
            except Exception as e:
                print(f"Error processing {f}: {e}")

        # Metrics
        # The base net cost (t_cost) IS the constant base cost.
        # Overhead and profit are add-ons calculated as percentages of the base cost.
        # Final Bid = Base Cost + Overhead + Profit.
        t_base_cost = t_cost
        overhead_amount = t_base_cost * (self.overhead_rate / 100.0)
        profit_amount = t_base_cost * (self.profit_rate / 100.0)
        t_final_bid = t_base_cost + overhead_amount + profit_amount
        
        actual_overhead_pct = (overhead_amount / t_final_bid * 100) if t_final_bid > 0 else 0
        actual_profit_pct = (profit_amount / t_final_bid * 100) if t_final_bid > 0 else 0
        
        self.card_total_bid.update_value(f"{self.currency_symbol}{t_final_bid:,.2f}")
        self.card_total_cost.update_value(f"{self.currency_symbol}{t_base_cost:,.2f}")
        self.card_margin.update_value(f"{actual_profit_pct:.2f}%")
        self.card_overhead.update_value(f"{actual_overhead_pct:.2f}%")
        
        self.donut_chart.currency_symbol = self.currency_symbol
        self.pareto_chart.currency_symbol = self.currency_symbol
        self.bridge_chart.currency_symbol = self.currency_symbol

        # Donut (Using exact ratios from bottom-up buildup analysis)
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
            ("Base Cost", t_base_cost, "#0277bd"),
            ("Overhead", overhead_amount, "#546e7a"),
            ("Profit", profit_amount, "#ef6c00"),
            ("Final Bid", t_final_bid, "#1b5e20")
        ])

        # 5. Populate Tables
        # Each section/category/sub cost = its actual bill amounts (constant base).
        # Its bid = cost + cost × markup%.
        combined_markup_pct = (self.overhead_rate + self.profit_rate) / 100.0
        
        # Sectional Table
        self._clear_table(self.table_list)
        self._add_table_header(self.table_list, "Section Description")
        sections.sort(key=lambda x: x['cost'], reverse=True)
        s_total_bid, s_total_cost = 0.0, 0.0
        for s in sections: 
            s['bid'] = s['cost'] * (1.0 + combined_markup_pct)  # final bid = base + markup
            self._add_table_row(self.table_list, s)
            s_total_bid += s['bid']
            s_total_cost += s['cost']
        
        if sections:
            self._add_table_row(self.table_list, {'name': 'TOTAL PROJECT SUMMARY', 'bid': s_total_bid, 'cost': s_total_cost}, is_total=True)
        
        # Categorical Table
        self._clear_table(self.cat_table_list)
        self._add_table_header(self.cat_table_list, "Trade Category")
        cat_list = [{'name': k, 'bid': v[0], 'cost': v[1]} for k, v in c_agg.items()]
        cat_list.sort(key=lambda x: x['cost'], reverse=True)
        c_total_bid, c_total_cost = 0.0, 0.0
        for c in cat_list: 
            if not c['name'].startswith('Sub-Contract:'):
                c['bid'] = c['cost'] * (1.0 + combined_markup_pct)
            # If it is a Sub-Contract, it retains its original BOQ Target bid (c['bid'])
            self._add_table_row(self.cat_table_list, c)
            c_total_bid += c['bid']
            c_total_cost += c['cost']

        if cat_list:
            self._add_table_row(self.cat_table_list, {'name': 'TOTAL CATEGORICAL SUMMARY', 'bid': c_total_bid, 'cost': c_total_cost}, is_total=True)
            
        # Sub-Contractor Table
        self._clear_table(self.sub_table_list)
        self._add_table_header(self.sub_table_list, "Sub-Contractor Package")
        sub_list = [{'name': k, 'bid': v[0], 'cost': v[1]} for k, v in sub_agg.items()]
        sub_list.sort(key=lambda x: x['cost'], reverse=True)
        sub_total_bid, sub_total_cost = 0.0, 0.0
        for sb in sub_list:
            # We explicitly do NOT apply the uniform markup formula here.
            # The Bid Amount (sb['bid']) retains its original value v[0], 
            # which is the true BOQ target/bill amount for this sub-contract package.
            self._add_table_row(self.sub_table_list, sb)
            sub_total_bid += sb['bid']
            sub_total_cost += sb['cost']
            
        if sub_list:
            self._add_table_row(self.sub_table_list, {'name': 'TOTAL SUB-CONTRACT SUMMARY', 'bid': sub_total_bid, 'cost': sub_total_cost}, is_total=True)
        
    def _to_float(self, val):
        if not val: return 0.0
        if isinstance(val, (int, float)): return float(val)
        try: return float(str(val).replace(',', '').replace(' ', '').replace('₵','').replace('$','').strip())
        except: return 0.0

    def _clear_table(self, layout):
        while layout.count() > 1:
            it = layout.takeAt(0)
            if it.widget(): it.widget().deleteLater()

    def _add_table_header(self, layout, desc_title):
        header = QFrame()
        header.setStyleSheet("background-color: transparent; border: none;")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(15, 0, 15, 5)
        h_layout.setSpacing(15)
        
        style = "font-family: 'Inter'; font-weight: 700; color: #64748b; font-size: 11px; text-transform: uppercase;"
        
        titles = [
            (desc_title, 6),
            ("Bid Amount", 2),
            ("Net Cost", 2),
            ("Profit & Overheads", 2),
            ("Margin %", 2)
        ]
        
        for text, stretch in titles:
            lbl = QLabel(text)
            lbl.setStyleSheet(style)
            if stretch == 2: lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            h_layout.addWidget(lbl, stretch)
            
        layout.insertWidget(layout.count() - 1, header)

    def _add_table_row(self, layout, data, is_total=False):
        bid, cost = data.get('bid', 0.0), data.get('cost', 0.0)
        margin = ((bid - cost) / bid * 100) if bid > 0 else 0
        r = MetricRow(data.get('name', 'Unknown'), bid, cost, margin, currency_symbol=self.currency_symbol.strip(), is_total=is_total)
        r.clicked.connect(self._handle_row_click)
        layout.insertWidget(layout.count() - 1, r)

    def _handle_row_click(self, row):
        if row.is_total: return
        
        # Unselect previous
        if self._selected_row and self._selected_row != row:
            try:
                self._selected_row.set_selected(False)
            except: pass
            
        self._selected_row = row
        self._selected_row.set_selected(True)

