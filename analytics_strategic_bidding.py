import os
import sqlite3
import json
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QFrame, QGridLayout, QScrollArea, QLineEdit,
                             QPushButton, QSpacerItem, QSizePolicy, QMessageBox)
from PyQt6.QtCore import Qt, QRectF, QPointF, pyqtSignal, QSize
from PyQt6.QtGui import QColor, QPainter, QBrush, QPen, QFont, QLinearGradient, QFontMetrics, QDoubleValidator

from analytics_components import get_project_currency_symbol, MetricCard, ChartWidget, WaterfallChart
from pboq_logic import PBOQLogic


class StrategicBiddingAnalytic(QWidget):
    """Interactive 'What-If' dashboard for project markup simulation."""
    def __init__(self, project_dir, parent=None):
        super().__init__(parent)
        self.project_dir = self._resolve_project_root(project_dir)
        self.pj_db_dir = os.path.join(self.project_dir, "Project Database")
        
        # State
        self.base_cost = 0.0
        self.fixed_cost = 0.0 # Costs that shouldn't receive profit (Prov/PC Sums)
        self.current_overhead = 0.0
        self.current_profit = 0.0
        self.current_factor = 1.0
        self.currency_symbol = get_project_currency_symbol(self.project_dir) + " "
        
        self.scenario_overhead = 0.0
        self.scenario_profit = 0.0
        self.scenario_factor = 1.0
        
        self._init_ui()
        self.load_baseline()

    def refresh_data(self):
        """Reload all data from the database to ensure freshness."""
        self.load_baseline()

    def _resolve_project_root(self, path):
        """Ensures the project directory points to the root (above Project Database)."""
        if not path: return ""
        norm_path = os.path.abspath(path)
        if os.path.basename(norm_path).lower() == "project database":
            return os.path.dirname(norm_path)
        # If "Project Database" folder exists as a sibling, we might be in another subfolder
        # But usually we expect the parent to contain it.
        if not os.path.exists(os.path.join(norm_path, "Project Database")):
            # Look one level up if it exists there
            parent = os.path.dirname(norm_path)
            if os.path.exists(os.path.join(parent, "Project Database")):
                return parent
        return norm_path

    def _init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setStyleSheet("background-color: #f8fafc;")
        
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(10, 10, 10, 10)
        self.content_layout.setSpacing(15)
        
        # Header
        header_container = QVBoxLayout()
        header = QLabel("Strategic Bidding 'What-If' Analysis")
        header.setStyleSheet("font-family: 'Outfit'; font-size: 26px; font-weight: 800; color: #1b5e20;")
        header_container.addWidget(header)
        desc = QLabel("Simulate project profitability by adjusting markups and scaling factors in real-time.")
        desc.setStyleSheet("color: #64748b; font-size: 14px;")
        header_container.addWidget(desc)
        self.content_layout.addLayout(header_container)
        
        # Main Split: Controls (Left) and Results (Right)
        main_split = QHBoxLayout()
        main_split.setSpacing(10)
        
        # --- LEFT: CONTROLS ---
        controls_frame = QFrame()
        controls_frame.setFixedWidth(260)
        controls_frame.setStyleSheet("background-color: white; border-radius: 16px; border: 1px solid #e2e8f0;")
        controls_layout = QVBoxLayout(controls_frame)
        controls_layout.setContentsMargins(20, 20, 20, 20)
        controls_layout.setSpacing(20)
        
        ctrl_title = QLabel("Simulation Controls")
        ctrl_title.setStyleSheet("font-weight: 800; color: #1e293b; font-size: 16px;")
        controls_layout.addWidget(ctrl_title)
        
        # Overhead Input
        self.ov_input = self._create_input_group(controls_layout, "Project Overhead (%)")
        self.ov_input.textChanged.connect(self._on_parameter_changed)
        
        # Profit Input
        self.pr_input = self._create_input_group(controls_layout, "Project Profit (%)")
        self.pr_input.textChanged.connect(self._on_parameter_changed)
        
        # Factor Input
        self.fc_input = self._create_input_group(controls_layout, "Global Adjustment Factor")
        self.fc_input.textChanged.connect(self._on_parameter_changed)
        
        controls_layout.addStretch()
        
        self.apply_btn = QPushButton("Apply to Project Settings")
        self.apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.apply_btn.setStyleSheet("""
            QPushButton {
                background-color: #2e7d32; 
                color: #ffff00; 
                border-radius: 8px; 
                padding: 12px; 
                font-weight: bold; 
                font-size: 13px;
            }
            QPushButton:hover { background-color: #388e3c; }
            QPushButton:pressed { background-color: #1b5e20; }
        """)
        self.apply_btn.clicked.connect(self.apply_to_project)
        controls_layout.addWidget(self.apply_btn)
        
        main_split.addWidget(controls_frame)
        
        # --- RIGHT: RESULTS ---
        results_layout = QVBoxLayout()
        results_layout.setSpacing(20)
        
        # Metric Comparison Row
        metrics_row = QHBoxLayout()
        metrics_row.setSpacing(5)
        
        self.card_bid = MetricCard("Total Bid", "0.00", "Current: 0.00", color="#1b5e20")
        self.card_profit = MetricCard("Net Profit", "0.00", "Current: 0.00", color="#ef6c00")
        self.card_margin = MetricCard("Margin (%)", "0.00%", "Current: 0.00%", color="#bf360c")
        self.card_overhead = MetricCard("Overhead", "0.00", "Current: 0.00", color="#546e7a")
        self.card_overhead_pct = MetricCard("Overhead (%)", "0.00%", "Current: 0.00%", color="#263238")
        
        # Aggressive shrinkage for cards
        for card in [self.card_bid, self.card_profit, self.card_margin, self.card_overhead, self.card_overhead_pct]:
            card.setMinimumWidth(110)
            card.setFixedHeight(100)
            card.value_label.setStyleSheet("color: #212121; font-weight: 800; font-size: 16px;")
            card.title_label.setStyleSheet(f"color: {card.title_label.palette().windowText().color().name()}; font-weight: bold; font-size: 10px;")
            metrics_row.addWidget(card)
        
        results_layout.addLayout(metrics_row)
        
        # Charts Row
        charts_row = QHBoxLayout()
        self.waterfall = WaterfallChart("Scenario Financial Bridge")
        
        charts_row.addWidget(self._create_chart_frame("Live Financial Bridge Comparison", self.waterfall))
        results_layout.addLayout(charts_row)
        
        main_split.addLayout(results_layout, 1)
        
        self.content_layout.addLayout(main_split)
        
        self.scroll_area.setWidget(self.content_widget)
        root_layout.addWidget(self.scroll_area)

    def _create_input_group(self, layout, title):
        lbl = QLabel(title)
        lbl.setStyleSheet("color: #64748b; font-weight: 600; font-size: 12px;")
        layout.addWidget(lbl)
        
        edit = QLineEdit()
        edit.setPlaceholderText("0.000000")
        # Allow values from -100 to 1000 with 6 decimal places for absolute precision
        validator = QDoubleValidator(-100.0, 1000.0, 6)
        validator.setNotation(QDoubleValidator.Notation.StandardNotation)
        edit.setValidator(validator)
        edit.setStyleSheet("""
            QLineEdit {
                border: 1px solid #cbd5e1; 
                border-radius: 8px; 
                padding: 10px; 
                font-size: 14px;
                background-color: #f8fafc;
            }
            QLineEdit:focus {
                border: 2px solid #1b5e20;
                background-color: white;
            }
        """)
        layout.addWidget(edit)
        
        # Monkey patch value property for easier access
        edit.actual_value = lambda: self._to_float(edit.text())
        edit.set_actual_value = lambda v: edit.setText(f"{float(v):.6f}")
        return edit

    def _create_chart_frame(self, title, chart):
        f = QFrame()
        f.setStyleSheet("background-color: white; border-radius: 16px; border: 1px solid #e2e8f0;")
        l = QVBoxLayout(f)
        l.setContentsMargins(15, 10, 15, 12)
        l.setSpacing(5)
        lbl = QLabel(title)
        lbl.setStyleSheet("font-weight: 800; color: #1e293b; font-size: 16px;")
        l.addWidget(lbl, 0, Qt.AlignmentFlag.AlignTop)
        l.addWidget(chart, 1)
        return f

    def load_baseline(self):
        """Loads current project financial state from databases with high accuracy."""
        try:
            # 1. Load Settings
            self._load_project_settings()
            
            # 2. Calculate Accurate Totals (Matches Financial Executive Dashboard)
            self._calculate_accurate_totals()
            
            # 3. Set inputs to actual effective markup rates discovered in PBOQ
            # This ensures "Scenario" starts exactly equal to "Current" with no rounding up.
            total_markup = self.actual_bid - self.base_cost
            markable = self.base_cost - self.fixed_cost
            
            eff_oh_rate = self.current_overhead
            eff_pr_rate = self.current_profit
            
            # Round effective rates to eliminate residual noise from floating point drift
            # If the rate is extremely small (e.g. 0.000001%), treat it as absolute zero
            if abs(eff_oh_rate) < 0.00001: eff_oh_rate = 0.0
            if abs(eff_pr_rate) < 0.00001: eff_pr_rate = 0.0
            
            self.ov_input.set_actual_value(eff_oh_rate)
            self.pr_input.set_actual_value(eff_pr_rate)
            self.fc_input.set_actual_value(self.current_factor)
            
            self.update_simulation()
        except Exception as e:
            print(f"Error loading baseline: {e}")

    def _load_project_settings(self):
        self.current_overhead = 15.0
        self.current_profit = 10.0
        self.current_factor = 1.0
        self.currency_symbol = "$"
        
        try:
            if os.path.exists(self.pj_db_dir):
                dbs = [f for f in os.listdir(self.pj_db_dir) if f.lower().endswith('.db') and "rates" not in f.lower()]
                if dbs:
                    db_path = os.path.join(self.pj_db_dir, dbs[0])
                    conn = sqlite3.connect(db_path)
                    cursor = conn.cursor()
                    
                    cursor.execute("SELECT key, value FROM settings WHERE key IN ('overhead', 'profit', 'factor')")
                    for k, v in cursor.fetchall():
                        if k == 'overhead': self.current_overhead = float(v)
                        elif k == 'profit': self.current_profit = float(v)
                        elif k == 'factor': self.current_factor = float(v)
                    
                    # 1. Load Currency using standardized helper
                    self.currency_symbol = get_project_currency_symbol(self.project_dir) + " "
                    conn.close()
        except: pass

    def _calculate_accurate_totals(self):
        """Deep resource drill-down to calculate true project net cost. Synchronized with Financial Dashboard."""
        self.base_cost = 0.0
        self.fixed_cost = 0.0
        self.actual_bid = 0.0
        self._rate_cache = {}
        pboq_folder = os.path.join(self.project_dir, "Priced BOQs")
        if not os.path.exists(pboq_folder): return

        files = [f for f in os.listdir(pboq_folder) if f.lower().endswith('.db')]
        for f in files:
            db_path = os.path.join(pboq_folder, f)
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
                
                query_parts = [f"\"{d_col}\"", f"\"{q_col}\"", f"\"{b_col}\""]
                for k in ['plug', 'plug_code', 'plug_cat', 'sub', 'gross', 'rate_code', 'prov', 'pc', 'dw']:
                    v = src_cols.get(k)
                    query_parts.append(f"\"{v}\"" if v else "''")
                
                cursor.execute(f"SELECT {', '.join(query_parts)} FROM pboq_items")
                rows = cursor.fetchall()

                for r in rows:
                    desc, q, b, plug, p_code, p_cat, sub, gross, r_code, prov, pc, dw = r
                    desc_low = (desc or "").lower()
                    if "collection" in desc_low or "summary" in desc_low: continue
                        
                    qty_f, bill_f = self._to_float(q), self._to_float(b)
                    if bill_f == 0 and qty_f == 0: continue
                    
                    p_val, s_val, g_val, pr_val, pc_val, d_val = [self._to_float(x) for x in [plug, sub, gross, prov, pc, dw]]
                    
                    # 1. CORE SYNC Logic
                    is_prelim = (str(p_cat).lower() == "preliminaries" or "prelim" in desc_low) if p_cat or desc else False
                    is_fixed_type = (pr_val > 0 or pc_val > 0 or d_val > 0 or is_prelim)
                    
                    active_code = p_code if p_code and str(p_code).strip() else r_code
                    _, master_net_cost = self._get_rate_composition(active_code) if active_code else (None, 0.0)
                    
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
                            unit_cost = bill_f if (is_prelim or is_fixed_type) and bill_f > 0 and qty_f <= 1 else 0.0
                    
                    # Ensure qty is at least 1 for lump sums
                    is_lump_sum = is_prelim or is_fixed_type
                    calc_qty = qty_f if qty_f > 0 else (1.0 if is_lump_sum and bill_f > 0 else 0.0)
                    item_net_cost = unit_cost * calc_qty
                    
                    self.base_cost += round(item_net_cost, 2)
                    self.actual_bid += round(bill_f, 2)
                    if is_fixed_type:
                        self.fixed_cost += round(item_net_cost, 2)
                
                conn.close()
            except Exception as e:
                print(f"Error accurately processing {f}: {e}")

    def _get_rate_composition(self, rate_code):
        """Analyzes a rate buildup. Cached for performance."""
        if not rate_code: return None, 0.0
        if rate_code in self._rate_cache: return self._rate_cache[rate_code]

        try:
            dbs = [f for f in os.listdir(self.pj_db_dir) if f.lower().endswith('.db') and "rates" not in f.lower()]
            if not dbs: return None, 0.0
            
            db_path = os.path.join(self.pj_db_dir, dbs[0])
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT net_total FROM estimates WHERE rate_code = ?", (rate_code,))
            res = cursor.fetchone()
            conn.close()
            if res:
                self._rate_cache[rate_code] = (None, float(res[0] or 0.0))
                return self._rate_cache[rate_code]
        except: pass
        return None, 0.0

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

    def _on_parameter_changed(self):
        self.scenario_overhead = self.ov_input.actual_value()
        self.scenario_profit = self.pr_input.actual_value()
        self.scenario_factor = self.fc_input.actual_value()
        self.update_simulation()

    def update_simulation(self):
        # The net cost (self.base_cost) IS the base cost — constant.
        # Overhead and profit are add-ons: Final Bid = Base Cost + OH + Profit.
        # This matches the Financial Executive dashboard model exactly.
        
        # Current baseline (from project settings)
        curr_cost = self.base_cost
        curr_overhead_amt = curr_cost * (self.current_overhead / 100.0)
        curr_profit_amt = curr_cost * (self.current_profit / 100.0)
        curr_bid = curr_cost + curr_overhead_amt + curr_profit_amt
        curr_margin_pct = (curr_profit_amt / curr_bid * 100) if curr_bid > 0 else 0
        curr_oh_pct = (curr_overhead_amt / curr_bid * 100) if curr_bid > 0 else 0
        
        # Scenario simulation: factor scales the base cost, then markups apply
        sim_cost = self.base_cost * self.scenario_factor
        sim_overhead_amt = sim_cost * (self.scenario_overhead / 100.0)
        sim_profit_amt = sim_cost * (self.scenario_profit / 100.0)
        sim_bid = sim_cost + sim_overhead_amt + sim_profit_amt
        sim_margin_pct = (sim_profit_amt / sim_bid * 100) if sim_bid > 0 else 0
        sim_oh_pct = (sim_overhead_amt / sim_bid * 100) if sim_bid > 0 else 0
        
        # Update Cards
        self.card_bid.update_value(f"{self.currency_symbol}{sim_bid:,.2f}", f"Current: {self.currency_symbol}{curr_bid:,.2f}")
        self.card_profit.update_value(f"{self.currency_symbol}{sim_profit_amt:,.2f}", f"Current: {self.currency_symbol}{curr_profit_amt:,.2f}")
        self.card_margin.update_value(f"{sim_margin_pct:.2f}%", f"Current: {curr_margin_pct:.2f}%")
        self.card_overhead.update_value(f"{self.currency_symbol}{sim_overhead_amt:,.2f}", f"Current: {self.currency_symbol}{curr_overhead_amt:,.2f}")
        self.card_overhead_pct.update_value(f"{sim_oh_pct:.2f}%", f"Current: {curr_oh_pct:.2f}%")
        
        # Update Waterfall
        self.waterfall.currency_symbol = self.currency_symbol
        self.waterfall.set_data([
            ("Base Cost", sim_cost, "#0277bd"),
            ("Overhead", sim_overhead_amt, "#546e7a"),
            ("Profit", sim_profit_amt, "#ef6c00"),
            ("Final Bid", sim_bid, "#1b5e20")
        ])


    def apply_to_project(self):
        # Package the scenario figures as overrides for the Settings dialog
        overrides = {
            'overhead': self.scenario_overhead,
            'profit': self.scenario_profit,
            'factor': self.scenario_factor
        }
        
        # Robust detection of the MainWindow or parent with open_settings capability
        main_win = None
        curr = self
        while curr:
            if hasattr(curr, 'open_settings'):
                main_win = curr
                break
            if hasattr(curr, 'main_window') and curr.main_window:
                main_win = curr.main_window
                break
            curr = curr.parent()
            
        if main_win:
            main_win.open_settings(overrides=overrides)
            # After settings dialog closes (if saved), refresh the baseline
            self.load_baseline()
        else:
            QMessageBox.warning(self, "Error", "Could not locate main window to open settings.")


    def _to_float(self, val):
        if not val: return 0.0
        if isinstance(val, (int, float)): return float(val)
        try: return float(str(val).replace(',', '').replace(' ', '').replace('₵','').replace('$','').strip())
        except: return 0.0
