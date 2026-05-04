import os
import sqlite3
import json
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QFrame, QScrollArea, QSpacerItem, QSizePolicy)
from PyQt6.QtCore import Qt
from analytics_components import MetricCard, DonutChart, ParetoBarChart, ChartWidget

class LogisticsRow(QFrame):
    def __init__(self, name, unit, qty, rate, amount, is_header=False, is_total=False, parent=None):
        super().__init__(parent)
        bg = "#f8fafc" if is_header else ("#f1f8e9" if is_total else "#ffffff")
        border = "#cbd5e1" if is_header else ("#2e7d32" if is_total else "#e2e8f0")
        
        self.setStyleSheet(f"""
            QFrame {{ background-color: {bg}; border-radius: 8px; border: 1px solid {border}; }}
            QFrame:hover {{ background-color: #f8fafc; border: 1px solid #cbd5e1; }}
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 8, 15, 8)
        layout.setSpacing(15)
        
        style = "font-family: 'Inter'; font-size: 12px; color: #1e293b;"
        if is_header:
            style = "font-family: 'Inter'; font-weight: 700; color: #64748b; font-size: 11px; text-transform: uppercase;"
        elif is_total:
            style = "font-family: 'Inter'; font-weight: 800; color: #1b5e20; font-size: 13px;"
            
        # 1. Name
        name_lbl = QLabel(name)
        name_lbl.setStyleSheet(style + " border: none;")
        name_lbl.setWordWrap(True)
        name_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        name_lbl.setToolTip(name)
        layout.addWidget(name_lbl, 6)
        
        # 2. Unit Pill
        unit_pill = QFrame()
        unit_pill.setStyleSheet("background-color: #f1f5f9; border-radius: 4px; padding: 2px 4px;")
        up_layout = QHBoxLayout(unit_pill)
        up_layout.setContentsMargins(4, 2, 4, 2)
        u_lbl = QLabel(unit)
        u_lbl.setStyleSheet("font-family: 'Inter'; font-weight: 700; color: #475569; font-size: 11px;")
        u_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        up_layout.addWidget(u_lbl)
        if is_header: unit_pill.setStyleSheet("background-color: transparent; border: none;")
        layout.addWidget(unit_pill, 1)
        
        # 3. Qty Pill
        qty_pill = QFrame()
        qty_pill.setStyleSheet("background-color: #eff6ff; border-radius: 4px; padding: 2px 8px;")
        qp_layout = QHBoxLayout(qty_pill)
        qp_layout.setContentsMargins(5, 2, 5, 2)
        qty_str = f"{qty:,.2f}" if not is_header else qty
        q_lbl = QLabel(qty_str)
        q_lbl.setStyleSheet("font-family: 'Consolas'; font-weight: 700; color: #1e40af; font-size: 12px;")
        if is_header: q_lbl.setStyleSheet(style)
        q_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        qp_layout.addWidget(q_lbl)
        if is_header: qty_pill.setStyleSheet("background-color: transparent; border: none;")
        layout.addWidget(qty_pill, 2)
        
        # 4. Rate Pill
        rate_pill = QFrame()
        rate_pill.setStyleSheet("background-color: #fffbeb; border-radius: 4px; padding: 2px 8px;")
        rp_layout = QHBoxLayout(rate_pill)
        rp_layout.setContentsMargins(5, 2, 5, 2)
        rate_str = f"$ {rate:,.2f}" if not is_header else rate
        r_lbl = QLabel(rate_str)
        r_lbl.setStyleSheet("font-family: 'Consolas'; font-weight: 700; color: #b45309; font-size: 12px;")
        if is_header: r_lbl.setStyleSheet(style)
        r_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        rp_layout.addWidget(r_lbl)
        if is_header: rate_pill.setStyleSheet("background-color: transparent; border: none;")
        layout.addWidget(rate_pill, 2)
        
        # 5. Amount Pill
        amt_pill = QFrame()
        amt_pill.setStyleSheet("background-color: #f0fdf4; border-radius: 4px; padding: 2px 8px;")
        ap_layout = QHBoxLayout(amt_pill)
        ap_layout.setContentsMargins(5, 2, 5, 2)
        amount_str = f"$ {amount:,.2f}" if not is_header else amount
        a_lbl = QLabel(amount_str)
        a_lbl.setStyleSheet("font-family: 'Consolas'; font-weight: 700; color: #166534; font-size: 12px;")
        if is_header: a_lbl.setStyleSheet(style)
        a_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ap_layout.addWidget(a_lbl)
        if is_header: amt_pill.setStyleSheet("background-color: transparent; border: none;")
        layout.addWidget(amt_pill, 2)

class ProcurementLogisticsAnalytic(QWidget):
    def __init__(self, project_dir, parent=None):
        super().__init__(parent)
        self.project_dir = project_dir
        self.pboq_folder = os.path.join(project_dir, "Priced BOQs")
        self.pj_db_dir = os.path.join(project_dir, "Project Database")
        self.pboq_state_dir = os.path.join(project_dir, "PBOQ States")
        
        self.currency_symbol = "$"
        self._init_ui()
        self.refresh_data()

    def _init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(20, 20, 20, 20)
        root_layout.setSpacing(20)

        # Header
        header = QLabel("Operational & Procurement Logistics")
        header.setStyleSheet("font-family: 'Inter'; font-size: 24px; font-weight: 800; color: #1e293b;")
        root_layout.addWidget(header)

        # Scroll Area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setSpacing(25)
        
        # 1. KPI Row
        kpi_layout = QHBoxLayout()
        self.card_mat_total = MetricCard("TOTAL MATERIAL VALUE", "$ 0.00", "Procurement budget")
        self.card_lab_total = MetricCard("TOTAL LABOR VALUE", "$ 0.00", "Workforce budget")
        self.card_pkg_count = MetricCard("PROCUREMENT PACKAGES", "0", "Vendor packages")
        self.card_completion = MetricCard("PROCUREMENT STATUS", "0%", "Allocated to subs")
        
        for c in [self.card_mat_total, self.card_lab_total, self.card_pkg_count, self.card_completion]:
            kpi_layout.addWidget(c)
        self.content_layout.addLayout(kpi_layout)

        # 2. Charts Row
        charts_layout = QHBoxLayout()
        self.res_split_chart = DonutChart("Resource Value Split")
        self.top_mat_chart = ParetoBarChart("Top 10 Procurement Items")
        
        charts_layout.addWidget(self._create_card_frame("RESOURCE SPLIT", self.res_split_chart), 1)
        charts_layout.addWidget(self._create_card_frame("TOP PROCUREMENT DRIVERS", self.top_mat_chart), 1)
        self.content_layout.addLayout(charts_layout)

        # 3. Bill of Materials (BOM) Table
        bom_frame = QFrame()
        bom_frame.setStyleSheet("background-color: white; border-radius: 16px; border: 1px solid #e2e8f0;")
        bom_vbox = QVBoxLayout(bom_frame)
        bom_vbox.setContentsMargins(20, 20, 20, 20)
        
        bom_header = QLabel("Operational Bill of Materials (BOM)")
        bom_header.setStyleSheet("font-family: 'Inter'; font-size: 16px; font-weight: 700; color: #1e293b;")
        bom_vbox.addWidget(bom_header)
        
        self.bom_list = QVBoxLayout()
        self.bom_list.setSpacing(5)
        self.bom_list.addStretch()
        
        self.bom_scroll = QScrollArea()
        self.bom_scroll.setFixedHeight(400)
        self.bom_scroll.setWidgetResizable(True)
        self.bom_scroll.setStyleSheet("border: none;")
        self.bom_container = QWidget()
        self.bom_container.setLayout(self.bom_list)
        self.bom_scroll.setWidget(self.bom_container)
        
        bom_vbox.addWidget(self.bom_scroll)
        self.content_layout.addWidget(bom_frame)

        # Final setup
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

    def refresh_data(self):
        """Heavy duty data extraction for procurement logistics."""
        all_materials = {} # name -> {qty, unit, total_cost}
        all_labor = {} # name -> {qty, unit, total_cost}
        sub_alloc = 0.0
        total_value = 0.0
        
        files = [f for f in os.listdir(self.pboq_folder) if f.lower().endswith('.db')]
        
        # 1. Get Rate Codes from PBOQs
        rate_codes = []
        for f in files:
            try:
                db_path = os.path.join(self.pboq_folder, f)
                mapping = self._get_pboq_mapping(f)
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                
                # We need qty and rate code
                cursor.execute("PRAGMA table_info(pboq_items)")
                cols = [info[1] for info in cursor.fetchall()]
                q_idx = mapping.get('qty')
                r_idx = mapping.get('rate_code')
                s_idx = mapping.get('sub_rate') # To check sub allocation
                
                if q_idx is None or r_idx is None: 
                    conn.close()
                    continue
                    
                q_col = cols[q_idx + 1]
                r_col = cols[r_idx + 1]
                s_col = cols[s_idx + 1] if s_idx is not None else None
                
                query = f"SELECT \"{q_col}\", \"{r_col}\", \"{s_col if s_col else 'Sheet'}\" FROM pboq_items"
                cursor.execute(query)
                for q_val, r_code, s_val in cursor.fetchall():
                    if not r_code: continue
                    qty = self._to_float(q_val)
                    sub_val = self._to_float(s_val) if s_col else 0.0
                    rate_codes.append((str(r_code).strip(), qty, sub_val))
                conn.close()
            except Exception as e:
                print(f"Error reading PBOQ {f}: {e}")

        # 2. Extract Resources from Project DB
        try:
            pj_dbs = [f for f in os.listdir(self.pj_db_dir) if f.lower().endswith('.db') and 'rates' not in f.lower()]
            if pj_dbs:
                db_path = os.path.join(self.pj_db_dir, pj_dbs[0])
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                
                for r_code, boq_qty, s_val in rate_codes:
                    # Get Estimate ID
                    cursor.execute("SELECT id, net_total FROM estimates WHERE rate_code = ?", (r_code,))
                    res = cursor.fetchone()
                    if not res: continue
                    est_id, net_total = res
                    
                    # Accumulate Sub-Contract Value (If plug-subbed)
                    if s_val > 0:
                        sub_alloc += s_val * boq_qty
                    
                    # Materials
                    cursor.execute("""
                        SELECT name, unit, quantity, price FROM estimate_materials 
                        WHERE task_id IN (SELECT id FROM tasks WHERE estimate_id = ?)
                    """, (est_id,))
                    for m_name, m_unit, m_qty, m_price in cursor.fetchall():
                        m_total_qty = (m_qty or 0) * boq_qty
                        m_total_cost = m_total_qty * (m_price or 0)
                        
                        key = f"{m_name} ({m_unit})"
                        if key not in all_materials:
                            all_materials[key] = {'name': m_name, 'unit': m_unit, 'qty': 0.0, 'cost': 0.0}
                        all_materials[key]['qty'] += m_total_qty
                        all_materials[key]['cost'] += m_total_cost

                    # Labor
                    cursor.execute("""
                        SELECT name_trade, unit, hours, rate FROM estimate_labor 
                        WHERE task_id IN (SELECT id FROM tasks WHERE estimate_id = ?)
                    """, (est_id,))
                    for l_name, l_unit, l_hours, l_rate in cursor.fetchall():
                        l_total_hours = (l_hours or 0) * boq_qty
                        l_total_cost = l_total_hours * (l_rate or 0)
                        
                        key = f"{l_name} ({l_unit})"
                        if key not in all_labor:
                            all_labor[key] = {'name': l_name, 'unit': l_unit, 'qty': 0.0, 'cost': 0.0}
                        all_labor[key]['qty'] += l_total_hours
                        all_labor[key]['cost'] += l_total_cost
                        
                conn.close()
        except Exception as e:
            print(f"Error reading Project DB: {e}")

        # 3. Update UI
        mat_total = sum(v['cost'] for v in all_materials.values())
        lab_total = sum(v['cost'] for v in all_labor.values())
        total_proc = mat_total + lab_total + sub_alloc
        
        self.card_mat_total.update_value(f"{self.currency_symbol}{mat_total:,.2f}")
        self.card_lab_total.update_value(f"{self.currency_symbol}{lab_total:,.2f}")
        self.card_pkg_count.update_value(str(len(all_materials)))
        
        perc = (sub_alloc / total_proc * 100) if total_proc > 0 else 0
        self.card_completion.update_value(f"{perc:.1f}% Allocated")
        
        # Charts
        self.res_split_chart.set_data([
            ("Materials", mat_total, "#2e7d32"),
            ("Labor", lab_total, "#0277bd"),
            ("Sub-Contract", sub_alloc, "#7e57c2")
        ])
        
        top_10 = sorted(all_materials.values(), key=lambda x: x['cost'], reverse=True)[:10]
        self.top_mat_chart.set_data([(v['name'], v['cost'], "#43a047") for v in top_10])
        
        # Populate BOM Table
        self._clear_table(self.bom_list)
        self.bom_list.insertWidget(0, LogisticsRow("RESOURCE NAME", "UNIT", "TOTAL QTY", "AVG RATE", "EST. TOTAL", is_header=True))
        
        sorted_mats = sorted(all_materials.values(), key=lambda x: x['cost'], reverse=True)
        for m in sorted_mats:
            avg_rate = m['cost'] / m['qty'] if m['qty'] > 0 else 0
            r = LogisticsRow(m['name'], m['unit'], m['qty'], avg_rate, m['cost'])
            self.bom_list.insertWidget(self.bom_list.count() - 1, r)
            
        if sorted_mats:
            self.bom_list.insertWidget(self.bom_list.count() - 1, LogisticsRow("TOTAL OPERATIONAL MATERIAL VALUE", "", 0, 0, mat_total, is_total=True))

    def _get_pboq_mapping(self, filename):
        state_path = os.path.join(self.pboq_state_dir, filename + ".json")
        if os.path.exists(state_path):
            with open(state_path, 'r') as f:
                data = json.load(f)
                return data.get('mappings', {})
        return {}

    def _to_float(self, val):
        if not val: return 0.0
        try: return float(str(val).replace(',', '').replace(' ', '').replace('₵','').replace('$','').strip())
        except: return 0.0

    def _clear_table(self, layout):
        while layout.count() > 1:
            it = layout.takeAt(0)
            if it.widget(): it.widget().deleteLater()
