import os
import sqlite3
import json
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QFrame, QGridLayout, QScrollArea, QGraphicsDropShadowEffect)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QColor, QFont, QPainter, QLinearGradient

import pboq_constants as const
from pboq_logic import PBOQLogic

class MetricCard(QFrame):
    """A premium, styled card for displaying KPI headline metrics."""
    def __init__(self, title, value, subtext="", color="#2e7d32", parent=None):
        super().__init__(parent)
        self.setFixedSize(240, 110)
        self.setObjectName("MetricCard")
        
        # Enhanced Styling
        self.setStyleSheet(f"""
            QFrame#MetricCard {{
                background-color: white;
                border-radius: 12px;
                border: 1px solid #e0e0e0;
            }}
        """)
        
        # Shadow Effect
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(15)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 40))
        self.setGraphicsEffect(shadow)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(5)
        
        self.title_label = QLabel(title.upper())
        self.title_label.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 11px; letter-spacing: 1px;")
        
        self.value_label = QLabel(value)
        self.value_label.setStyleSheet("color: #212121; font-weight: 800; font-size: 20px;")
        self.value_label.setWordWrap(True)
        
        self.subtext_label = QLabel(subtext)
        self.subtext_label.setStyleSheet("color: #757575; font-size: 12px;")
        
        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)
        layout.addStretch()
        layout.addWidget(self.subtext_label)

    def update_value(self, value, subtext=None):
        self.value_label.setText(value)
        if subtext is not None:
            self.subtext_label.setText(subtext)

class AnalyticsDashboard(QWidget):
    """The central hub for project-wide financial and progress analytics."""
    def __init__(self, project_dir, parent=None):
        super().__init__(parent)
        self.project_dir = project_dir
        self.pboq_folder = os.path.join(self.project_dir, "Priced BOQs")
        self.setWindowTitle("Project Analytics Dashboard")
        
        self._init_ui()
        self.refresh_data()

    def _init_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 20, 20, 20)
        self.layout.setSpacing(15)
        
        # Header
        header_layout = QHBoxLayout()
        title_label = QLabel("Project Performance Analytics")
        title_label.setStyleSheet("font-size: 22px; font-weight: 800; color: #1b5e20;")
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        
        self.project_name_label = QLabel(os.path.basename(self.project_dir))
        self.project_name_label.setStyleSheet("font-size: 14px; color: #666; font-style: italic;")
        header_layout.addWidget(self.project_name_label)
        
        self.layout.addLayout(header_layout)
        
        # Headline Cards Grid
        self.cards_layout = QGridLayout()
        self.cards_layout.setSpacing(20)
        
        self.card_total_bid = MetricCard("Total Bid Value", "$0.00", "0 items priced", color="#1b5e20")
        self.card_progress = MetricCard("Pricing Progress", "0%", "0 of 0 completed", color="#0277bd")
        self.card_risk = MetricCard("Review Flags", "0", "High risk items detected", color="#c62828")
        self.card_confidence = MetricCard("Confidence Index", "N/A", "Pricing source analysis", color="#ef6c00")
        
        self.cards_layout.addWidget(self.card_total_bid, 0, 0)
        self.cards_layout.addWidget(self.card_progress, 0, 1)
        self.cards_layout.addWidget(self.card_risk, 0, 2)
        self.cards_layout.addWidget(self.card_confidence, 0, 3)
        
        self.layout.addLayout(self.cards_layout)
        
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
        
        self.breakdown_container = QWidget()
        self.breakdown_list = QVBoxLayout(self.breakdown_container)
        self.breakdown_list.setSpacing(10)
        self.breakdown_list.addStretch()
        
        self.scroll_area.setWidget(self.breakdown_container)
        breakdown_layout.addWidget(self.scroll_area)
        
        self.layout.addWidget(breakdown_group, 1) # Give breakdown more stretch
        
        self.layout.addStretch()

    def refresh_data(self):
        """Aggregates data across all PBOQ databases in the project folder."""
        if not os.path.exists(self.pboq_folder):
            return

        total_bid = 0.0
        total_items = 0
        priced_items = 0
        flagged_items = 0
        
        sources = {
            'library': 0, # Green
            'manual': 0,  # Purple
            'sub': 0,     # Orange
            'provisional': 0, # Blue/Cyan
        }
        
        sheet_data = []

        for f in os.listdir(self.pboq_folder):
            if f.lower().endswith('.db'):
                db_path = os.path.join(self.pboq_folder, f)
                
                # Load mappings from state file if it exists
                qty_col = -1
                unit_col = -1
                desc_col = -1
                state_file = os.path.join(self.project_dir, "PBOQ States", f + ".json")
                if os.path.exists(state_file):
                    try:
                        with open(state_file, 'r') as sf:
                            state = json.load(sf)
                            m = state.get('mappings', {})
                            qty_col = m.get('qty', -1)
                            unit_col = m.get('unit', -1)
                            desc_col = m.get('desc', -1)
                    except: pass
                
                # Smart-Detection Fallback: If not mapped, try to find them by name
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
                                qty_col = i - 1 # Adjusted because index 0 is Sheet
                            if unit_col < 0 and clean_name == "unit":
                                unit_col = i - 1
                            if desc_col < 0 and clean_name in ["description", "desc"]:
                                desc_col = i - 1
                    
                    # Construct dynamic item detection clause based on user definition:
                    # An item MUST have a Description AND (Quantity OR Unit OR Price).
                    # This firmly filters out headings (Description only) and rogue numbers (No description).
                    item_clause = "(1=0)" # Default to none if no useful columns found
                    req_parts = []
                    if desc_col >= 0 or unit_col >= 0 or qty_col >= 0:
                        cursor.execute("PRAGMA table_info(pboq_items)")
                        actual_cols = [info[1] for info in cursor.fetchall()]
                        
                        desc_name = actual_cols[desc_col+1] if desc_col >= 0 and (desc_col+1) < len(actual_cols) else None
                        qty_name = actual_cols[qty_col+1] if qty_col >= 0 and (qty_col+1) < len(actual_cols) else None
                        unit_name = actual_cols[unit_col+1] if unit_col >= 0 and (unit_col+1) < len(actual_cols) else None
                        
                        if desc_name:
                            desc_check = f"(TRIM(\"{desc_name}\") != '' AND \"{desc_name}\" IS NOT NULL)"
                            
                            # Mandatory Combination: Description + (Non-Zero Numeric Quantity AND Non-Empty Unit) OR Price
                            or_parts = []
                            if qty_name and unit_name:
                                # Strict check for numeric quantity and a legitimate unit
                                qty_check = f"(TYPEOF(CAST(\"{qty_name}\" AS REAL)) = 'real' AND CAST(\"{qty_name}\" AS REAL) != 0)"
                                unit_check = f"(TRIM(\"{unit_name}\") != '' AND \"{unit_name}\" IS NOT NULL)"
                                or_parts.append(f"({qty_check} AND {unit_check})")
                            
                            # Check for any valid price in any typical 'Bill Amount' variant
                            price_variants = ["Bill Amount", "BillAmount", "Bill Rate", "BillRate"]
                            for pv in price_variants:
                                if pv in actual_cols:
                                    or_parts.append(f"(\"{pv}\" > 0 AND \"{pv}\" != '' AND \"{pv}\" IS NOT NULL)")
                                    
                            if or_parts:
                                item_clause = f"({desc_check} AND ({' OR '.join(or_parts)}))"

                    # 1. Sheet Summaries
                    q1 = f"""
                        SELECT Sheet, 
                               SUM(CASE WHEN {item_clause} THEN 1 ELSE 0 END), 
                               SUM(CASE WHEN {item_clause} AND "Bill Amount" > 0 THEN 1 ELSE 0 END), 
                               SUM(CAST("Bill Amount" AS REAL)) 
                        FROM pboq_items 
                        GROUP BY Sheet
                    """
                    cursor.execute(q1)
                    for sheet, count, priced, amt in cursor.fetchall():
                        sheet_data.append({
                            'name': f"{f.replace('.db','')} - {sheet}",
                            'total': count,
                            'priced': priced,
                            'amount': amt or 0.0
                        })
                    
                    # 2. General Aggregates
                    q2 = f"""
                        SELECT SUM(CAST("Bill Amount" AS REAL)), 
                               SUM(CASE WHEN {item_clause} THEN 1 ELSE 0 END), 
                               SUM(IsFlagged) 
                        FROM pboq_items
                    """
                    cursor.execute(q2)
                    row = cursor.fetchone()
                    if row:
                        total_bid += (row[0] or 0.0)
                        total_items += (row[1] or 0)
                        flagged_items += (row[2] or 0)
                        
                    # 3. Source Analysis (PCI)
                    # We check logical columns to see which source was used.
                    cursor.execute("""
                        SELECT 
                            SUM(CASE WHEN GrossRate != '' AND GrossRate IS NOT NULL THEN 1 ELSE 0 END),
                            SUM(CASE WHEN PlugRate != '' AND PlugRate IS NOT NULL THEN 1 ELSE 0 END),
                            SUM(CASE WHEN SubbeeRate != '' AND SubbeeRate IS NOT NULL THEN 1 ELSE 0 END),
                            SUM(CASE WHEN ProvSum != '' AND ProvSum IS NOT NULL THEN 1 ELSE 0 END)
                        FROM pboq_items
                    """)
                    src_row = cursor.fetchone()
                    if src_row:
                        sources['library'] += src_row[0] or 0
                        sources['manual'] += src_row[1] or 0
                        sources['sub'] += src_row[2] or 0
                        sources['provisional'] += src_row[3] or 0
                        
                    conn.close()
                except Exception as e:
                    print(f"Error reading {f}: {e}")

        # Final Counts
        priced_items = sources['library'] + sources['manual'] + sources['sub'] + sources['provisional']
        
        # Update Cards
        self.card_total_bid.update_value(f"${total_bid:,.2f}", f"Total cross-project value")
        
        progress_pct = (priced_items / total_items * 100) if total_items > 0 else 0
        self.card_progress.update_value(f"{progress_pct:.1f}%", f"{priced_items} of {total_items} items priced")
        
        self.card_risk.update_value(str(flagged_items), "Items flagged for review")
        
        # PCI Logic
        confidence = "N/A"
        if priced_items > 0:
            lib_pct = (sources['library'] / priced_items * 100)
            if lib_pct > 70: confidence = "HIGH"
            elif lib_pct > 40: confidence = "MEDIUM"
            else: confidence = "LOW"
        self.card_confidence.update_value(confidence, f"{int(lib_pct if priced_items > 0 else 0)}% verified library rates")

        # Update Breakdown List
        self._clear_breakdown()
        for s in sheet_data:
            self._add_sheet_row(s)

    def _clear_breakdown(self):
        while self.breakdown_list.count() > 1: # Keep the stretch
            item = self.breakdown_list.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _add_sheet_row(self, data):
        row = QFrame()
        row.setStyleSheet("background-color: #f5f5f5; border-radius: 6px; border: none; padding: 5px;")
        l = QHBoxLayout(row)
        
        name = QLabel(data['name'])
        name.setStyleSheet("font-weight: bold; color: #444;")
        
        progress = QLabel(f"{data['priced']}/{data['total']} items")
        progress.setStyleSheet("color: #666;")
        
        amount = QLabel(f"${data['amount']:,.2f}")
        amount.setStyleSheet("font-weight: 800; color: #2e7d32;")
        
        l.addWidget(name)
        l.addStretch()
        l.addWidget(progress)
        l.addSpacing(20)
        l.addWidget(amount)
        
        self.breakdown_list.insertWidget(self.breakdown_list.count() - 1, row)
