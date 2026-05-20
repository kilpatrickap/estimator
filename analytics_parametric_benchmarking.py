# analytics_parametric_benchmarking.py

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
        grad_low = QLinearGradient(QPointF(x_start, bar_y), QPointF(x_min_norm, bar_y))
        grad_low.setColorAt(0, QColor("#ef6c00")) # High variance / Risk
        grad_low.setColorAt(1, QColor("#81c784")) # Competitively low cost
        painter.setBrush(QBrush(grad_low))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(QRectF(x_start, bar_y, x_min_norm - x_start, bar_h), 6, 6)
        
        # Segment 2: Optimal / Competitive Budget Range (Green)
        grad_opt = QLinearGradient(QPointF(x_min_norm, bar_y), QPointF(x_max_norm, bar_y))
        grad_opt.setColorAt(0, QColor("#81c784"))
        grad_opt.setColorAt(0.5, QColor("#4caf50"))
        grad_opt.setColorAt(1, QColor("#81c784"))
        painter.setBrush(QBrush(grad_opt))
        painter.drawRect(QRectF(x_min_norm, bar_y, x_max_norm - x_min_norm, bar_h))
        
        # Segment 3: Premium / High Spec Range (Green to Red)
        grad_high = QLinearGradient(QPointF(x_max_norm, bar_y), QPointF(x_end, bar_y))
        grad_high.setColorAt(0, QColor("#81c784"))
        grad_high.setColorAt(0.6, QColor("#e53935")) # Very high budget
        grad_high.setColorAt(1, QColor("#b71c1c")) # Extreme/Luxury
        painter.setBrush(QBrush(grad_high))
        painter.drawRoundedRect(QRectF(x_max_norm, bar_y, x_end - x_max_norm, bar_h), 6, 6)

        # Draw segment boundaries & division text
        painter.setFont(QFont("Inter", 8, QFont.Weight.Medium))
        painter.setPen(QPen(QColor("#64748b")))
        
        # Draw min/max markers below the bar
        painter.drawText(QRectF(x_min_norm - 60, bar_y + bar_h + 8, 120, 20), 
                         Qt.AlignmentFlag.AlignCenter, 
                         f"Min Norm\n{self.currency_symbol}{self.min_normal:,.0f}")
        painter.drawText(QRectF(x_max_norm - 60, bar_y + bar_h + 8, 120, 20), 
                         Qt.AlignmentFlag.AlignCenter, 
                         f"Max Norm\n{self.currency_symbol}{self.max_normal:,.0f}")

        # Draw scale bounds
        painter.setFont(QFont("Inter", 7))
        painter.drawText(QRectF(x_start - 30, bar_y + bar_h + 8, 60, 20), 
                         Qt.AlignmentFlag.AlignCenter, 
                         f"{self.currency_symbol}{scale_min:,.0f}")
        painter.drawText(QRectF(x_end - 30, bar_y + bar_h + 8, 60, 20), 
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
            painter.drawText(QRectF(xs - 100, bar_y - 28, 200, 18), 
                             Qt.AlignmentFlag.AlignCenter, 
                             f"SIMULATED: {self.currency_symbol}{self.simulated_rate:,.1f}/m²")

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
            painter.drawText(QRectF(xa - 100, bar_y + bar_h + 38, 200, 18), 
                             Qt.AlignmentFlag.AlignCenter, 
                             f"ACTUAL: {self.currency_symbol}{self.actual_rate:,.1f}/m²")


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
        
        # Draw stacked bar
        current_x = float(margin_x)
        for label, val, color in self.cost_drivers:
            if val <= 0: continue
            seg_w = (val / total) * bar_w
            
            grad = QLinearGradient(QPointF(current_x, bar_y), QPointF(current_x + seg_w, bar_y))
            grad.setColorAt(0, QColor(color))
            grad.setColorAt(1, QColor(color).lighter(110))
            
            painter.setBrush(QBrush(grad))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(QRectF(current_x, bar_y, seg_w, bar_h))
            
            # Subtle vertical grid line divider
            painter.setPen(QPen(QColor("white"), 1))
            painter.drawLine(QPointF(current_x + seg_w, bar_y), QPointF(current_x + seg_w, bar_y + bar_h))
            
            current_x += seg_w

        # Draw a beautiful outer frame around the stacked bar
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor("#e2e8f0"), 1.5))
        painter.drawRoundedRect(QRectF(margin_x, bar_y, bar_w, bar_h), 2, 2)
        
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
        self.currency_symbol = "$"
        self.actual_project_net = 0.0
        
        # Load Project Constants/Base Settings
        self._load_currency()
        self._scan_actual_project_cost()
        
        self._init_ui()
        self._load_state()
        self.refresh_calculations()

    def _load_currency(self):
        """Standardized currency symbol discovery."""
        self.currency_symbol = get_project_currency_symbol(self.project_dir)

    def _scan_actual_project_cost(self):
        """
        Scans all database tables in priced BOQs folder to extract 
        the exact actual total cost for real-time benchmarking comparison.
        """
        self.actual_project_net = 0.0
        if not os.path.exists(self.pboq_folder): 
            return
            
        total_net = 0.0
        files = [f for f in os.listdir(self.pboq_folder) if f.lower().endswith('.db')]
        
        # Retrieve overhead/profit factors
        overhead_rate = 0.0
        profit_rate = 0.0
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
                        if row: overhead_rate = float(row[0])
                        
                        cursor.execute("SELECT value FROM settings WHERE key='profit'")
                        row = cursor.fetchone()
                        if row: profit_rate = float(row[0])
                    except: pass
                    conn.close()
        except: pass
        
        combined_markup = 1.0 + ((overhead_rate + profit_rate) / 100.0)

        for f in files:
            db_path = os.path.join(self.pboq_folder, f)
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                # Use standard PBOQ database scanner to sum bill amounts
                cursor.execute("PRAGMA table_info(pboq_items)")
                cols = [info[1] for info in cursor.fetchall()]
                
                # Retrieve bill amount mapping
                mapping_file = os.path.join(self.project_dir, "PBOQ States", f + ".json")
                b_col = None
                if os.path.exists(mapping_file):
                    try:
                        with open(mapping_file, 'r') as sf:
                            m = json.load(sf).get('mappings', {})
                            b_idx = m.get('bill_amount')
                            if b_idx is not None and (b_idx + 1) < len(cols):
                                b_col = cols[b_idx + 1]
                    except: pass
                
                if not b_col:
                    b_col = next((c for c in cols if c.lower() in ["bill amount", "billamount", "column 5"]), None)
                
                if b_col:
                    cursor.execute(f"SELECT SUM(CAST(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(\"{b_col}\", ',', ''), ' ', ''), '₵', ''), '$', ''), 'GH¢', '') AS REAL)) FROM pboq_items")
                    row = cursor.fetchone()
                    if row and row[0]:
                        total_net += float(row[0])
                conn.close()
            except: pass
            
        # Apply exact combined markup to get true project value
        self.actual_project_net = total_net * combined_markup

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
        header = QLabel("Parametric Benchmarking (Cost/m²)")
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
        
        input_title = QLabel("Parametric Estimator & Scenario Modeler")
        input_title.setStyleSheet("font-family: 'Inter'; font-weight: 700; color: #1e293b; font-size: 15px;")
        input_layout.addWidget(input_title)
        
        # Gross Floor Area (GFA) input
        gfa_lbl_lay = QHBoxLayout()
        gfa_lbl = QLabel("Gross Floor Area (GFA):")
        gfa_lbl.setStyleSheet("font-weight: 600; color: #475569; font-size: 12px;")
        self.gfa_val_lbl = QLabel("150 m²")
        self.gfa_val_lbl.setStyleSheet("font-weight: 800; color: #166534; font-size: 13px; font-family: 'Consolas';")
        gfa_lbl_lay.addWidget(gfa_lbl)
        gfa_lbl_lay.addStretch()
        gfa_lbl_lay.addWidget(self.gfa_val_lbl)
        input_layout.addLayout(gfa_lbl_lay)
        
        self.gfa_slider = QSlider(Qt.Orientation.Horizontal)
        self.gfa_slider.setMinimum(10)
        self.gfa_slider.setMaximum(2500)
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
        
        # Divider Line
        div_l = QFrame()
        div_l.setFrameShape(QFrame.Shape.HLine)
        div_l.setStyleSheet("background-color: #f1f5f9; min-height: 1px;")
        input_layout.addWidget(div_l)
        
        # Project Benchmarker Section (Integrates current priced PBOQs)
        proj_title = QLabel("Actual Project Estimator")
        proj_title.setStyleSheet("font-family: 'Inter'; font-weight: 700; color: #1e40af; font-size: 13px; margin-top: 5px;")
        input_layout.addWidget(proj_title)
        
        act_gfa_lay = QHBoxLayout()
        act_gfa_lbl = QLabel("Actual GFA input (m²):")
        act_gfa_lbl.setStyleSheet("font-weight: 600; color: #475569; font-size: 11px;")
        act_gfa_lay.addWidget(act_gfa_lbl)
        
        self.act_gfa_spin = QDoubleSpinBox()
        self.act_gfa_spin.setMinimum(1.0)
        self.act_gfa_spin.setMaximum(100000.0)
        self.act_gfa_spin.setValue(180.0)
        self.act_gfa_spin.valueChanged.connect(self.refresh_calculations)
        self.act_gfa_spin.setStyleSheet("padding: 5px; border-radius: 6px; border: 1px solid #cbd5e1; font-family: 'Consolas'; font-size: 11px;")
        act_gfa_lay.addWidget(self.act_gfa_spin)
        input_layout.addLayout(act_gfa_lay)
        
        self.refresh_btn = QPushButton("🔄 Scan Project Databases")
        self.refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_btn.clicked.connect(self.refresh_data)
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #f1f5f9;
                color: #1e293b;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 8px;
                font-weight: 600;
                font-size: 10px;
                font-family: 'Inter';
            }
            QPushButton:hover {
                background-color: #e2e8f0;
            }
        """)
        input_layout.addWidget(self.refresh_btn)
        
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
        
        main_grid.addWidget(kpi_parent, 0, 1)
        
        # Right Panel Bottom: Dynamic Custom Painted Graphical Charts
        charts_frame = QFrame()
        charts_frame.setStyleSheet("background-color: white; border-radius: 16px; border: 1px solid #e2e8f0;")
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
        
        main_grid.addWidget(charts_frame, 1, 1)
        content_layout.addLayout(main_grid)
        
        # 3. Informational & Educational Card Section (Formula Guide)
        edu_card = QFrame()
        edu_card.setStyleSheet("background-color: #f8fafc; border-radius: 16px; border: 1.5px dashed #cbd5e1;")
        edu_layout = QVBoxLayout(edu_card)
        edu_layout.setContentsMargins(25, 25, 25, 25)
        edu_layout.setSpacing(15)
        
        edu_title_lay = QHBoxLayout()
        edu_icon = QLabel("📐")
        edu_icon.setStyleSheet("font-size: 22px;")
        edu_title = QLabel("Quantity Surveyor's Guide to Cost/m² Parametrics")
        edu_title.setStyleSheet("font-family: 'Outfit'; font-weight: bold; color: #0f172a; font-size: 18px;")
        edu_title_lay.addWidget(edu_icon)
        edu_title_lay.addWidget(edu_title)
        edu_title_lay.addStretch()
        edu_layout.addLayout(edu_title_lay)
        
        formula_box = QFrame()
        formula_box.setStyleSheet("background-color: #ffffff; border-radius: 8px; border: 1px solid #e2e8f0; padding: 12px;")
        formula_lay = QVBoxLayout(formula_box)
        
        formula_math = QLabel("Cost per m² = Total Construction Cost / Gross Floor Area (GFA) or Plinth Area")
        formula_math.setStyleSheet("font-family: 'Consolas'; font-weight: 700; color: #166534; font-size: 13px;")
        formula_math.setAlignment(Qt.AlignmentFlag.AlignCenter)
        formula_lay.addWidget(formula_math)
        edu_layout.addWidget(formula_box)
        
        body_lay = QHBoxLayout()
        body_lay.setSpacing(20)
        
        col1_layout = QVBoxLayout()
        col1_layout.setSpacing(10)
        
        c1_t = QLabel("<b>Definitions & Scope</b>")
        c1_t.setStyleSheet("font-size: 13px; color: #0f172a;")
        col1_layout.addWidget(c1_t)
        
        c1_desc = QLabel(
            "<b>Total Construction Cost:</b> Includes structural work, secondary works, and standard finishes. "
            "It generally excludes land purchase, site utility servicing, and external legal fees.<br/><br/>"
            "<b>Gross Floor Area (GFA):</b> The total area of all floors measured to the outside face of external walls."
        )
        c1_desc.setWordWrap(True)
        c1_desc.setStyleSheet("color: #475569; font-size: 11px; line-height: 1.5;")
        col1_layout.addWidget(c1_desc)
        
        c1_uses = QLabel("<b>Common Uses in Estimating</b>")
        c1_uses.setStyleSheet("font-size: 13px; color: #0f172a; margin-top: 5px;")
        col1_layout.addWidget(c1_uses)
        
        c1_uses_desc = QLabel(
            "• <b>Feasibility Studies:</b> Helps clients understand if a project is financially viable.<br/>"
            "• <b>Early-Stage Budgeting:</b> Allows estimators to scale costs based on project size before detailed designs exist.<br/>"
            "• <b>Comparison:</b> Empowers quantity surveyors to benchmark quotes against past, similar projects."
        )
        c1_uses_desc.setWordWrap(True)
        c1_uses_desc.setStyleSheet("color: #475569; font-size: 11px; line-height: 1.5;")
        col1_layout.addWidget(c1_uses_desc)
        
        col2_layout = QVBoxLayout()
        col2_layout.setSpacing(10)
        
        c2_t = QLabel("<b>Key Variables That Distort Cost/m²</b>")
        c2_t.setStyleSheet("font-size: 13px; color: #c2410c;")
        col2_layout.addWidget(c2_t)
        
        c2_desc = QLabel(
            "Relying solely on a single flat rate can be highly inaccurate because no two buildings are identical. "
            "Costs scale drastically based on the following:<br/><br/>"
            "• <b>Room Functionality:</b> 'Wet areas' like kitchens and bathrooms cost significantly more per m² "
            "than bedrooms due to heavy plumbing, high-end cabinetry, and premium tiling.<br/>"
            "• <b>Building Complexity:</b> Complex, multi-angled perimeters require more structural materials, forming, "
            "and labor than simple square footprints, driving up the rates.<br/>"
            "• <b>Quality of Specification:</b> High-end, premium finishes easily double or triple the basic structural rate.<br/>"
            "• <b>Site Conditions:</b> Difficult soil, steep slopes, or poor utility access create heavy groundwork "
            "expenses that are independent of the building's floor area."
        )
        c2_desc.setWordWrap(True)
        c2_desc.setStyleSheet("color: #475569; font-size: 11px; line-height: 1.5;")
        col2_layout.addWidget(c2_desc)
        
        body_lay.addLayout(col1_layout, 1)
        body_lay.addLayout(col2_layout, 1)
        edu_layout.addLayout(body_lay)
        
        # Source Citation & PDF Open Section
        source_box = QFrame()
        source_box.setStyleSheet("background-color: #f1f5f9; border-radius: 12px; border: 1px solid #e2e8f0; padding: 15px; margin-top: 10px;")
        source_lay = QHBoxLayout(source_box)
        source_lay.setContentsMargins(15, 10, 15, 10)
        source_lay.setSpacing(15)
        
        cite_icon = QLabel("📖")
        cite_icon.setStyleSheet("font-size: 20px; border: none; background: transparent;")
        
        cite_txt = QLabel(
            "<b>Institutional Reference Source:</b> "
            "Ghana Institution of Surveyors (GhIS) Standard Cost Indices & "
            "<b>AECOM Africa Property & Construction Cost Guide 2025</b>."
        )
        cite_txt.setStyleSheet("color: #334155; font-size: 11px; font-family: 'Inter'; border: none; background: transparent;")
        cite_txt.setWordWrap(True)
        
        self.open_pdf_btn = QPushButton("📄 Open AECOM Cost Guide 2025")
        self.open_pdf_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_pdf_btn.clicked.connect(self.open_aecom_guide)
        self.open_pdf_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e40af;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 16px;
                font-weight: bold;
                font-size: 11px;
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
        self.gfa_val_lbl.setText(f"{value} m²")
        self.refresh_calculations()

    def _on_complexity_changed(self, index):
        factors = ["Simple (1.00x)", "Moderate (1.15x)", "High (1.35x)"]
        self.comp_val_lbl.setText(factors[index])
        self.refresh_calculations()

    def refresh_data(self):
        """Re-scans databases and updates graphs/metric cards."""
        self._scan_actual_project_cost()
        self.refresh_calculations()

    def refresh_calculations(self):
        """
        Main calculation engine that translates slider options 
        and inputs into beautiful visual cost models in real time.
        """
        gfa = float(self.gfa_slider.value())
        
        # 1. Base Rates for target types ( Accra baseline )
        base_rates = {
            "Residential House": 750.0,
            "Commercial Office": 1200.0,
            "Retail / Showroom": 950.0,
            "Industrial / Warehouse": 500.0,
            "Extension / Add-on": 800.0
        }
        b_type = self.type_combo.currentText()
        base_rate = base_rates.get(b_type, 750.0)
        
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
        wet_prem_rate = wet_premiums[spec_idx]
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
        actual_gfa = self.act_gfa_spin.value()
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
            "gfa": self.gfa_slider.value(),
            "building_type_idx": self.type_combo.currentIndex(),
            "region_idx": self.region_combo.currentIndex(),
            "spec_idx": self.spec_combo.currentIndex(),
            "complexity_idx": self.comp_combo.currentIndex(),
            "wet_areas": self.wet_spin.value(),
            "site_conditions_idx": self.site_combo.currentIndex(),
            "actual_gfa": self.act_gfa_spin.value()
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
            self.act_gfa_spin.blockSignals(True)
            
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
            if "actual_gfa" in state:
                self.act_gfa_spin.setValue(state["actual_gfa"])
                
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
            self.act_gfa_spin.blockSignals(False)

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
