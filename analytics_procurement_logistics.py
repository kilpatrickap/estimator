import os
import sqlite3
import json
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QFrame, QScrollArea, QSpacerItem, QSizePolicy)
from PyQt6.QtCore import Qt, pyqtSignal
from analytics_components import MetricCard, DonutChart, ParetoBarChart, ChartWidget

class LogisticsRow(QFrame):
    clicked = pyqtSignal(object)

    def __init__(self, name, unit, qty, rate, amount, is_header=False, is_total=False, parent=None):
        super().__init__(parent)
        self.is_header = is_header
        self.is_total = is_total
        self.is_selected = False
        self._update_style()
        
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
        unit_pill.setStyleSheet("background-color: #f1f5f9; border-radius: 4px; border: 1px solid #475569;")
        up_layout = QHBoxLayout(unit_pill)
        up_layout.setContentsMargins(4, 2, 4, 2)
        u_lbl = QLabel(unit)
        u_lbl.setStyleSheet("font-family: 'Inter'; font-weight: 700; color: #475569; font-size: 11px; border: none;")
        u_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        up_layout.addWidget(u_lbl)
        if is_header or is_total: unit_pill.setStyleSheet("background-color: transparent; border: none;")
        layout.addWidget(unit_pill, 1)
        
        # 3. Qty Pill
        q_border = "#1e40af" if not is_total else "none"
        qty_pill = QFrame()
        qty_pill.setStyleSheet(f"background-color: #eff6ff; border-radius: 4px; border: 1px solid {q_border};")
        qp_layout = QHBoxLayout(qty_pill)
        qp_layout.setContentsMargins(5, 2, 5, 2)
        qty_str = f"{qty:,.2f}" if not is_header else qty
        q_lbl = QLabel(qty_str)
        q_lbl.setStyleSheet("font-family: 'Consolas'; font-weight: 700; color: #1e40af; font-size: 12px; border: none;")
        if is_header: q_lbl.setStyleSheet(style)
        q_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        qp_layout.addWidget(q_lbl)
        if is_header: qty_pill.setStyleSheet("background-color: transparent; border: none;")
        layout.addWidget(qty_pill, 2)
        
        # 4. Rate Pill
        r_border = "#b45309" if not is_total else "none"
        rate_pill = QFrame()
        rate_pill.setStyleSheet(f"background-color: #fffbeb; border-radius: 4px; border: 1px solid {r_border};")
        rp_layout = QHBoxLayout(rate_pill)
        rp_layout.setContentsMargins(5, 2, 5, 2)
        rate_str = f"$ {rate:,.2f}" if not is_header else rate
        r_lbl = QLabel(rate_str)
        r_lbl.setStyleSheet("font-family: 'Consolas'; font-weight: 700; color: #b45309; font-size: 12px; border: none;")
        if is_header: r_lbl.setStyleSheet(style)
        r_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        rp_layout.addWidget(r_lbl)
        if is_header: rate_pill.setStyleSheet("background-color: transparent; border: none;")
        layout.addWidget(rate_pill, 2)
        
        # 5. Amount Pill
        a_border = "#166534" if not is_total else "none"
        amt_pill = QFrame()
        amt_pill.setStyleSheet(f"background-color: #f0fdf4; border-radius: 4px; border: 1px solid {a_border};")
        ap_layout = QHBoxLayout(amt_pill)
        ap_layout.setContentsMargins(5, 2, 5, 2)
        amount_str = f"$ {amount:,.2f}" if not is_header else amount
        a_lbl = QLabel(amount_str)
        a_lbl.setStyleSheet("font-family: 'Consolas'; font-weight: 700; color: #166534; font-size: 12px; border: none;")
        if is_header: a_lbl.setStyleSheet(style)
        a_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ap_layout.addWidget(a_lbl)
        if is_header: amt_pill.setStyleSheet("background-color: transparent; border: none;")
        layout.addWidget(amt_pill, 2)

    def _update_style(self):
        if self.is_header:
            bg, border = "#f8fafc", "#cbd5e1"
        elif self.is_total or self.is_selected:
            bg, border = "#f1f8e9", "#2e7d32"
        else:
            bg, border = "#ffffff", "#e2e8f0"
            
        hover_bg = "#ecfdf5" if not (self.is_header or self.is_total) else bg
        
        self.setStyleSheet(f"""
            LogisticsRow {{ background-color: {bg}; border-radius: 8px; border: 1px solid {border}; }}
            LogisticsRow:hover {{ background-color: {hover_bg}; border: 1px solid #2e7d32; }}
        """)

    def set_selected(self, selected):
        if self.is_header or self.is_total: return
        self.is_selected = selected
        self._update_style()

    def mousePressEvent(self, event):
        if not self.is_header and event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self)
        super().mousePressEvent(event)

class PackageRow(QFrame):
    clicked = pyqtSignal(object)

    def __init__(self, name, subbee, amount, is_header=False, is_total=False, parent=None):
        super().__init__(parent)
        self.is_header = is_header
        self.is_total = is_total
        self.is_selected = False
        self._update_style()
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 10, 15, 10)
        layout.setSpacing(15)
        
        style = "font-family: 'Inter'; font-size: 12px; color: #1e293b;"
        if is_header:
            style = "font-family: 'Inter'; font-weight: 700; color: #64748b; font-size: 11px; text-transform: uppercase;"
        elif is_total:
            style = "font-family: 'Inter'; font-weight: 800; color: #0369a1; font-size: 13px;"
            
        # Package Name
        name_lbl = QLabel(name)
        name_lbl.setStyleSheet(style + " border: none;")
        name_lbl.setWordWrap(True)
        layout.addWidget(name_lbl, 5)
        
        # Sub-Contractor
        s_border = "#1e40af" if not is_total else "none"
        sub_pill = QFrame()
        sub_pill.setObjectName("SubPill")
        sub_pill.setStyleSheet(f"QFrame#SubPill {{ background-color: #f8fafc; border-radius: 4px; border: 1px solid {s_border}; }}")
        sp_layout = QHBoxLayout(sub_pill)
        sp_layout.setContentsMargins(4, 2, 4, 2)
        s_lbl = QLabel(subbee)
        s_lbl.setStyleSheet("font-family: 'Inter'; font-weight: 600; color: #1e40af; border: none;")
        if is_header: s_lbl.setStyleSheet(style + " border: none;")
        s_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sp_layout.addWidget(s_lbl)
        if is_header: sub_pill.setStyleSheet("background-color: transparent; border: none;")
        layout.addWidget(sub_pill, 4)
        
        # Value Pill
        v_border = "#166534" if not is_total else "none"
        val_pill = QFrame()
        val_pill.setStyleSheet(f"background-color: #f0f9ff; border-radius: 4px; border: 1px solid {v_border};")
        vp_layout = QHBoxLayout(val_pill)
        vp_layout.setContentsMargins(8, 2, 8, 2)
        val_str = f"$ {amount:,.2f}" if not is_header else amount
        v_lbl = QLabel(val_str)
        v_lbl.setStyleSheet("font-family: 'Consolas'; font-weight: 700; color: #166534; font-size: 12px; border: none;")
        if is_header: v_lbl.setStyleSheet(style)
        v_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vp_layout.addWidget(v_lbl)
        if is_header: val_pill.setStyleSheet("background-color: transparent; border: none;")
        layout.addWidget(val_pill, 3)
        
        # Status Badge
        status_pill = QFrame()
        status_pill.setStyleSheet("background-color: transparent; border: none;")
        stp_layout = QHBoxLayout(status_pill)
        stp_layout.setContentsMargins(4, 2, 4, 2)
        
        status = "ALLOCATED" if not is_header and not is_total else ("STATUS" if is_header else "")
        status_lbl = QLabel(status)
        if not is_header and not is_total:
            status_lbl.setStyleSheet("background-color: #f0fdf4; color: #166534; border-radius: 4px; padding: 4px 8px; font-weight: 800; font-size: 10px; border: none;")
        else:
            status_lbl.setStyleSheet(style + " border: none;")
        status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        stp_layout.addWidget(status_lbl)
        layout.addWidget(status_pill, 2)

    def _update_style(self):
        if self.is_header:
            bg, border = "#f8fafc", "#cbd5e1"
        elif self.is_total or self.is_selected:
            bg, border = "#f1f8e9", "#2e7d32"
        else:
            bg, border = "#ffffff", "#e2e8f0"
            
        hover_bg = "#ecfdf5" if not (self.is_header or self.is_total) else bg
        
        self.setStyleSheet(f"""
            PackageRow {{ background-color: {bg}; border-radius: 8px; border: 1px solid {border}; }}
            PackageRow:hover {{ background-color: {hover_bg}; border: 1px solid #2e7d32; }}
        """)

    def set_selected(self, selected):
        if self.is_header or self.is_total: return
        self.is_selected = selected
        self._update_style()

    def mousePressEvent(self, event):
        if not self.is_header and event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self)
        super().mousePressEvent(event)

class ProcurementLogisticsAnalytic(QWidget):
    def __init__(self, project_dir, parent=None):
        super().__init__(parent)
        self.project_dir = project_dir
        self.pboq_folder = os.path.join(project_dir, "Priced BOQs")
        self.pj_db_dir = os.path.join(project_dir, "Project Database")
        self.pboq_state_dir = os.path.join(project_dir, "PBOQ States")
        self._selected_row = None
        
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

        # 4. Sub-Contractor Package Schedule
        sub_frame = QFrame()
        sub_frame.setStyleSheet("background-color: white; border-radius: 16px; border: 1px solid #e2e8f0;")
        sub_vbox = QVBoxLayout(sub_frame)
        sub_vbox.setContentsMargins(20, 20, 20, 20)
        
        sub_header = QLabel("Sub-Contractor Package Schedule")
        sub_header.setStyleSheet("font-family: 'Inter'; font-size: 16px; font-weight: 700; color: #1e293b;")
        sub_vbox.addWidget(sub_header)
        
        self.pkg_list = QVBoxLayout()
        self.pkg_list.setSpacing(5)
        self.pkg_list.addStretch()
        
        self.pkg_scroll = QScrollArea()
        self.pkg_scroll.setFixedHeight(300)
        self.pkg_scroll.setWidgetResizable(True)
        self.pkg_scroll.setStyleSheet("border: none;")
        self.pkg_container = QWidget()
        self.pkg_container.setLayout(self.pkg_list)
        self.pkg_scroll.setWidget(self.pkg_container)
        
        sub_vbox.addWidget(self.pkg_scroll)
        self.content_layout.addWidget(sub_frame)

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
                # We need qty, rate code, sub info
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info(pboq_items)")
                cols = [info[1] for info in cursor.fetchall()]
                q_idx = mapping.get('qty')
                r_idx = mapping.get('rate_code')
                s_idx = mapping.get('sub_rate')
                p_idx = mapping.get('sub_package')
                n_idx = mapping.get('sub_name')
                
                if q_idx is None: 
                    conn.close()
                    continue
                    
                q_col = cols[q_idx + 1]
                r_col = cols[r_idx + 1] if r_idx is not None else "Sheet"
                s_col = cols[s_idx + 1] if s_idx is not None else None
                p_col = cols[p_idx + 1] if p_idx is not None else None
                n_col = cols[n_idx + 1] if n_idx is not None else None
                
                cols_to_sel = [q_col, r_col]
                cols_to_sel.append(s_col if s_col else "'0.0'")
                cols_to_sel.append(p_col if p_col else "'Uncategorized'")
                cols_to_sel.append(n_col if n_col else "'Open'")
                
                query = f"SELECT \"{cols_to_sel[0]}\", \"{cols_to_sel[1]}\", \"{cols_to_sel[2]}\", \"{cols_to_sel[3]}\", \"{cols_to_sel[4]}\" FROM pboq_items"
                cursor.execute(query)
                for q_val, r_code, s_val, p_val, n_val in cursor.fetchall():
                    qty = self._to_float(q_val)
                    sub_rate = self._to_float(s_val)
                    # We keep the item if it has a sub rate OR a rate code
                    if sub_rate > 0 or (r_code and r_code != 'Sheet'):
                        rate_codes.append({
                            'r_code': str(r_code or "").strip(),
                            'qty': qty,
                            'sub_rate': sub_rate,
                            'package': str(p_val or "Uncategorized").strip(),
                            'subbee': str(n_val or "Open").strip()
                        })
                conn.close()
            except Exception as e:
                print(f"Error reading PBOQ {f}: {e}")

        # 2. Extract Resources from Project DB
        all_packages = {} # (package, subbee) -> amount
        try:
            pj_dbs = [f for f in os.listdir(self.pj_db_dir) if f.lower().endswith('.db') and 'rates' not in f.lower()]
            if pj_dbs:
                db_path = os.path.join(self.pj_db_dir, pj_dbs[0])
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                
                for item in rate_codes:
                    r_code = item['r_code']
                    boq_qty = item['qty']
                    s_rate = item['sub_rate']
                    pkg_name = item['package']
                    sub_name = item['subbee']
                    
                    # Case 1: Sub-Contracted Item
                    if s_rate > 0:
                        amt = s_rate * boq_qty
                        sub_alloc += amt
                        
                        key = (pkg_name, sub_name)
                        if key not in all_packages: all_packages[key] = 0.0
                        all_packages[key] += amt
                        continue 
                    
                    # Case 2: Self-Performed Item
                    if not r_code or r_code == 'Sheet': continue
                    
                    cursor.execute("SELECT id FROM estimates WHERE rate_code = ?", (r_code,))
                    res = cursor.fetchone()
                    if not res: continue
                    est_id = res[0]
                    
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
        self.res_split_chart.currency_symbol = self.currency_symbol
        self.top_mat_chart.currency_symbol = self.currency_symbol
        
        self.res_split_chart.set_data([
            ("Materials", mat_total, "#2e7d32"),
            ("Labor", lab_total, "#0277bd"),
            ("Sub-Contract", sub_alloc, "#7e57c2")
        ])
        
        top_10 = sorted(all_materials.values(), key=lambda x: x['cost'], reverse=True)[:10]
        self.top_mat_chart.set_data([(v['name'], v['cost'], "#43a047") for v in top_10])
        
        # Populate BOM Table
        self._clear_table(self.bom_list)
        self._add_bom_row(("RESOURCE NAME", "UNIT", "TOTAL QTY", "AVG RATE", "EST. TOTAL"), is_header=True)
        
        sorted_mats = sorted(all_materials.values(), key=lambda x: x['cost'], reverse=True)
        for m in sorted_mats:
            avg_rate = m['cost'] / m['qty'] if m['qty'] > 0 else 0
            self._add_bom_row((m['name'], m['unit'], m['qty'], avg_rate, m['cost']))
            
        if sorted_mats:
            self._add_bom_row(("TOTAL OPERATIONAL MATERIAL VALUE", "", 0, 0, mat_total), is_total=True)

        # Populate Package Table
        self._clear_table(self.pkg_list)
        self._add_pkg_row(("PACKAGE NAME", "SUB-CONTRACTOR", "ALLOCATED VALUE"), is_header=True)
        
        sorted_pkgs = sorted(all_packages.items(), key=lambda x: x[1], reverse=True)
        for (p_name, s_name), val in sorted_pkgs:
            self._add_pkg_row((p_name, s_name, val))
            
        if sorted_pkgs:
            self._add_pkg_row(("TOTAL SUB-CONTRACTOR COMMITMENT", "", sub_alloc), is_total=True)

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

    def _add_bom_row(self, data, is_header=False, is_total=False):
        row = LogisticsRow(data[0], data[1], data[2], data[3], data[4], is_header=is_header, is_total=is_total)
        if not is_header and not is_total:
            row.clicked.connect(self._handle_row_click)
        self.bom_list.insertWidget(self.bom_list.count()-1, row)

    def _add_pkg_row(self, data, is_header=False, is_total=False):
        row = PackageRow(data[0], data[1], data[2], is_header=is_header, is_total=is_total)
        if not is_header and not is_total:
            row.clicked.connect(self._handle_row_click)
        self.pkg_list.insertWidget(self.pkg_list.count()-1, row)

    def _handle_row_click(self, row):
        # Unselect previous
        if self._selected_row and self._selected_row != row:
            try:
                self._selected_row.set_selected(False)
            except: pass
            
        self._selected_row = row
        self._selected_row.set_selected(True)
