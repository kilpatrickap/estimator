import os
import sqlite3
import json
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QFrame, QGridLayout, QScrollArea, QSpacerItem, QSizePolicy)
from PyQt6.QtCore import Qt, pyqtSignal

from analytics_components import get_project_currency_symbol, MetricCard, SelectionFrame, DonutChart, ParetoBarChart
from pboq_logic import PBOQLogic

class ProjectPerformanceAnalytic(QWidget):
    """Analytic view for Project Performance."""
    def __init__(self, project_dir, parent=None):
        super().__init__(parent)
        self.project_dir = project_dir
        self.pboq_folder = os.path.join(self.project_dir, "Priced BOQs")
        self.currency_symbol = "$" # Default
        self._selected_row = None
        self._init_ui()
        self.refresh_data()

    def _init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        
        self.main_scroll = QScrollArea()
        self.main_scroll.setWidgetResizable(True)
        self.main_scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        self.content_widget = QWidget()
        self.content_widget.setStyleSheet("background-color: transparent;")
        self.layout = QVBoxLayout(self.content_widget)
        self.layout.setContentsMargins(20, 20, 20, 20)
        self.layout.setSpacing(15)
        
        # Header
        header_layout = QHBoxLayout()
        title_label = QLabel("Project Performance Analytics")
        title_label.setStyleSheet("font-size: 22px; font-weight: 800; color: #1b5e20;")
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        
        self.layout.addLayout(header_layout)
        
        # Headline Cards Grid
        self.cards_layout = QGridLayout()
        self.cards_layout.setSpacing(20)
        
        self.card_total_bid = MetricCard("Total Bid Value", f"{self.currency_symbol}0.00", "0 items priced", color="#1b5e20")
        self.card_progress = MetricCard("Pricing Progress", "0%", "0 of 0 completed", color="#0277bd")
        self.card_risk = MetricCard("Review Flags", "0", "High risk items detected", color="#c62828")
        self.card_confidence = MetricCard("Confidence Index", "N/A", "Pricing source analysis", color="#ef6c00")
        
        self.cards_layout.addWidget(self.card_total_bid, 0, 0)
        self.cards_layout.addWidget(self.card_progress, 0, 1)
        self.cards_layout.addWidget(self.card_risk, 0, 2)
        self.cards_layout.addWidget(self.card_confidence, 0, 3)
        
        self.layout.addLayout(self.cards_layout)
        
        # Charts Row
        self.charts_layout = QHBoxLayout()
        self.charts_layout.setSpacing(15)
        
        # 1. Donut Mix Chart
        donut_group = QFrame()
        donut_group.setStyleSheet("background-color: white; border-radius: 12px; border: 1px solid #e0e0e0;")
        donut_layout = QVBoxLayout(donut_group)
        donut_layout.setContentsMargins(15, 15, 15, 15)
        
        donut_title = QLabel("Pricing Mix (Value Distribution)")
        donut_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #333; margin-bottom: 5px;")
        donut_layout.addWidget(donut_title)
        
        self.mix_chart = DonutChart("Pricing Mix")
        donut_layout.addWidget(self.mix_chart)
        self.charts_layout.addWidget(donut_group, 1)
        
        # 2. Pareto Bar Chart
        bar_group = QFrame()
        bar_group.setStyleSheet("background-color: white; border-radius: 12px; border: 1px solid #e0e0e0;")
        bar_layout = QVBoxLayout(bar_group)
        bar_layout.setContentsMargins(15, 15, 15, 15)
        
        bar_title = QLabel("Price Type Values")
        bar_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #333; margin-bottom: 5px;")
        bar_layout.addWidget(bar_title)
        
        self.mix_bar_chart = ParetoBarChart("Price Type Analysis")
        bar_layout.addWidget(self.mix_bar_chart)
        self.charts_layout.addWidget(bar_group, 1)
        
        self.layout.addLayout(self.charts_layout)
        
        # Sectional Breakdown (Sheet Level)
        breakdown_group = QFrame()
        breakdown_group.setStyleSheet("background-color: white; border-radius: 12px; border: 1px solid #e0e0e0;")
        breakdown_layout = QVBoxLayout(breakdown_group)
        breakdown_layout.setContentsMargins(20, 20, 20, 20)
        
        label = QLabel("Sectional Summary (Sheet Breakdown)")
        label.setStyleSheet("font-size: 16px; font-weight: bold; color: #333; margin-bottom: 10px;")
        breakdown_layout.addWidget(label)
        
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setMinimumHeight(400)
        
        self.breakdown_container = QWidget()
        self.breakdown_list = QVBoxLayout(self.breakdown_container)
        self.breakdown_list.setSpacing(4)
        self.breakdown_list.setContentsMargins(0, 5, 0, 5)
        self.breakdown_list.addStretch()
        
        self.scroll_area.setWidget(self.breakdown_container)
        breakdown_layout.addWidget(self.scroll_area)
        
        self.layout.addWidget(breakdown_group)
        self.layout.addStretch()
        
        self.main_scroll.setWidget(self.content_widget)
        root_layout.addWidget(self.main_scroll)

    def _load_currency(self):
        """Discovers the project-wide currency symbol from the master project database."""
        self.currency_symbol = get_project_currency_symbol(self.project_dir) + " "

    def _load_project_settings(self):
        """Loads currency, overhead, and profit settings from the master database."""
        self._load_currency()
        self.overhead_rate = 0.0
        self.profit_rate = 0.0
        
        try:
            db_dir = os.path.join(self.project_dir, "Project Database")
            if os.path.exists(db_dir):
                dbs = [f for f in os.listdir(db_dir) if f.lower().endswith('.db') and "rates" not in f.lower()]
                if dbs:
                    db_path = os.path.join(db_dir, dbs[0])
                    conn = sqlite3.connect(db_path)
                    cursor = conn.cursor()
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

    def _to_float(self, val):
        if not val: return 0.0
        if isinstance(val, (int, float)): return float(val)
        try: return float(str(val).replace(',', '').replace(' ', '').replace('₵','').replace('$','').strip())
        except: return 0.0

    def _get_net_rate(self, rate_code):
        """Fetches the pure net total from the estimates database."""
        if not rate_code: return 0.0
        if not hasattr(self, '_rate_cache'): self._rate_cache = {}
        if rate_code in self._rate_cache: return self._rate_cache[rate_code]
        
        try:
            db_dir = os.path.join(self.project_dir, "Project Database")
            dbs = [f for f in os.listdir(db_dir) if f.lower().endswith('.db') and "rates" not in f.lower()]
            if not dbs: return 0.0
            
            db_path = os.path.join(db_dir, dbs[0])
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT net_total FROM estimates WHERE rate_code = ?", (rate_code,))
            res = cursor.fetchone()
            conn.close()
            
            if res:
                net = float(res[0] or 0.0)
                self._rate_cache[rate_code] = net
                return net
        except: pass
        
        self._rate_cache[rate_code] = 0.0
        return 0.0

    def refresh_data(self):
        """Aggregates data across all PBOQ databases accurately calculating Net Cost first."""
        self._load_project_settings()
        if not os.path.exists(self.pboq_folder):
            return

        total_net_cost = 0.0
        total_items = 0
        priced_items = 0
        flagged_items = 0
        
        sources_net = {
            'gross': 0.0, 
            'plug': 0.0, 
            'sub': 0.0, 
            'provisional': 0.0,
            'pc_sum': 0.0,
            'daywork': 0.0
        }
        sheet_net = {}
        sheet_stats = {}

        for f in os.listdir(self.pboq_folder):
            if f.lower().endswith('.db'):
                db_path = os.path.join(self.pboq_folder, f)
                
                qty_col_idx = -1
                desc_col_idx = -1
                bill_amt_col_idx = -1
                
                state_file = os.path.join(self.project_dir, "PBOQ States", f + ".json")
                if os.path.exists(state_file):
                    try:
                        with open(state_file, 'r') as sf:
                            state = json.load(sf)
                            m = state.get('mappings', {})
                            qty_col_idx = m.get('qty', -1)
                            desc_col_idx = m.get('desc', -1)
                            bill_amt_col_idx = m.get('bill_amount', -1)
                    except: pass
                    
                try:
                    conn = sqlite3.connect(db_path)
                    PBOQLogic.ensure_schema(conn)
                    cursor = conn.cursor()
                    cursor.execute("PRAGMA table_info(pboq_items)")
                    cols = [info[1] for info in cursor.fetchall()]
                    
                    qty_name = cols[qty_col_idx + 1] if qty_col_idx >= 0 and (qty_col_idx + 1) < len(cols) else next((c for c in cols if c.lower() in ["quantity", "qty"]), None)
                    desc_name = cols[desc_col_idx + 1] if desc_col_idx >= 0 and (desc_col_idx + 1) < len(cols) else next((c for c in cols if c.lower() in ["description", "desc"]), None)
                    bill_name = cols[bill_amt_col_idx + 1] if bill_amt_col_idx >= 0 and (bill_amt_col_idx + 1) < len(cols) else next((c for c in cols if c.lower() in ["bill amount", "billamount", "column 5"]), None)
                    
                    col_map = {
                        'sheet': next((c for c in cols if c.lower() == 'sheet'), None),
                        'desc': desc_name,
                        'qty': qty_name,
                        'bill': bill_name,
                        'gross': next((c for c in cols if c.lower() in ["grossrate", "gross_rate"]), None),
                        'plug': next((c for c in cols if c.lower() in ["plugrate", "plug_rate"]), None),
                        'sub': next((c for c in cols if c.lower() in ["subbeerate", "sub_rate"]), None),
                        'prov': next((c for c in cols if c.lower() in ["provsum", "prov_sum"]), None),
                        'pc': next((c for c in cols if c.lower() in ["pcsum", "pc_sum"]), None),
                        'dw': next((c for c in cols if c.lower() in ["daywork"]), None),
                        'flag': next((c for c in cols if c.lower() == "isflagged"), None),
                        'rcode': next((c for c in cols if c.lower() in ["ratecode", "rate_code"]), None),
                        'pcode': next((c for c in cols if c.lower() in ["plugcode", "plug_code"]), None)
                    }
                    
                    if not (col_map['desc'] and col_map['qty']):
                        continue
                        
                    query_cols = []
                    for k in ['sheet', 'desc', 'qty', 'bill', 'gross', 'plug', 'sub', 'prov', 'pc', 'dw', 'flag', 'rcode', 'pcode']:
                        if col_map[k]: query_cols.append(f"\"{col_map[k]}\"")
                        else: query_cols.append("''")
                        
                    cursor.execute(f"SELECT {', '.join(query_cols)} FROM pboq_items")
                    rows = cursor.fetchall()
                    
                    for r in rows:
                        sheet, desc, q, b, gross, plug, sub, prov, pc, dw, flag, rcode, pcode = r
                        desc_low = (desc or "").lower()
                        if not str(desc).strip() or "collection" in desc_low or "summary" in desc_low:
                            continue
                            
                        qty_f = self._to_float(q)
                        bill_f = self._to_float(b)
                        
                        if qty_f == 0 and bill_f == 0:
                            continue
                        
                        g_val = self._to_float(gross)
                        p_val = self._to_float(plug)
                        s_val = self._to_float(sub)
                        pr_val = self._to_float(prov)
                        pc_val = self._to_float(pc)
                        d_val = self._to_float(dw)
                        
                        is_priced = (g_val > 0 or p_val > 0 or s_val > 0 or pr_val > 0 or pc_val > 0 or d_val > 0 or bill_f > 0)
                        
                        active_code = pcode if pcode and str(pcode).strip() else rcode
                        master_net_cost = self._get_net_rate(active_code) if active_code else 0.0
                        
                        unit_cost = 0.0
                        src = None
                        
                        if pr_val > 0: unit_cost = pr_val; src = 'provisional'
                        elif pc_val > 0: unit_cost = pc_val; src = 'pc_sum'
                        elif d_val > 0: unit_cost = d_val; src = 'daywork'
                        elif master_net_cost > 0: unit_cost = master_net_cost; src = 'gross'
                        else:
                            if p_val > 0: unit_cost = p_val; src = 'plug'
                            elif s_val > 0: unit_cost = s_val; src = 'sub'
                            elif g_val > 0: unit_cost = g_val; src = 'gross'
                            else:
                                if bill_f > 0:
                                    unit_cost = bill_f if qty_f <= 1 else 0.0
                                    src = 'gross'
                                
                        calc_qty = qty_f if qty_f > 0 else (1.0 if bill_f > 0 else 0.0)
                        item_net_cost = round(unit_cost * calc_qty, 2)
                        
                        total_items += 1
                        if is_priced: priced_items += 1
                        total_net_cost += item_net_cost
                        
                        if src:
                            sources_net[src] += item_net_cost
                            
                        if flag and str(flag) == '1':
                            flagged_items += 1
                            
                        sheet_key = f"{f.replace('.db', '')} - {sheet}"
                        if sheet_key not in sheet_net:
                            sheet_net[sheet_key] = 0.0
                            sheet_stats[sheet_key] = {'total': 0, 'priced': 0}
                            
                        sheet_net[sheet_key] += item_net_cost
                        sheet_stats[sheet_key]['total'] += 1
                        if is_priced: sheet_stats[sheet_key]['priced'] += 1
                        
                    conn.close()
                except Exception as e:
                    print(f"Error processing {f}: {e}")

        # Apply exact combined markups for parity with Financial Executive
        combined_markup_pct = (self.overhead_rate + self.profit_rate) / 100.0
        total_bid = total_net_cost * (1.0 + combined_markup_pct)
        
        sources = {k: v * (1.0 + combined_markup_pct) for k, v in sources_net.items()}
        
        sheet_data = []
        for k, net_val in sheet_net.items():
            sheet_data.append({
                'name': k,
                'amount': net_val * (1.0 + combined_markup_pct),
                'total': sheet_stats[k]['total'],
                'priced': sheet_stats[k]['priced']
            })
        
        self.card_total_bid.update_value(f"{self.currency_symbol}{total_bid:,.2f}", f"Total cross-project value")
        
        progress_pct = (priced_items / total_items * 100) if total_items > 0 else 0
        self.card_progress.update_value(f"{progress_pct:.2f}%", f"{priced_items} of {total_items} items priced")
        
        self.card_risk.update_value(str(flagged_items), "Items flagged for review")
        
        confidence = "N/A"
        lib_pct = 0
        total_priced_val = sum(sources.values())
        if total_priced_val > 0:
            lib_pct = (sources['gross'] / total_priced_val * 100)
            if lib_pct > 70: confidence = "HIGH"
            elif lib_pct > 40: confidence = "MEDIUM"
            else: confidence = "LOW"
        self.card_confidence.update_value(confidence, f"{int(lib_pct)}% from Gross Rates")

        # Update Donut Chart
        chart_data = [
            ("Gross Rates", sources['gross'], "#2e7d32"),
            ("Plug Rates", sources['plug'], "#0277bd"),
            ("Subcontractor", sources['sub'], "#ef6c00"),
            ("Prov. Sums", sources['provisional'], "#c62828"),
            ("PC Sums", sources['pc_sum'], "#6a1b9a"),
            ("Dayworks", sources['daywork'], "#37474f")
        ]
        self.mix_chart.set_data(chart_data)
        
        # Update Bar Chart (Sorted by value for Pareto effect)
        sorted_bar_data = sorted(chart_data, key=lambda x: x[1], reverse=True)
        self.mix_bar_chart.set_data(sorted_bar_data)

        self._clear_breakdown()
        for s in sheet_data:
            self._add_sheet_row(s)
            
        if sheet_data:
            self._add_sheet_row({
                'name': 'TOTAL PROJECT SUMMARY',
                'priced': priced_items,
                'total': total_items,
                'amount': total_bid
            }, is_total=True)

    def _clear_breakdown(self):
        while self.breakdown_list.count() > 1:
            item = self.breakdown_list.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _add_sheet_row(self, data, is_total=False):
        row = SelectionFrame()
        row.setObjectName("breakdownRow")
        
        bg_color = "#f1f8e9" if is_total else "transparent"
        border_color = "#2e7d32" if is_total else "transparent"
        hover_bg = "#f5f5f5" if not is_total else "#f1f8e9"
        
        row.setStyleSheet(f"""
            QFrame#breakdownRow {{
                background-color: {bg_color}; 
                border-radius: 6px; 
                border: 1px solid {border_color};
            }}
            QFrame#breakdownRow:hover {{
                background-color: {hover_bg};
            }}
            QFrame#breakdownRow[selected="true"] {{
                background-color: #fffde7;
                border: 1px solid #fbc02d;
            }}
        """)
        row.setProperty("selected", "false")
        
        l = QHBoxLayout(row)
        l.setContentsMargins(10, 5, 10, 5)
        l.setSpacing(15)
        
        # Sheet Name 'Pill' (Responsive Column 1)
        name_container = QFrame()
        name_bg = "white" if is_total else "#f1f3f4"
        name_container.setStyleSheet(f"background-color: {name_bg}; border-radius: 4px; padding: 2px;")
        name_container.setMinimumWidth(650)
        nc_layout = QHBoxLayout(name_container)
        nc_layout.setContentsMargins(8, 2, 8, 2)
        
        name = QLabel(data['name'])
        font_weight = "800" if is_total else "600"
        name.setStyleSheet(f"font-weight: {font_weight}; color: #3c4043; font-size: 8.5pt; border: none;")
        name.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        nc_layout.addWidget(name)
        
        # Progress (Column 2)
        progress = QLabel(f"{data['priced']}/{data['total']} items")
        progress_color = "#1b5e20" if is_total else "#70757a"
        progress_weight = "bold" if is_total else "normal"
        progress.setStyleSheet(f"color: {progress_color}; font-size: 8pt; font-family: 'Segoe UI'; font-weight: {progress_weight};")
        # Let it scale or keep it compact
        progress.setMinimumWidth(80)
        progress.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Amount Capsule (Position: Between Description and Items)
        amount_container = QFrame()
        amount_bg = "white" if is_total else "#f1f3f4"
        amount_container.setStyleSheet(f"background-color: {amount_bg}; border-radius: 4px; padding: 2px;")
        amount_container.setMinimumWidth(180)
        ac_layout = QHBoxLayout(amount_container)
        ac_layout.setContentsMargins(8, 2, 8, 2)
        
        amount = QLabel(f"{self.currency_symbol}{data['amount']:,.2f}")
        amount.setStyleSheet("font-weight: 700; color: #1b5e20; font-size: 9pt; font-family: 'Consolas'; border: none; background: transparent;")
        amount.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        ac_layout.addWidget(amount)
        
        l.addWidget(name_container, 6)  # High stretch for sheet name
        l.addWidget(amount_container, 2) # Medium stretch for amount
        l.addWidget(progress, 1)         # Small stretch for counts
        l.addStretch(1)                  # Balancing stretch
        
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
        
        self.breakdown_list.insertWidget(self.breakdown_list.count() - 1, row)
