import os
import sqlite3
import json
import shutil
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QFrame, QScrollArea, QSpacerItem, QSizePolicy, QPushButton, QDialog,
                             QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from analytics_components import MetricCard, TrendLineChart

class BenchmarkRow(QFrame):
    clicked = pyqtSignal(object)

    def __init__(self, description, unit, current_rate, avg_rate, last_rate, currency_symbol="$", is_header=False, parent=None):
        super().__init__(parent)
        self.is_header = is_header
        self.currency_symbol = currency_symbol
        self.data = (description, unit, current_rate, avg_rate, last_rate)
        self.is_selected = False
        self._update_style()
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 8, 15, 8)
        layout.setSpacing(15)
        
        style = "font-family: 'Inter'; font-size: 12px; color: #1e293b;"
        if is_header:
            style = "font-family: 'Inter'; font-weight: 700; color: #64748b; font-size: 11px; text-transform: uppercase;"
            
        # 1. Description
        desc_lbl = QLabel(description)
        desc_lbl.setStyleSheet(style + " border: none;")
        desc_lbl.setWordWrap(True)
        layout.addWidget(desc_lbl, 4)
        
        # 2. Unit
        unit_lbl = QLabel(unit)
        unit_lbl.setStyleSheet(style)
        unit_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(unit_lbl, 1)
        
        # 3. Current Rate
        curr_lbl = QLabel(f"{self.currency_symbol} {current_rate:,.2f}" if not is_header else "Current")
        curr_lbl.setStyleSheet(style + " font-family: 'Consolas'; font-weight: 700;")
        curr_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(curr_lbl, 2)
        
        # 4. Historical Avg
        avg_lbl = QLabel(f"{self.currency_symbol} {avg_rate:,.2f}" if not is_header else "Hist. Avg")
        avg_lbl.setStyleSheet(style + " font-family: 'Consolas'; color: #475569;")
        avg_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(avg_lbl, 2)
        
        # 5. Variance %
        var_pct = 0
        if not is_header and avg_rate > 0:
            var_pct = ((current_rate - avg_rate) / avg_rate) * 100
        
        var_color = "#166534" if abs(var_pct) <= 15 else "#991b1b"
        if is_header: var_str = "Variance"
        else: var_str = f"{var_pct:+.1f}%"
        
        var_lbl = QLabel(var_str)
        if not is_header:
            var_lbl.setStyleSheet(f"font-family: 'Inter'; font-weight: 800; color: {var_color}; font-size: 11px;")
        else:
            var_lbl.setStyleSheet(style)
        var_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(var_lbl, 2)

    def _update_style(self):
        if self.is_header:
            bg, border = "#f8fafc", "#cbd5e1"
        elif self.is_selected:
            bg, border = "#fffde7", "#fbc02d"
        else:
            bg, border = "#ffffff", "#e2e8f0"
            
        self.setStyleSheet(f"""
            BenchmarkRow {{ background-color: {bg}; border-radius: 8px; border: 1px solid {border}; }}
            BenchmarkRow:hover {{ border: 1px solid #2e7d32; background-color: #f1f8e9; }}
        """)

    def set_selected(self, selected):
        if self.is_header: return
        self.is_selected = selected
        self._update_style()

    def mousePressEvent(self, event):
        if not self.is_header:
            self.clicked.emit(self)
        super().mousePressEvent(event)

class HistoricalBenchmarkingAnalytic(QWidget):
    def __init__(self, project_dir, parent=None):
        super().__init__(parent)
        self.project_dir = project_dir
        self.benchmark_dir = r"C:\Users\Consar-Kilpatrick\Desktop\Atlantic Catering School\Project Database"
        self.config_path = os.path.join(self.project_dir, "Benchmark", "benchmark_config.json")
        self.selected_benchmark_files = []
        self._selected_row = None
        self.all_benchmarks = {} # description -> [ {project, rate, prod}, ... ]
        self.current_project_rates = {} # description -> rate
        
        self.currency_symbol = "$"
        self._init_ui()
        
        # Load persistent selection or fallback to default scan
        self._load_config()
        if not self.selected_benchmark_files and os.path.exists(self.benchmark_dir):
            self.selected_benchmark_files = [os.path.join(self.benchmark_dir, f) for f in os.listdir(self.benchmark_dir) if f.endswith('.db')]
            
        self.refresh_data()

    def _load_config(self):
        """Loads the selected project list from the Benchmark folder, with root migration."""
        # 1. Handle migration from root if necessary
        old_root_path = os.path.join(self.project_dir, "benchmark_config.json")
        new_bench_dir = os.path.join(self.project_dir, "Benchmark")
        
        if os.path.exists(old_root_path):
            if not os.path.exists(new_bench_dir): os.makedirs(new_bench_dir)
            try: shutil.move(old_root_path, self.config_path)
            except: pass
            
        # 2. Load from new location
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    data = json.load(f)
                    self.selected_benchmark_files = data.get('selected_files', [])
            except: pass

    def _save_config(self):
        """Persists the selected project list to the Benchmark subdirectory."""
        try:
            config_dir = os.path.dirname(self.config_path)
            if not os.path.exists(config_dir):
                os.makedirs(config_dir)
                
            with open(self.config_path, 'w') as f:
                json.dump({'selected_files': self.selected_benchmark_files}, f)
        except: pass

    def _init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(20, 20, 20, 20)
        root_layout.setSpacing(20)

        # Header
        header_layout = QHBoxLayout()
        header = QLabel("Historical Benchmarking & Unit Rate Comparison")
        header.setStyleSheet("font-family: 'Inter'; font-size: 24px; font-weight: 800; color: #1e293b;")
        header_layout.addWidget(header)
        
        header_layout.addStretch()
        
        self.select_btn = QPushButton("Select Projects...")
        self.select_btn.setFixedSize(160, 38)
        self.select_btn.setStyleSheet("""
            QPushButton {
                background-color: #2e7d32; color: #ffeb3b; border-radius: 8px; 
                font-family: 'Inter'; font-weight: 700; font-size: 12px;
            }
            QPushButton:hover { background-color: #1b5e20; }
        """)
        self.select_btn.clicked.connect(self._select_projects)
        header_layout.addWidget(self.select_btn)
        
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
        self.card_coverage = MetricCard("BENCHMARK COVERAGE", "0%", "Items with hist. data", color="#0369a1")
        self.card_outliers = MetricCard("HIGH-RISK OUTLIERS", "0", "Rates deviating > 15%", color="#991b1b")
        self.card_avg_var = MetricCard("AVG. PORTFOLIO VARIANCE", "0.0%", "Current vs. Hist. Mean", color="#166534")
        
        for c in [self.card_coverage, self.card_outliers, self.card_avg_var]:
            kpi_layout.addWidget(c)
        self.content_layout.addLayout(kpi_layout)

        # 2. Chart & Selection Row
        charts_layout = QHBoxLayout()
        self.trend_chart = TrendLineChart("Unit Rate Trend (Last 5 Projects)")
        charts_layout.addWidget(self._create_card_frame("UNIT RATE TREND ANALYSIS", self.trend_chart), 3)
        
        # Guide Card
        guide_frame = QFrame()
        guide_frame.setStyleSheet("background-color: white; border-radius: 16px; border: 1px solid #e2e8f0;")
        guide_vbox = QVBoxLayout(guide_frame)
        guide_vbox.setContentsMargins(20, 20, 20, 20)
        
        guide_title = QLabel("BENCHMARKING INSIGHTS")
        guide_title.setStyleSheet("font-family: 'Inter'; font-size: 13px; font-weight: 800; color: #64748b; letter-spacing: 1px;")
        guide_vbox.addWidget(guide_title)
        
        self.insight_text = QLabel("Select an item from the table below to analyze its historical price volatility and compare it against the 'Golden Record'.")
        self.insight_text.setStyleSheet("font-family: 'Inter'; font-size: 13px; color: #1e293b; line-height: 1.4;")
        self.insight_text.setWordWrap(True)
        guide_vbox.addWidget(self.insight_text)
        guide_vbox.addStretch()
        
        charts_layout.addWidget(guide_frame, 1)
        self.content_layout.addLayout(charts_layout)

        # 3. Benchmark Table
        table_frame = QFrame()
        table_frame.setStyleSheet("background-color: white; border-radius: 16px; border: 1px solid #e2e8f0;")
        table_vbox = QVBoxLayout(table_frame)
        table_vbox.setContentsMargins(20, 20, 20, 20)
        
        table_header = QLabel("Historical Unit Rate Comparison Schedule")
        table_header.setStyleSheet("font-family: 'Inter'; font-size: 16px; font-weight: 700; color: #1e293b;")
        table_vbox.addWidget(table_header)
        
        self.benchmark_list = QVBoxLayout()
        self.benchmark_list.setSpacing(5)
        self.benchmark_list.addStretch()
        
        table_scroll = QScrollArea()
        table_scroll.setFixedHeight(400)
        table_scroll.setWidgetResizable(True)
        table_scroll.setStyleSheet("border: none;")
        table_container = QWidget()
        table_container.setLayout(self.benchmark_list)
        table_scroll.setWidget(table_container)
        
        table_vbox.addWidget(table_scroll)
        self.content_layout.addWidget(table_frame)

        scroll.setWidget(content)
        root_layout.addWidget(scroll)

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
        """Scans project databases for historical benchmarks with currency normalization."""
        self.all_benchmarks = {}
        self.current_project_rates = {}
        self.exchange_rates = {} # currency -> rate relative to base
        self.base_currency = "USD"
        
        # 1. Load Current Project Settings & Exchange Rates
        curr_db_dir = os.path.join(self.project_dir, "Project Database")
        if os.path.exists(curr_db_dir):
            dbs = [f for f in os.listdir(curr_db_dir) if f.endswith('.db')]
            if dbs:
                db_path = os.path.join(curr_db_dir, dbs[0])
                self._load_current_project_context(db_path)
                self._extract_rates(db_path, "CURRENT", is_current=True)

        # 2. Use Selected Benchmark Files
        if self.selected_benchmark_files:
            for f_path in self.selected_benchmark_files:
                if os.path.exists(f_path):
                    p_name = os.path.basename(f_path).replace('.db', '')
                    self._extract_rates(f_path, p_name)
        elif os.path.exists(self.benchmark_dir):
            # Fallback to default directory if nothing selected
            for f in os.listdir(self.benchmark_dir):
                if f.endswith('.db'):
                    p_name = f.replace('.db', '')
                    self._extract_rates(os.path.join(self.benchmark_dir, f), p_name)

        # 3. Calculate Aggregates
        benchmarked_items = []
        outliers = 0
        total_var = 0.0
        
        for desc, rates in self.all_benchmarks.items():
            if desc in self.current_project_rates:
                curr_rate = self.current_project_rates[desc]
                # Filter out the current project from averages
                hist_rates = [r['rate'] for r in rates if r['project'] != "CURRENT"]
                if not hist_rates: continue
                
                avg_rate = sum(hist_rates) / len(hist_rates)
                last_rate = hist_rates[-1]
                unit = self.benchmark_units.get(desc, "ea")
                
                var_pct = ((curr_rate - avg_rate) / avg_rate * 100) if avg_rate > 0 else 0
                if abs(var_pct) > 15: outliers += 1
                total_var += var_pct
                
                benchmarked_items.append({
                    'desc': desc,
                    'unit': unit,
                    'curr': curr_rate,
                    'avg': avg_rate,
                    'last': last_rate,
                    'var': var_pct
                })

        # Update KPIs
        coverage = (len(benchmarked_items) / len(self.current_project_rates) * 100) if self.current_project_rates else 0
        avg_var = (total_var / len(benchmarked_items)) if benchmarked_items else 0
        
        self.card_coverage.update_value(f"{coverage:.1f}%")
        self.card_outliers.update_value(str(outliers))
        self.card_avg_var.update_value(f"{avg_var:+.1f}%")

        # Update Table
        self._selected_row = None # Safety reset before clearing
        self._clear_layout(self.benchmark_list)
        self.benchmark_list.insertWidget(0, BenchmarkRow("ITEM DESCRIPTION", "UNIT", 0, 0, 0, currency_symbol=self.currency_symbol, is_header=True))
        
        for item in sorted(benchmarked_items, key=lambda x: abs(x['var']), reverse=True):
            row = BenchmarkRow(item['desc'], item['unit'], item['curr'], item['avg'], item['last'], currency_symbol=self.currency_symbol)
            row.clicked.connect(self._handle_row_click)
            self.benchmark_list.insertWidget(self.benchmark_list.count()-1, row)

    def _load_current_project_context(self, db_path):
        """Loads the base currency and exchange rates of the current project."""
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Get Base Currency
            cursor.execute("SELECT value FROM settings WHERE key = 'base_currency'")
            res = cursor.fetchone()
            if res: self.base_currency = res[0]
            else:
                cursor.execute("SELECT currency FROM estimates LIMIT 1")
                res = cursor.fetchone()
                if res: self.base_currency = res[0]
            
            self.currency_symbol = "₵" if "GHS" in self.base_currency else "$"
            
            # Get Exchange Rates
            cursor.execute("SELECT currency, rate FROM estimate_exchange_rates")
            for curr, rate in cursor.fetchall():
                self.exchange_rates[curr] = rate
            conn.close()
        except: pass

    def _extract_rates(self, db_path, project_name, is_current=False):
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # A. Get Historical Project Currency
            hist_currency = ""
            cursor.execute("SELECT value FROM settings WHERE key = 'base_currency'")
            res = cursor.fetchone()
            if res: hist_currency = res[0]
            else:
                cursor.execute("SELECT currency FROM estimates LIMIT 1")
                res = cursor.fetchone()
                if res: hist_currency = res[0]
            
            # B. Calculate Conversion Factor to Current Base Currency
            conv_factor = 1.0
            if not is_current and hist_currency and hist_currency != self.base_currency:
                # We need to convert FROM hist_currency TO current base_currency
                # In Estimator, rates are usually (1 Base = X Foreign)
                # So to get Base value: Foreign / rate
                rate_in_curr_proj = self.exchange_rates.get(hist_currency)
                if rate_in_curr_proj and rate_in_curr_proj > 0:
                    conv_factor = 1.0 / rate_in_curr_proj
            
            # 1. Extract Unit Rates from pboq_items
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pboq_items'")
            if cursor.fetchone():
                cursor.execute('SELECT "Description", "Unit", "Bill Rate", "RateCode" FROM pboq_items WHERE "Bill Rate" IS NOT NULL AND "Bill Rate" != ""')
                rows = cursor.fetchall()
                for desc, unit, rate, rcode in rows:
                    try:
                        raw_val = float(str(rate).replace(',', '').replace(' ', '').replace('₵','').replace('$','').strip())
                        if raw_val <= 0: continue
                        
                        # Apply Currency Normalization
                        rate_val = raw_val * conv_factor
                        
                        if is_current:
                            self.current_project_rates[desc] = rate_val
                        
                        if desc not in self.all_benchmarks:
                            self.all_benchmarks[desc] = []
                        
                        # 2. Try to find productivity (man-hours) if rcode is present
                        prod_val = 0.0
                        if rcode:
                            cursor.execute("""
                                SELECT SUM(l.hours) / t.quantity 
                                FROM estimate_labor l 
                                JOIN tasks t ON l.task_id = t.id 
                                WHERE t.estimate_id = (SELECT id FROM estimates WHERE rate_code = ?)
                            """, (rcode,))
                            res = cursor.fetchone()
                            if res and res[0]: prod_val = res[0]

                        self.all_benchmarks[desc].append({
                            'project': project_name,
                            'rate': rate_val,
                            'prod': prod_val,
                            'currency': hist_currency
                        })
                        
                        if not hasattr(self, 'benchmark_units'): self.benchmark_units = {}
                        self.benchmark_units[desc] = unit or "ea"
                    except: continue
            conn.close()
        except: pass

    def _clear_layout(self, layout):
        while layout.count() > 1:
            it = layout.takeAt(0)
            if it.widget(): it.widget().deleteLater()

    def _handle_row_click(self, row):
        # Safety check: ensure previous row hasn't been deleted
        try:
            if self._selected_row: self._selected_row.set_selected(False)
        except RuntimeError: pass 

        self._selected_row = row
        self._selected_row.set_selected(True)
        
        desc = row.data[0]
        rates_data = self.all_benchmarks.get(desc, [])
        
        # Trend data for Unit Rates
        plot_data = [(r['project'], r['rate']) for r in rates_data if r['project'] != "CURRENT"]
        self.trend_chart.currency_symbol = self.currency_symbol # Sync chart currency
        self.trend_chart.set_data(plot_data)
        
        # Productivity Analysis
        prod_data = [r['prod'] for r in rates_data if r['project'] != "CURRENT" and r['prod'] > 0]
        avg_prod = (sum(prod_data) / len(prod_data)) if prod_data else 0
        
        # Update Insight
        avg = row.data[3]
        curr = row.data[2]
        var = ((curr - avg) / avg * 100) if avg > 0 else 0
        
        status = "is trending HIGHER than" if var > 0 else "is trending LOWER than"
        risk = "HIGH RISK" if abs(var) > 15 else "STABLE"
        
        prod_txt = f"<br/><br/><b>Productivity Benchmark:</b> {avg_prod:.2f} hrs/{row.data[1]}" if avg_prod > 0 else ""
        
        self.insight_text.setText(f"<b>{desc}</b> {status} the historical average by {abs(var):.1f}%.<br/><br/>"
                                 f"Status: <span style='color: {'#991b1b' if abs(var) > 15 else '#166534'}; font-weight: bold;'>{risk}</span>"
                                 f"{prod_txt}<br/><br/>"
                                 f"Recommendation: Verify quantity buildups and supplier quotes to ensure accuracy.")

    def _select_projects(self):
        """Opens the portfolio manager dialog to curate the benchmarking set."""
        dialog = BenchmarkProjectSelectionDialog(self.benchmark_dir, self.selected_benchmark_files, self)
        if dialog.exec():
            self.selected_benchmark_files = dialog.get_selected_files()
            self._save_config()
            self.refresh_data()

class BenchmarkProjectSelectionDialog(QDialog):
    """A premium table-based dialog for managing the benchmarking project portfolio."""
    def __init__(self, benchmark_dir, selected_files, parent=None):
        super().__init__(parent)
        self.benchmark_dir = benchmark_dir
        self.initial_selection = selected_files
        self.setWindowTitle("Benchmark Portfolio Manager")
        self.setMinimumSize(600, 500)
        self.setStyleSheet("background-color: #f8fafc;")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        title = QLabel("Select Projects for Historical Analysis")
        title.setStyleSheet("font-family: 'Inter'; font-size: 18px; font-weight: 800; color: #1e293b;")
        layout.addWidget(title)
        
        subtitle = QLabel("Choose the historical databases that should contribute to the 'Golden Record' averages.")
        subtitle.setStyleSheet("font-family: 'Inter'; font-size: 12px; color: #64748b;")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)
        
        # Table
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["", "Project Name", "Path / Source", "Action"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 40)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(1, 200)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(3, 80)
        
        self.table.setStyleSheet("""
            QTableWidget { background-color: white; border-radius: 8px; border: 1px solid #e2e8f0; gridline-color: #f1f5f9; }
            QHeaderView::section { background-color: #f8fafc; padding: 8px; border: none; font-weight: bold; color: #475569; }
            QPushButton#RemoveBtn { background-color: #fee2e2; color: #991b1b; border: 1px solid #fecaca; border-radius: 4px; font-weight: bold; font-size: 10px; }
            QPushButton#RemoveBtn:hover { background-color: #fecaca; }
        """)
        
        layout.addWidget(self.table)
        
        # Portfolio List Management
        self.current_portfolio = list(self.initial_selection)
        # Also auto-discover from benchmark_dir if not already in portfolio
        if os.path.exists(self.benchmark_dir):
            for f in os.listdir(self.benchmark_dir):
                if f.endswith('.db'):
                    path = os.path.join(self.benchmark_dir, f)
                    if path not in self.current_portfolio:
                        self.current_portfolio.append(path)

        self._refresh_table()
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        add_btn = QPushButton("+ Add External Project...")
        add_btn.setFixedSize(180, 35)
        add_btn.setStyleSheet("background-color: #f0fdf4; color: #166534; border: 1px solid #bbf7d0; border-radius: 6px; font-weight: bold;")
        add_btn.clicked.connect(self._add_external)
        btn_layout.addWidget(add_btn)
        
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedSize(100, 35)
        cancel_btn.setStyleSheet("background-color: #f1f5f9; color: #475569; border-radius: 6px; font-weight: bold;")
        cancel_btn.clicked.connect(self.reject)
        
        apply_btn = QPushButton("Apply Portfolio")
        apply_btn.setFixedSize(140, 35)
        apply_btn.setStyleSheet("background-color: #2e7d32; color: #ffeb3b; border-radius: 6px; font-weight: bold;")
        apply_btn.clicked.connect(self.accept)
        
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(apply_btn)
        layout.addLayout(btn_layout)

    def _refresh_table(self):
        self.table.setRowCount(0)
        self.checkbox_map = {} # row -> (checkbox, path)
        
        for i, path in enumerate(self.current_portfolio):
            self.table.insertRow(i)
            name = os.path.basename(path).replace('.db', '')
            
            # 1. Checkbox
            cb_container = QWidget()
            cb_layout = QHBoxLayout(cb_container)
            cb_layout.setContentsMargins(0, 0, 0, 0)
            cb_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cb = QCheckBox()
            # If it was in initial selection, or is newly added, keep it checked
            if path in self.initial_selection:
                cb.setChecked(True)
            cb_layout.addWidget(cb)
            self.table.setCellWidget(i, 0, cb_container)
            self.checkbox_map[i] = (cb, path)
            
            # 2. Name
            self.table.setItem(i, 1, QTableWidgetItem(name))
            
            # 3. Path
            path_item = QTableWidgetItem(path)
            path_item.setForeground(QColor("#64748b"))
            path_item.setFont(QFont("Inter", 8))
            self.table.setItem(i, 2, path_item)
            
            # 4. Remove Button
            rem_btn = QPushButton("Remove")
            rem_btn.setObjectName("RemoveBtn")
            rem_btn.setFixedSize(60, 22)
            rem_btn.clicked.connect(lambda checked, p=path: self._remove_from_portfolio(p))
            self.table.setCellWidget(i, 3, rem_btn)

    def _add_external(self):
        from PyQt6.QtWidgets import QFileDialog
        files, _ = QFileDialog.getOpenFileNames(self, "Add External Projects", "", "Project Databases (*.db);;All Files (*)")
        if files:
            for f in files:
                if f not in self.current_portfolio:
                    self.current_portfolio.append(f)
                    # New external projects are checked by default
                    if f not in self.initial_selection:
                        self.initial_selection.append(f)
            self._refresh_table()

    def _remove_from_portfolio(self, path):
        if path in self.current_portfolio:
            self.current_portfolio.remove(path)
        if path in self.initial_selection:
            self.initial_selection.remove(path)
        self._refresh_table()

    def get_selected_files(self):
        selected = []
        for i in range(self.table.rowCount()):
            cb, path = self.checkbox_map[i]
            if cb.isChecked():
                selected.append(path)
        return selected

    def refresh_data_called(self):
        self.refresh_data()
