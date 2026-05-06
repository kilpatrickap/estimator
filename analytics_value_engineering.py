import os
import sqlite3
import json
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QFrame, QScrollArea, QSpacerItem, QSizePolicy, QSpinBox)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from analytics_components import get_project_currency_symbol, MetricCard, DonutChart, SelectionFrame

class VERow(SelectionFrame):
    """A styled row for Value Engineering tables."""
    def __init__(self, description, unit, quantity, rate, total, currency_symbol="$", source="Manual", is_header=False, parent=None):
        super().__init__(parent)
        self.currency_symbol = currency_symbol
        self.is_header = is_header
        self.data = (description, unit, quantity, rate, total, source)
        self.is_selected = False
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 8, 15, 8)
        layout.setSpacing(15)
        
        style = "font-family: 'Inter'; font-size: 12px; color: #1e293b;"
        if is_header:
            style = "font-family: 'Inter'; font-weight: 700; color: #64748b; font-size: 11px; text-transform: uppercase;"
            self.setStyleSheet("background-color: #f8fafc; border-bottom: 2px solid #e2e8f0;")
        else:
            self._update_style()

        # 1. Description
        desc_lbl = QLabel(description)
        desc_lbl.setStyleSheet(style + " border: none;")
        desc_lbl.setWordWrap(True)
        layout.addWidget(desc_lbl, 4)
        
        # 2. Source/Type (Flag)
        source_lbl = QLabel(source.upper() if not is_header else "Source")
        if not is_header:
            color = "#991b1b" if source == "Manual" else ("#0369a1" if source == "Market" else "#166534")
            source_lbl.setStyleSheet(f"font-family: 'Inter'; font-weight: 800; color: {color}; font-size: 10px; background: {color}15; padding: 2px 6px; border-radius: 4px;")
        else:
            source_lbl.setStyleSheet(style)
        source_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(source_lbl, 1)

        # 3. Rate
        rate_lbl = QLabel(f"{self.currency_symbol} {rate:,.2f}" if not is_header else "Rate")
        rate_lbl.setStyleSheet(style + " font-family: 'Consolas';")
        rate_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(rate_lbl, 2)
        
        # 4. Total Value
        total_lbl = QLabel(f"{self.currency_symbol} {total:,.2f}" if not is_header else "Total Value")
        total_lbl.setStyleSheet(style + (" font-family: 'Consolas'; font-weight: 800; color: #0f172a;" if not is_header else ""))
        total_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(total_lbl, 2)

    def _update_style(self):
        bg = "#fffde7" if self.is_selected else "#ffffff"
        border = "#fbc02d" if self.is_selected else "#e2e8f0"
        self.setStyleSheet(f"""
            VERow {{ background-color: {bg}; border-radius: 8px; border: 1px solid {border}; }}
            VERow:hover {{ border: 1px solid #2e7d32; background-color: #f1f8e9; }}
        """)

    def set_selected(self, selected):
        if self.is_header: return
        self.is_selected = selected
        self._update_style()

class ValueEngineeringAnalytic(QWidget):
    """Automated Value Engineering Finder - Identifies manual plugs and high-cost outliers."""
    def __init__(self, project_dir, parent=None):
        super().__init__(parent)
        self.project_dir = project_dir
        self._selected_row = None
        self.currency_symbol = get_project_currency_symbol(project_dir) + " "
        self._init_ui()
        self.refresh_data()

    def _init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(20, 20, 20, 20)
        root_layout.setSpacing(20)

        header_layout = QHBoxLayout()
        header = QLabel("Automated Value Engineering (VE) Finder")
        header.setStyleSheet("font-family: 'Inter'; font-size: 24px; font-weight: 800; color: #1e293b;")
        header_layout.addWidget(header)
        header_layout.addStretch()
        
        # Target % Selection
        target_lbl = QLabel("TARGET SAVINGS % : ")
        target_lbl.setStyleSheet("font-family: 'Inter'; font-weight: 800; color: #64748b; font-size: 11px;")
        header_layout.addWidget(target_lbl)
        
        self.target_pct_spin = QSpinBox()
        self.target_pct_spin.setRange(1, 100)
        self.target_pct_spin.setValue(5)
        self.target_pct_spin.setSuffix(" %")
        self.target_pct_spin.setStyleSheet("""
            QSpinBox {
                background: white; border: 1px solid #e2e8f0; border-radius: 6px; 
                padding: 5px 10px; font-weight: bold; color: #166534; font-size: 12px;
            }
        """)
        self.target_pct_spin.valueChanged.connect(self.refresh_data)
        header_layout.addWidget(self.target_pct_spin)
        
        root_layout.addLayout(header_layout)

        # Scroll Area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none; background: transparent;")
        content = QWidget()
        self.content_layout = QVBoxLayout(content)
        self.content_layout.setSpacing(25)
        
        # 1. KPI Row
        kpi_layout = QHBoxLayout()
        self.card_opportunities = MetricCard("VE OPPORTUNITIES", "0", "Manual Plug items identified", color="#991b1b")
        self.card_outliers_val = MetricCard("HIGH-VALUE RISK", f"{self.currency_symbol}0", "Total value of Top 50 items", color="#0369a1")
        self.card_savings = MetricCard("EST. SAVINGS TARGET", f"{self.currency_symbol}0", "Potential @ 5% reduction", color="#166534")
        
        for c in [self.card_opportunities, self.card_outliers_val, self.card_savings]:
            kpi_layout.addWidget(c)
        self.content_layout.addLayout(kpi_layout)


        # 2. Charts & Insights Row (Middle)
        analytics_row = QHBoxLayout()
        
        # Source Reliability Chart
        self.confidence_chart = DonutChart("PRICING CONFIDENCE MIX")
        self.confidence_frame = self._create_card_frame("SOURCE RELIABILITY", self.confidence_chart)
        analytics_row.addWidget(self.confidence_frame, 1)
        
        # Insight Panel
        insight_frame = QFrame()
        insight_frame.setStyleSheet("background-color: white; border-radius: 16px; border: 1px solid #e2e8f0;")
        insight_vbox = QVBoxLayout(insight_frame)
        insight_vbox.setContentsMargins(20, 20, 20, 20)
        
        insight_title = QLabel("VE STRATEGY INSIGHTS")
        insight_title.setStyleSheet("font-family: 'Inter'; font-size: 13px; font-weight: 800; color: #64748b; letter-spacing: 1px;")
        insight_vbox.addWidget(insight_title)
        
        self.insight_text = QLabel("Select an item from the tables below to analyze its Value Engineering potential.")
        self.insight_text.setStyleSheet("font-family: 'Inter'; font-size: 13px; color: #1e293b; line-height: 1.5;")
        self.insight_text.setWordWrap(True)
        insight_vbox.addWidget(self.insight_text)
        insight_vbox.addStretch()
        analytics_row.addWidget(insight_frame, 1)
        
        self.content_layout.addLayout(analytics_row)

        # 3. Full-Width Tables (Bottom)
        # Table 1: High Cost Outliers
        outlier_frame = self._create_table_frame("TOP 50 COST OUTLIERS", "Big-ticket items where small % changes yield maximum impact.")
        self.outlier_list = QVBoxLayout()
        self.outlier_list.setSpacing(5)
        self.outlier_list.addStretch()
        outlier_scroll = self._setup_table_scroll(self.outlier_list)
        outlier_frame.layout().addWidget(outlier_scroll)
        self.content_layout.addWidget(outlier_frame)

        # Table 2: Manual Plugs (VE Opportunities)
        ve_frame = self._create_table_frame("VE OPPORTUNITIES (MANUAL PLUGS)", "High-risk custom estimates requiring standard validation.")
        self.ve_list = QVBoxLayout()
        self.ve_list.setSpacing(5)
        self.ve_list.addStretch()
        ve_scroll = self._setup_table_scroll(self.ve_list)
        ve_frame.layout().addWidget(ve_scroll)
        self.content_layout.addWidget(ve_frame)

        scroll.setWidget(content)
        root_layout.addWidget(scroll)


    def _create_card_frame(self, title, widget):
        f = QFrame()
        f.setStyleSheet("background-color: white; border-radius: 16px; border: 1px solid #e2e8f0;")
        l = QVBoxLayout(f)
        l.setContentsMargins(20, 20, 20, 20)
        lbl = QLabel(f"<span style='font-family: Inter; font-weight: bold; color: #475569; font-size: 13px; letter-spacing: 0.5px;'>{title}</span>")
        l.addWidget(lbl)
        l.addWidget(widget)
        return f

    def _create_table_frame(self, title, subtitle):
        f = QFrame()
        f.setStyleSheet("background-color: white; border-radius: 16px; border: 1px solid #e2e8f0;")
        l = QVBoxLayout(f)
        l.setContentsMargins(20, 20, 20, 20)
        
        t_lbl = QLabel(title)
        t_lbl.setStyleSheet("font-family: 'Inter'; font-size: 16px; font-weight: 700; color: #1e293b;")
        l.addWidget(t_lbl)
        
        s_lbl = QLabel(subtitle)
        s_lbl.setStyleSheet("font-family: 'Inter'; font-size: 12px; color: #64748b; margin-bottom: 10px;")
        s_lbl.setWordWrap(True)
        l.addWidget(s_lbl)
        return f

    def _setup_table_scroll(self, layout):
        scroll = QScrollArea()
        scroll.setMinimumHeight(300)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none;")
        container = QWidget()
        container.setLayout(layout)
        scroll.setWidget(container)
        return scroll

    def refresh_data(self):
        """Scans all PBOQ databases in the project folder and aggregates VE insights."""
        pboq_dir = os.path.join(self.project_dir, "Priced BOQs")
        if not os.path.exists(pboq_dir): return

        all_items = []
        
        for f in os.listdir(pboq_dir):
            if f.endswith('.db'):
                db_path = os.path.join(pboq_dir, f)
                all_items.extend(self._extract_ve_data(db_path))

        if not all_items: return

        # 1. Calculate Confidence Mix
        verified_val = sum(i['total'] for i in all_items if i['source'] == "Verified")
        market_val = sum(i['total'] for i in all_items if i['source'] == "Market")
        manual_val = sum(i['total'] for i in all_items if i['source'] == "Manual")
        
        self.confidence_chart.set_data([
            ("Verified (Library)", verified_val, "#166534"),
            ("Market (Quotes)", market_val, "#0369a1"),
            ("Manual (Plugs)", manual_val, "#991b1b")
        ])


        # 2. Extract VE Opportunities (Manual Plugs sorted by Value)
        manual_plugs = sorted([i for i in all_items if i['source'] == "Manual"], key=lambda x: x['total'], reverse=True)
        self._populate_list(self.ve_list, manual_plugs)
        self.card_opportunities.update_value(str(len(manual_plugs)))

        # 3. Extract High Cost Outliers (Top 50)
        top_50 = sorted(all_items, key=lambda x: x['total'], reverse=True)[:50]
        self._populate_list(self.outlier_list, top_50)
        
        outlier_total = sum(i['total'] for i in top_50)
        target_pct = self.target_pct_spin.value() / 100.0
        self.card_outliers_val.update_value(f"{self.currency_symbol}{outlier_total:,.0f}")
        self.card_savings.update_value(f"{self.currency_symbol}{outlier_total * target_pct:,.0f}", subtext=f"Potential @ {self.target_pct_spin.value()}% reduction")


    def _extract_ve_data(self, db_path):
        items = []
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Get Currency
            self.currency_symbol = get_project_currency_symbol(self.project_dir) + " "
            
            # Find Column Roles
            cursor.execute("PRAGMA table_info(pboq_items)")
            cols = {info[1]: i for i, info in enumerate(cursor.fetchall())}
            
            # Query all priced items
            # Logic: If Bill Rate exists, use it. Else try PlugRate or SubbeeRate.
            query = "SELECT * FROM pboq_items"
            cursor.execute(query)
            rows = cursor.fetchall()
            
            def get_v(row, col_name):
                idx = cols.get(col_name, -1)
                return row[idx] if idx >= 0 else None

            def clean_f(val):
                try: return float(str(val).replace(',', '').replace('%', '').strip())
                except: return 0.0

            for row in rows:
                desc = get_v(row, "Description") or get_v(row, "Column 1") or "Unnamed Item"
                unit = get_v(row, "Unit") or "ea"
                qty = clean_f(get_v(row, "Quantity") or get_v(row, "Column 2"))
                
                bill_rate = clean_f(get_v(row, "Bill Rate") or get_v(row, "Column 4"))
                rate_code = get_v(row, "RateCode")
                plug_rate = clean_f(get_v(row, "PlugRate"))
                plug_code = get_v(row, "PlugCode")
                sub_name = get_v(row, "SubbeeName")
                
                if qty <= 0 or bill_rate <= 0: continue
                
                # Determine Source (Priority: Manual Plug > Market > Verified)
                if plug_rate > 0:
                    source = "Manual"
                elif sub_name and str(sub_name).strip():
                    source = "Market"
                elif rate_code and str(rate_code).strip():
                    source = "Verified"
                else:
                    source = "Manual"
                
                items.append({
                    'desc': desc,
                    'unit': unit,
                    'qty': qty,
                    'rate': bill_rate,
                    'total': qty * bill_rate,
                    'source': source
                })
            conn.close()
        except Exception as e:
            print(f"VE Data Extraction Error: {e}")
        return items

    def _populate_list(self, layout, items):
        # Clear existing
        while layout.count() > 1:
            it = layout.takeAt(0)
            if it.widget(): it.widget().deleteLater()
            
        # Add Header
        layout.insertWidget(0, VERow("ITEM DESCRIPTION", "UNIT", 0, 0, 0, is_header=True))
        
        # Add Rows
        for item in items:
            row = VERow(item['desc'], item['unit'], item['qty'], item['rate'], item['total'], currency_symbol=self.currency_symbol.strip(), source=item['source'])
            row.clicked.connect(self._handle_row_click)
            layout.insertWidget(layout.count() - 1, row)

    def _handle_row_click(self, row=None):
        # Row selection highlighting logic
        sender = row or self.sender()
        if self._selected_row: self._selected_row.set_selected(False)
        self._selected_row = sender
        self._selected_row.set_selected(True)
        
        desc, unit, qty, rate, total, source = sender.data
        
        # Generate dynamic insight
        if source == "Manual":
            status = "<span style='color: #991b1b; font-weight: bold;'>HIGH RISK (Manual Plug)</span>"
            action = "Search the SOR/Library for a standard equivalent. If this is a custom item, consider splitting the rate buildup into Material/Labor for better cost control."
        elif source == "Market":
            status = "<span style='color: #0369a1; font-weight: bold;'>MEDIUM RISK (Market Quote)</span>"
            action = "This item is linked to a subcontractor quote. Verify if the 'Specification' can be optimized or if alternative subcontractors offer more competitive quotes."
        else:
            status = "<span style='color: #166534; font-weight: bold;'>LOW RISK (Verified SOR)</span>"
            action = "Item is linked to the library. Focus VE on quantity reduction or check if the library rate is dated compared to current project scale."
            
        self.insight_text.setText(f"<b>{desc}</b><br/><br/>"
                                 f"Status: {status}<br/><br/>"
                                 f"<b>Total Value:</b> {self.currency_symbol}{total:,.2f}<br/>"
                                 f"<b>Unit Rate:</b> {self.currency_symbol}{rate:,.2f}<br/><br/>"
                                 f"<b>Recommendation:</b><br/>{action}")
