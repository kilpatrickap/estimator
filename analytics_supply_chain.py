import os
import sqlite3
import json
import re
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QFrame, QScrollArea, QSpacerItem, QSizePolicy, QDialog, QPushButton)
from PyQt6.QtCore import Qt, pyqtSignal, QRectF, QPointF
from PyQt6.QtGui import QColor, QPainter, QBrush, QPen, QFont, QLinearGradient
from analytics_components import MetricCard, ChartWidget

class BidderRow(QFrame):
    """A row in the submitted bidders table, matching analytics UI consistency."""
    def __init__(self, name, amount, target_val, is_winner=False, is_header=False, parent=None):
        super().__init__(parent)
        self.is_header = is_header
        self.is_winner = is_winner
        self._update_style()
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 10, 15, 10)
        layout.setSpacing(15)
        
        style = "font-family: 'Inter'; font-size: 12px; color: #1e293b;"
        if is_header:
            style = "font-family: 'Inter'; font-weight: 700; color: #64748b; font-size: 11px; text-transform: uppercase;"
            
        # 1. Name
        n_lbl = QLabel(name)
        n_lbl.setStyleSheet(style + " border: none;")
        n_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(n_lbl, 3)
        
        # 2. Amount
        a_lbl = QLabel(f"${amount:,.2f}" if not is_header else "Quote Amount")
        a_lbl.setStyleSheet(style + " font-family: 'Consolas'; font-weight: 700; color: #334155;")
        a_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(a_lbl, 2)
        
        # 3. Variance
        var = target_val - amount
        var_pct = (var / target_val * 100) if target_val > 0 else 0
        v_color = "#166534" if var >= 0 else "#991b1b"
        v_str = f"{var_pct:+.1f}%" if not is_header else "Variance"
        
        v_lbl = QLabel(v_str)
        if not is_header:
            v_lbl.setStyleSheet(f"font-family: 'Inter'; font-weight: 800; color: {v_color}; font-size: 11px;")
        else:
            v_lbl.setStyleSheet(style)
        v_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(v_lbl, 1)
        
        # 4. Status Badge
        status_pill = QFrame()
        sp_layout = QHBoxLayout(status_pill)
        sp_layout.setContentsMargins(8, 2, 8, 2)
        
        s_lbl = QLabel("AWARDED" if is_winner else "OPEN")
        if is_header: s_lbl.setText("Status")
        
        s_color = "#166534" if is_winner else "#64748b"
        s_bg = "#f0fdf4" if is_winner else "#f8fafc"
        s_border = "#bbf7d0" if is_winner else "#e2e8f0"
        
        status_pill.setStyleSheet(f"background-color: {s_bg}; border-radius: 4px; border: 1px solid {s_border};")
        s_lbl.setStyleSheet(f"font-family: 'Inter'; font-weight: 800; color: {s_color}; font-size: 9px; border: none;")
        s_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sp_layout.addWidget(s_lbl)
        
        if is_header: status_pill.setStyleSheet("background: transparent; border: none;")
        layout.addWidget(status_pill, 1)

    def _update_style(self):
        if self.is_header:
            bg, border = "#f8fafc", "#cbd5e1"
        elif self.is_winner:
            bg, border = "#f0fdf4", "#10b981"
        else:
            bg, border = "#ffffff", "#e2e8f0"
            
        self.setStyleSheet(f"""
            BidderRow {{ background-color: {bg}; border-radius: 8px; border: 1px solid {border}; }}
            BidderRow:hover {{ border: 1px solid #166534; }}
        """)

class SubmittedBiddersDialog(QDialog):
    """A premium dialog showing a detailed table of all submitted bidders for a package."""
    def __init__(self, package_name, target_val, all_bids, winner_name, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Submitted Bidders - {package_name}")
        self.setMinimumSize(650, 500)
        self.setStyleSheet("background-color: #f1f5f9;") # Match main dashboard bg
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)
        
        # Header Section
        header_card = QFrame()
        header_card.setStyleSheet("background-color: white; border-radius: 12px; border: 1px solid #e2e8f0;")
        hc_layout = QVBoxLayout(header_card)
        hc_layout.setContentsMargins(20, 15, 20, 15)
        
        title_lbl = QLabel(f"Adjudication Breakdown: {package_name}")
        title_lbl.setStyleSheet("font-family: 'Inter'; font-size: 20px; font-weight: 800; color: #1e293b;")
        hc_layout.addWidget(title_lbl)
        
        target_info = QLabel(f"Internal Target Budget: <span style='font-family: Consolas; font-weight: bold; color: #166534;'>${target_val:,.2f}</span>")
        target_info.setStyleSheet("font-family: 'Inter'; font-size: 13px; color: #64748b;")
        hc_layout.addWidget(target_info)
        layout.addWidget(header_card)
        
        # Table Container
        table_frame = QFrame()
        table_frame.setStyleSheet("background-color: white; border-radius: 12px; border: 1px solid #e2e8f0;")
        table_layout = QVBoxLayout(table_frame)
        table_layout.setContentsMargins(15, 15, 15, 15)
        
        # Header Row
        table_layout.addWidget(BidderRow("SUBCONTRACTOR NAME", 0, 0, is_header=True))
        
        # List Area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none; background: transparent;")
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        list_layout = QVBoxLayout(container)
        list_layout.setSpacing(6)
        list_layout.addStretch()
        
        sorted_bids = sorted(all_bids.items(), key=lambda x: x[1])
        for s_name, s_val in sorted_bids:
            row = BidderRow(s_name, s_val, target_val, is_winner=(s_name == winner_name))
            list_layout.insertWidget(list_layout.count()-1, row)
            
        scroll.setWidget(container)
        table_layout.addWidget(scroll)
        layout.addWidget(table_frame)
        
        # Actions
        btn_box = QHBoxLayout()
        btn_box.addStretch()
        close_btn = QPushButton("Done")
        close_btn.setFixedSize(140, 45)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #2e7d32; color: #ffeb3b; border-radius: 8px; 
                font-family: 'Inter'; font-weight: 700; font-size: 13px;
            }
            QPushButton:hover { background-color: #1b5e20; }
        """)
        close_btn.clicked.connect(self.accept)
        btn_box.addWidget(close_btn)
        layout.addLayout(btn_box)

class SupplyChainRow(QFrame):
    clicked = pyqtSignal(object)
    bidsClicked = pyqtSignal(object) # New signal for bids interaction

    def __init__(self, name, bids_count, target_val, min_val, max_val, winner_val, winner_name="", all_bids=None, is_header=False, is_total=False, parent=None):
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
            
        # 1. Package Name (Include Winner in brackets if present)
        display_name = name
        if not is_header and not is_total and winner_name:
            display_name = f"{name} ({winner_name})"
            
        name_lbl = QLabel(display_name)
        name_lbl.setStyleSheet(style + " border: none;")
        name_lbl.setWordWrap(True)
        name_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(name_lbl, 4)
        
        # 2. Bids Count Pill (Interactive Button)
        b_border = "#6366f1" if not is_total else "none"
        self.bids_pill = QFrame()
        self.bids_pill.setStyleSheet(f"background-color: #f5f3ff; border-radius: 4px; border: 1px solid {b_border};")
        bp_layout = QHBoxLayout(self.bids_pill)
        bp_layout.setContentsMargins(4, 2, 4, 2)
        b_lbl = QLabel(str(bids_count) if not is_header else "Bids")
        b_lbl.setStyleSheet("font-family: 'Inter'; font-weight: 700; color: #6366f1; font-size: 11px; border: none;")
        b_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bp_layout.addWidget(b_lbl)
        
        if not is_header and not is_total and all_bids:
            tooltip = "<b>SUBMITTED BIDDERS:</b><br/>"
            sorted_bids = sorted(all_bids.items(), key=lambda x: x[1])
            for s, v in sorted_bids:
                is_win = " (Winner)" if s == winner_name else ""
                tooltip += f"<br/>• {s}: <b>${v:,.2f}</b>{is_win}"
            self.bids_pill.setToolTip(tooltip)
            self.bids_pill.setCursor(Qt.CursorShape.PointingHandCursor)
            
            # Capture bid details for dialog
            self.bid_context = (name, target_val, all_bids, winner_name)

        if is_header or is_total: self.bids_pill.setStyleSheet("background-color: transparent; border: none;")
        layout.addWidget(self.bids_pill, 1)
        
        # 3. Target Value
        t_lbl = QLabel(f"$ {target_val:,.2f}" if not is_header else "Target")
        t_lbl.setStyleSheet(style + " font-family: 'Consolas'; color: #475569;")
        t_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(t_lbl, 2)
        
        # 4. Winning Quote
        w_color = "#166534" if winner_val <= target_val else "#991b1b"
        w_lbl = QLabel(f"$ {winner_val:,.2f}" if not is_header else "Winner")
        if not is_header and not is_total:
            w_lbl.setStyleSheet(f"font-family: 'Consolas'; font-weight: 700; color: {w_color}; font-size: 12px;")
        else:
            w_lbl.setStyleSheet(style)
        w_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(w_lbl, 2)
        
        # 5. Savings (Absolute)
        savings = target_val - winner_val
        s_lbl = QLabel(f"$ {savings:,.2f}" if not is_header else "Savings")
        s_lbl.setStyleSheet(style + " font-family: 'Consolas'; font-weight: 700; color: #1e293b;")
        if not is_header and not is_total:
            s_lbl.setStyleSheet("font-family: 'Consolas'; font-weight: 700; color: #166534; font-size: 12px;")
        s_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(s_lbl, 2)
        
        # 6. Variance %
        var = target_val - winner_val
        var_pct = (var / target_val * 100) if target_val > 0 else 0
        var_color = "#166534" if var >= 0 else "#991b1b"
        var_str = f"{var_pct:+.1f}%" if not is_header else "Var %"
        if is_total: 
            var_str = f"AVG: {var_pct:+.1f}%"
        
        var_lbl = QLabel(var_str)
        if not is_header:
            v_style = f"font-family: 'Inter'; font-weight: 800; color: {var_color}; font-size: 11px;"
            if is_total: v_style = f"font-family: 'Inter'; font-weight: 800; color: {var_color}; font-size: 12px;"
            var_lbl.setStyleSheet(v_style)
        else:
            var_lbl.setStyleSheet(style)
        var_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(var_lbl, 2)

    def _update_style(self):
        if self.is_header:
            bg, border = "#f8fafc", "#cbd5e1"
        elif self.is_selected:
            bg, border = "#fffde7", "#fbc02d"
        elif self.is_total:
            bg, border = "#f1f8e9", "#2e7d32"
        else:
            bg, border = "#ffffff", "#e2e8f0"
            
        hover_bg = "#ecfdf5" if not (self.is_header or self.is_total) else bg
        
        self.setStyleSheet(f"""
            SupplyChainRow {{ background-color: {bg}; border-radius: 8px; border: 1px solid {border}; }}
            SupplyChainRow:hover {{ background-color: {hover_bg}; border: 1px solid #2e7d32; }}
        """)

    def set_selected(self, selected):
        if self.is_header or self.is_total: return
        self.is_selected = selected
        self._update_style()

    def mousePressEvent(self, event):
        # Check if click is on the bids pill
        child = self.childAt(event.pos())
        if hasattr(self, 'bids_pill') and (child == self.bids_pill or self.bids_pill.isAncestorOf(child)):
            self.bidsClicked.emit(self.bid_context)
            event.accept()
            return

        if not self.is_header and event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self)
        super().mousePressEvent(event)

class BidSpreadChart(ChartWidget):
    """Custom chart showing Min, Max, and Winning bid relative to Target with annotations and interactive hints."""
    def __init__(self, title, parent=None):
        super().__init__(title, parent)
        self.setMouseTracking(True)
        self.hit_boxes = [] # List of (rect, tooltip_text)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        self.hit_boxes = [] # Reset for this frame
        
        if not self.data:
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "No Adjudication Data Available")
            return

        # 1. Legend (Top Right)
        legend_font = QFont("Inter", 8, QFont.Weight.Medium)
        painter.setFont(legend_font)
        legend_x = rect.width() - 360
        legend_y = 15
        
        # Target
        painter.setPen(QPen(QColor("#94a3b8"), 1, Qt.PenStyle.DashLine))
        painter.drawLine(legend_x, legend_y + 6, legend_x + 20, legend_y + 6)
        painter.setPen(QPen(QColor("#64748b")))
        painter.drawText(legend_x + 25, legend_y + 10, "Internal Target")
        
        # Spread
        painter.setPen(QPen(QColor("#e2e8f0"), 4, cap=Qt.PenCapStyle.RoundCap))
        painter.drawLine(legend_x + 110, legend_y + 6, legend_x + 130, legend_y + 6)
        painter.setPen(QPen(QColor("#64748b")))
        painter.drawText(legend_x + 135, legend_y + 10, "Market Spread")
        
        # Winner
        painter.setBrush(QBrush(QColor("#166534")))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(legend_x + 235, legend_y + 6), 4, 4)
        painter.setPen(QPen(QColor("#64748b")))
        painter.drawText(legend_x + 245, legend_y + 10, "Selected Winner")

        # 2. Main Chart
        margin_left, margin_right, margin_top, margin_bottom = 120, 60, 50, 40
        chart_w = rect.width() - margin_left - margin_right
        chart_h = rect.height() - margin_top - margin_bottom
        
        pkg_count = len(self.data)
        row_h = min(40, chart_h / pkg_count)
        
        painter.setFont(QFont("Inter", 8))
        
        for i, (name, d) in enumerate(self.data):
            y = margin_top + i * row_h
            center_y = y + row_h / 2
            
            # Draw Label
            painter.setPen(QPen(QColor("#475569")))
            painter.drawText(QRectF(10, y, margin_left - 20, row_h), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, name)
            
            # Scaling
            local_max = max(d['target'], d['max'], d['winner'])
            if local_max == 0: continue
            
            def to_x(val): return margin_left + (val / local_max * chart_w)
            
            # 1. Target Line
            target_x = to_x(d['target'])
            painter.setPen(QPen(QColor("#94a3b8"), 1, Qt.PenStyle.DashLine))
            painter.drawLine(int(target_x), int(y + 5), int(target_x), int(y + row_h - 5))
            self.hit_boxes.append((QRectF(target_x - 5, y + 5, 10, row_h - 10), f"Budget Target: ${d['target']:,.2f}"))
            
            # 2. Spread Bar (Min to Max)
            min_x = to_x(d['min'])
            max_x = to_x(d['max'])
            painter.setPen(QPen(QColor("#e2e8f0"), 4, cap=Qt.PenCapStyle.RoundCap))
            painter.drawLine(int(min_x), int(center_y), int(max_x), int(center_y))
            
            spread_pct = ((d['max'] - d['min']) / d['min'] * 100) if d['min'] > 0 else 0
            self.hit_boxes.append((QRectF(min_x, center_y - 5, max_x - min_x, 10), 
                                  f"Market Range: ${d['min']:,.2f} - ${d['max']:,.2f}\nSpread: {spread_pct:.1f}%"))
            
            # 3. Min/Max Dots
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor("#94a3b8")))
            painter.drawEllipse(QPointF(min_x, center_y), 3, 3)
            painter.drawEllipse(QPointF(max_x, center_y), 3, 3)
            
            # 4. Winner Dot
            winner_x = to_x(d['winner'])
            is_saving = d['winner'] <= d['target']
            win_color = "#166534" if is_saving else "#991b1b"
            painter.setBrush(QBrush(QColor(win_color)))
            painter.drawEllipse(QPointF(winner_x, center_y), 5, 5)
            
            var = d['target'] - d['winner']
            var_pct = (abs(var) / d['target'] * 100) if d['target'] > 0 else 0
            status = "SAVING" if is_saving else "OVERRUN"
            self.hit_boxes.append((QRectF(winner_x - 8, center_y - 8, 16, 16), 
                                  f"Winner Quote: ${d['winner']:,.2f}\n{status}: ${abs(var):,.2f} ({var_pct:.1f}%)"))
            
            # 5. Connecting Winner to Target
            painter.setPen(QPen(QColor(win_color), 1))
            painter.drawLine(int(target_x), int(center_y), int(winner_x), int(center_y))

    def mouseMoveEvent(self, event):
        pos = event.position()
        found = False
        for rect, text in self.hit_boxes:
            if rect.contains(pos):
                self.setToolTip(text)
                found = True
                break
        if not found:
            self.setToolTip("")
        super().mouseMoveEvent(event)

class SupplyChainIntelligenceAnalytic(QWidget):
    def __init__(self, project_dir, parent=None):
        super().__init__(parent)
        self.project_dir = project_dir
        self.pboq_folder = os.path.join(project_dir, "Priced BOQs")
        self.pboq_state_dir = os.path.join(project_dir, "PBOQ States")
        self._selected_row = None
        
        self.currency_symbol = "$"
        self._init_ui()
        self.refresh_data()

    def _init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(15, 15, 15, 15)
        root_layout.setSpacing(15)

        # Header
        header = QLabel("Adjudication & Supply Chain Intelligence")
        header.setStyleSheet("font-family: 'Inter'; font-size: 24px; font-weight: 800; color: #1e293b;")
        root_layout.addWidget(header)

        # Scroll Area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 10, 0) # Tighter margins for small screens
        self.content_layout.setSpacing(15) # Reduced spacing
        
        # 1. KPI Row
        kpi_layout = QHBoxLayout()
        self.card_heat = MetricCard("MARKET HEAT", "0.0", "Avg bids per package", color="#6366f1")
        self.card_savings = MetricCard("ADJUDICATION SAVINGS", "$ 0.00", "Total vs. Target", color="#166534")
        self.card_risk = MetricCard("SINGLE SOURCE RISK", "0", "Packages with 1 bid", color="#991b1b")
        self.card_awarded = MetricCard("AWARDED VALUE", "$ 0.00", "Adjudicated total", color="#0369a1")
        
        for c in [self.card_heat, self.card_savings, self.card_risk, self.card_awarded]:
            kpi_layout.addWidget(c)
        self.content_layout.addLayout(kpi_layout)

        # 2. Charts Row
        charts_layout = QHBoxLayout()
        self.spread_chart = BidSpreadChart("Bid Spread Analysis")
        
        charts_layout.addWidget(self._create_card_frame("BID SPREAD ANALYSIS (MIN / MAX / WINNER vs TARGET)", self.spread_chart), 3)
        
        # Intelligence Guide Card
        guide_frame = QFrame()
        guide_frame.setStyleSheet("background-color: white; border-radius: 16px; border: 1px solid #e2e8f0;")
        guide_vbox = QVBoxLayout(guide_frame)
        guide_vbox.setContentsMargins(20, 20, 20, 20)
        
        guide_title = QLabel("HOW TO READ THE INTELLIGENCE")
        guide_title.setStyleSheet("font-family: 'Inter'; font-size: 13px; font-weight: 800; color: #64748b; letter-spacing: 1px;")
        guide_vbox.addWidget(guide_title)
        
        guide_text = QLabel("""
            <div style='font-family: Inter; color: #1e293b; line-height: 1.4;'>
                <p><b>• Wide Spread:</b> Indicates <b>Scope Ambiguity</b>. Market interpretations differ significantly.</p>
                <p><b>• Tight Spread:</b> Indicates <b>Market Certainty</b>. Scope and pricing are well-defined.</p>
                <p><b>• Winner far from Min:</b> Suggests a <b>Quality/Reliability</b> preference over lowest price.</p>
                <p><b>• Winner left of Target:</b> Represents a successful <b>Procurement Saving</b>.</p>
            </div>
        """)
        guide_text.setWordWrap(True)
        guide_vbox.addWidget(guide_text)
        guide_vbox.addStretch()
        
        charts_layout.addWidget(guide_frame, 1)
        self.content_layout.addLayout(charts_layout)

        # 3. Supply Chain Intelligence Table
        table_frame = QFrame()
        table_frame.setStyleSheet("background-color: white; border-radius: 16px; border: 1px solid #e2e8f0;")
        table_vbox = QVBoxLayout(table_frame)
        table_vbox.setContentsMargins(20, 20, 20, 20)
        
        table_header = QLabel("Supply Chain Adjudication Schedule")
        table_header.setStyleSheet("font-family: 'Inter'; font-size: 16px; font-weight: 700; color: #1e293b;")
        table_vbox.addWidget(table_header)
        
        self.package_list = QVBoxLayout()
        self.package_list.setSpacing(5)
        self.package_list.addStretch()
        
        self.table_scroll = QScrollArea()
        self.table_scroll.setMinimumHeight(300) # Flexible minimum instead of fixed 450
        self.table_scroll.setWidgetResizable(True)
        self.table_scroll.setStyleSheet("border: none; background: transparent;")
        self.table_container = QWidget()
        self.table_container.setStyleSheet("background: transparent;")
        self.table_container.setLayout(self.package_list)
        self.table_scroll.setWidget(self.table_container)
        
        table_vbox.addWidget(self.table_scroll)
        self.content_layout.addWidget(table_frame)

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
        """Aggregates adjudication data from all PBOQ databases."""
        if not os.path.exists(self.pboq_folder): return

        all_packages = {} # pkg_name -> {bids: [], target: 0, winner_name: "", winner_val: 0}
        
        db_files = [f for f in os.listdir(self.pboq_folder) if f.lower().endswith('.db')]
        
        for f in db_files:
            db_path = os.path.join(self.pboq_folder, f)
            mapping = self._get_pboq_mapping(f)
            
            # Map column names for Qty and Bill Rate
            q_idx = mapping.get('qty')
            br_idx = mapping.get('bill_rate')
            pkg_idx = mapping.get('sub_package')
            sw_idx = mapping.get('sub_name')
            sr_idx = mapping.get('sub_rate')
            
            if q_idx is None or br_idx is None or pkg_idx is None: continue
            
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info(pboq_items)")
                cols = [info[1] for info in cursor.fetchall()]
                
                # Dynamic column names
                q_col = cols[q_idx + 1]
                br_col = cols[br_idx + 1]
                pkg_col = cols[pkg_idx + 1]
                sw_col = cols[sw_idx + 1] if sw_idx is not None else None
                sr_col = cols[sr_idx + 1] if sr_idx is not None else None
                
                # 1. Load basic item data per package
                sel_cols = [f'"{pkg_col}"', f'"{q_col}"', f'"{br_col}"', "rowid"]
                if sw_col: sel_cols.append(f'"{sw_col}"')
                if sr_col: sel_cols.append(f'"{sr_col}"')
                
                query = f"SELECT {', '.join(sel_cols)} FROM pboq_items WHERE {f'\"{pkg_col}\"' } IS NOT NULL AND {f'\"{pkg_col}\"' } != ''"
                cursor.execute(query)
                
                pkg_items = {} # pkg -> {rowid -> {qty, target, winner_name, winner_val}}
                for row in cursor.fetchall():
                    p_name = row[0]
                    qty = self._to_float(row[1])
                    target = self._to_float(row[2])
                    rid = row[3]
                    w_name = row[4] if len(row) > 4 else ""
                    w_val = self._to_float(row[5]) if len(row) > 5 else 0.0
                    
                    if p_name not in all_packages:
                        all_packages[p_name] = {'bids': {}, 'target': 0.0, 'winner_name': "", 'winner_val': 0.0}
                    
                    all_packages[p_name]['target'] += (qty * target)
                    all_packages[p_name]['winner_val'] += (qty * w_val)
                    if w_name and not all_packages[p_name]['winner_name']:
                        all_packages[p_name]['winner_name'] = w_name
                        
                    if p_name not in pkg_items: pkg_items[p_name] = {}
                    pkg_items[p_name][rid] = {'qty': qty, 'target': target}

                # 2. Load all quotes for these packages
                cursor.execute("SELECT package_name, subcontractor_name, row_idx, rate FROM subcontractor_quotes")
                for p_name, s_name, rid, rate in cursor.fetchall():
                    if p_name in all_packages and rid in pkg_items[p_name]:
                        qty = pkg_items[p_name][rid]['qty']
                        amt = qty * (rate or 0)
                        
                        if s_name not in all_packages[p_name]['bids']:
                            all_packages[p_name]['bids'][s_name] = 0.0
                        all_packages[p_name]['bids'][s_name] += amt
                
                conn.close()
            except Exception as e:
                print(f"Error processing {f} for Supply Chain Analytics: {e}")

        # 3. Calculate Intelligence Metrics
        total_target = 0.0
        total_winner = 0.0
        total_bids_count = 0
        single_source_count = 0
        spread_data = [] # (name, {target, min, max, winner})
        
        valid_packages = []
        for p_name, data in all_packages.items():
            bids = list(data['bids'].values())
            if not bids: continue
            
            b_count = len(bids)
            total_bids_count += b_count
            if b_count == 1: single_source_count += 1
            
            p_min = min(bids)
            p_max = max(bids)
            p_winner = data['winner_val'] if data['winner_val'] > 0 else p_min
            
            total_target += data['target']
            total_winner += p_winner
            
            spread_data.append((p_name, {
                'target': data['target'],
                'min': p_min,
                'max': p_max,
                'winner': p_winner,
                'bids_count': b_count
            }))
            
            valid_packages.append({
                'name': p_name,
                'bids_count': b_count,
                'target': data['target'],
                'min': p_min,
                'max': p_max,
                'winner': p_winner,
                'winner_name': data['winner_name'],
                'all_bids': data['bids']
            })

        # Update KPIs
        avg_heat = total_bids_count / len(valid_packages) if valid_packages else 0
        savings = total_target - total_winner
        
        self.card_heat.update_value(f"{avg_heat:.1f}")
        self.card_savings.update_value(f"{self.currency_symbol}{savings:,.2f}")
        self.card_risk.update_value(str(single_source_count))
        self.card_awarded.update_value(f"{self.currency_symbol}{total_winner:,.2f}")
        
        # Update Chart
        self.spread_chart.set_data(spread_data[:12]) # Show top 12 for legibility

        # Update Table
        self._clear_table(self.package_list)
        self._add_row(("PACKAGE NAME", "BIDS", 0, 0, 0, 0), is_header=True)
        
        # Sort by target value descending
        for p in sorted(valid_packages, key=lambda x: x['target'], reverse=True):
            self._add_row((p['name'], p['bids_count'], p['target'], p['min'], p['max'], p['winner'], p['winner_name'], p['all_bids']))
            
        if valid_packages:
            self._add_row(("TOTAL ADJUDICATED PORTFOLIO", total_bids_count, total_target, 0, 0, total_winner), is_total=True)

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

    def _add_row(self, data, is_header=False, is_total=False):
        if is_header or is_total:
            row = SupplyChainRow(data[0], data[1], data[2], data[3], data[4], data[5], is_header=is_header, is_total=is_total)
        else:
            row = SupplyChainRow(data[0], data[1], data[2], data[3], data[4], data[5], winner_name=data[6], all_bids=data[7], is_header=is_header, is_total=is_total)
            row.bidsClicked.connect(self._show_bidders_details)
            
        if not is_header and not is_total:
            row.clicked.connect(self._handle_row_click)
        self.package_list.insertWidget(self.package_list.count()-1, row)

    def _show_bidders_details(self, context):
        """Opens the nice 'Submitted Bidders' table dialog."""
        pkg_name, target, bids, winner = context
        dialog = SubmittedBiddersDialog(pkg_name, target, bids, winner, self)
        dialog.exec()

    def _handle_row_click(self, row):
        if self._selected_row and self._selected_row != row:
            try: self._selected_row.set_selected(False)
            except: pass
        self._selected_row = row
        self._selected_row.set_selected(True)
