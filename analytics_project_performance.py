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

    def refresh_data(self):
        """Aggregates data across all PBOQ databases."""
        self._load_currency()
        if not os.path.exists(self.pboq_folder):
            return

        total_bid = 0.0
        total_items = 0
        priced_items = 0
        flagged_items = 0
        
        sources = {
            'gross': 0.0, 
            'plug': 0.0, 
            'sub': 0.0, 
            'provisional': 0.0,
            'pc_sum': 0.0,
            'daywork': 0.0
        }
        sheet_data = []

        for f in os.listdir(self.pboq_folder):
            if f.lower().endswith('.db'):
                db_path = os.path.join(self.pboq_folder, f)
                
                qty_col = -1
                unit_col = -1
                desc_col = -1
                bill_amt_col = -1
                state_file = os.path.join(self.project_dir, "PBOQ States", f + ".json")
                if os.path.exists(state_file):
                    try:
                        with open(state_file, 'r') as sf:
                            state = json.load(sf)
                            m = state.get('mappings', {})
                            qty_col = m.get('qty', -1)
                            unit_col = m.get('unit', -1)
                            desc_col = m.get('desc', -1)
                            bill_amt_col = m.get('bill_amount', -1)
                    except: pass
                
                try:
                    conn = sqlite3.connect(db_path)
                    PBOQLogic.ensure_schema(conn)
                    cursor = conn.cursor()
                    
                    if qty_col < 0 or unit_col < 0 or desc_col < 0:
                        cursor.execute("PRAGMA table_info(pboq_items)")
                        cols = [info[1] for info in cursor.fetchall()]
                        for i, name in enumerate(cols):
                            clean_name = name.lower().replace(" ", "").replace("_", "")
                            if qty_col < 0 and clean_name in ["quantity", "qty"]:
                                qty_col = i - 1 
                            if unit_col < 0 and clean_name == "unit":
                                unit_col = i - 1
                            if desc_col < 0 and clean_name in ["description", "desc"]:
                                desc_col = i - 1
                    
                    item_clause = "(1=0)"
                    priced_clause = "(1=0)"
                    amt_sum_expr = "0.0"
                    
                    if desc_col >= 0 or unit_col >= 0 or qty_col >= 0:
                        cursor.execute("PRAGMA table_info(pboq_items)")
                        actual_cols = [info[1] for info in cursor.fetchall()]
                        
                        desc_name = actual_cols[desc_col+1] if desc_col >= 0 and (desc_col+1) < len(actual_cols) else None
                        qty_name = actual_cols[qty_col+1] if qty_col >= 0 and (qty_col+1) < len(actual_cols) else None
                        unit_name = actual_cols[unit_col+1] if unit_col >= 0 and (unit_col+1) < len(actual_cols) else None
                        
                        # Detect Bill Amount column: Use mapping first
                        bill_amt_name = None
                        if bill_amt_col >= 0 and (bill_amt_col + 1) < len(actual_cols):
                            bill_amt_name = actual_cols[bill_amt_col + 1]
                        
                        if not bill_amt_name:
                            bill_amt_name = next((pv for pv in ["Bill Amount", "BillAmount"] if pv in actual_cols), None)
                            
                        if not bill_amt_name and "Column 5" in actual_cols:
                            bill_amt_name = "Column 5"
                        
                        sani = "'0'"
                        if bill_amt_name:
                            # Sanitize: Strip symbols (GH¢, GHC, GHS, ¢, ₵), commas, spaces
                            sani = f"REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(IFNULL(\"{bill_amt_name}\", '0'), ',', ''), ' ', ''), 'GH¢', ''), 'GHC', ''), 'GHS', ''), '¢', ''), '₵', '')"
                        
                        amt_sum_expr = f"SUM(CAST({sani} AS REAL))"
                        
                        if desc_name:
                            desc_check = f"(TRIM(\"{desc_name}\") != '' AND \"{desc_name}\" IS NOT NULL)"
                            or_parts = []
                            if qty_name:
                                qty_check = f"(CAST(REPLACE(\"{qty_name}\", ',', '') AS REAL) != 0)"
                                if unit_name:
                                    unit_check = f"(TRIM(\"{unit_name}\") != '' AND \"{unit_name}\" IS NOT NULL)"
                                    or_parts.append(f"({qty_check} AND {unit_check})")
                                else:
                                    or_parts.append(qty_check)
                            
                            priced_parts = []
                            # Include the detected bill_amt_name (which might be Column 5) in price variants
                            price_variants = ["Bill Amount", "BillAmount", "Bill Rate", "BillRate"]
                            if bill_amt_name and bill_amt_name not in price_variants:
                                price_variants.append(bill_amt_name)
                                
                            for pv in price_variants:
                                if pv in actual_cols:
                                    pv_clean = f"CAST(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(IFNULL(\"{pv}\", '0'), ',', ''), ' ', ''), 'GH¢', ''), 'GHC', ''), 'GHS', ''), '¢', ''), '₵', '') AS REAL)"
                                    or_parts.append(f"({pv_clean} > 0)")
                                    # Removed original Bill Amount from priced_parts to honor user requirement:
                                    # "only bill amounts with price types have to be considered"
                            
                            src_cols = ["GrossRate", "PlugRate", "SubbeeRate", "ProvSum", "PCSum", "Daywork"]
                            for sc in src_cols:
                                if sc in actual_cols:
                                    priced_parts.append(f"(\"{sc}\" != '' AND \"{sc}\" IS NOT NULL)")
 
                            if or_parts:
                                item_clause = f"({desc_check} AND ({' OR '.join(or_parts)}) AND (LOWER(\"{desc_name}\") NOT LIKE '%collection%' AND LOWER(\"{desc_name}\") NOT LIKE '%summary%'))"
                            if priced_parts:
                                priced_clause = f"({desc_check} AND ({' OR '.join(priced_parts)}))"
 
                    q1 = f"""
                        SELECT Sheet, 
                               SUM(CASE WHEN {item_clause} THEN 1 ELSE 0 END), 
                               SUM(CASE WHEN {item_clause} AND {priced_clause} THEN 1 ELSE 0 END), 
                               SUM(CASE WHEN {item_clause} AND {priced_clause} THEN CAST({sani} AS REAL) ELSE 0.0 END)
                        FROM pboq_items 
                        GROUP BY Sheet
                    """
                    cursor.execute(q1)
                    rows = cursor.fetchall()
                    for sheet, count, priced, amt in rows:
                        sheet_data.append({
                            'name': f"{f.replace('.db','')} - {sheet}",
                            'total': count,
                            'priced': priced,
                            'amount': amt or 0.0
                        })
                        total_items += count
                        priced_items += priced
                        total_bid += (amt or 0.0)
                    
                    cursor.execute("SELECT SUM(IsFlagged) FROM pboq_items")
                    flagged_items += (cursor.fetchone()[0] or 0)
                        
                    cursor.execute(f"""
                        SELECT 
                            SUM(CASE WHEN GrossRate != '' AND GrossRate IS NOT NULL THEN CAST({sani} AS REAL) ELSE 0 END),
                            SUM(CASE WHEN PlugRate != '' AND PlugRate IS NOT NULL THEN CAST({sani} AS REAL) ELSE 0 END),
                            SUM(CASE WHEN SubbeeRate != '' AND SubbeeRate IS NOT NULL THEN CAST({sani} AS REAL) ELSE 0 END),
                            SUM(CASE WHEN ProvSum != '' AND ProvSum IS NOT NULL THEN CAST({sani} AS REAL) ELSE 0 END),
                            SUM(CASE WHEN PCSum != '' AND PCSum IS NOT NULL THEN CAST({sani} AS REAL) ELSE 0 END),
                            SUM(CASE WHEN Daywork != '' AND Daywork IS NOT NULL THEN CAST({sani} AS REAL) ELSE 0 END)
                        FROM pboq_items
                    """)
                    src_row = cursor.fetchone()
                    if src_row:
                        sources['gross'] += src_row[0] or 0.0
                        sources['plug'] += src_row[1] or 0.0
                        sources['sub'] += src_row[2] or 0.0
                        sources['provisional'] += src_row[3] or 0.0
                        sources['pc_sum'] += src_row[4] or 0.0
                        sources['daywork'] += src_row[5] or 0.0
                        
                    conn.close()
                except Exception as e:
                    print(f"Error reading {f}: {e}")

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
