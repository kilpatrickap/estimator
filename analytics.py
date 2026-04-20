import os
import sqlite3
import json
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QFrame, QGridLayout, QScrollArea, QGraphicsDropShadowEffect,
                             QPushButton, QSpacerItem, QSizePolicy, QDockWidget, QStackedWidget)
from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QColor, QFont

class AnalyticsPane(QWidget):
    """Left-hand sidebar pane for Project Analytics navigation."""
    categorySelected = pyqtSignal(int)

    def __init__(self, owner=None):
        super().__init__()
        self.owner = owner
        self.setFixedWidth(290)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(4)
        
        header_layout = QHBoxLayout()
        icon_label = QLabel("📊") 
        icon_label.setStyleSheet("font-size: 14pt;")
        
        title_label = QLabel("ANALYTICS HUB")
        title_label.setStyleSheet("font-weight: bold; color: #1b5e20; font-size: 10pt; letter-spacing: 1px;")
        
        header_layout.addWidget(icon_label)
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        layout.addLayout(header_layout)
        
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setStyleSheet("background-color: #2e7d32; min-height: 1px;")
        layout.addWidget(line)
        
        headings = [
            "Project Performance",
            "Financial & Executive Dashboards",
            "Pricing Confidence & Risk Assurance",
            "Operational & Procurement Logistics",
            "Strategic Bidding & 'What-If' Analysis",
            "Adjudication & Supply Chain Intelligence",
            "Sustainability & Compliance (ESG)",
            "Historical Benchmarking",
            "Automated Value Engineering (VE) Finder"
        ]
        
        self.buttons = []
        for i, text in enumerate(headings):
            btn = QPushButton(f"{i+1}. {text}")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setCheckable(True)
            if i == 0: btn.setChecked(True)
            
            btn.setStyleSheet("""
                QPushButton {
                    background-color: white;
                    border: 1px solid #e0e0e0;
                    border-left: 3px solid #2e7d32;
                    border-radius: 3px;
                    padding: 8px 8px;
                    text-align: left;
                    font-weight: 500;
                    color: #333;
                    font-size: 8.5pt;
                }
                QPushButton:hover {
                    background-color: #f1f8e9;
                }
                QPushButton:checked {
                    background-color: #e8f5e9;
                    border-left: 5px solid #1b5e20;
                    font-weight: bold;
                    color: #1b5e20;
                }
            """)
            btn.clicked.connect(lambda checked, idx=i: self._on_button_clicked(idx))
            layout.addWidget(btn)
            self.buttons.append(btn)
            
        layout.addStretch()
        
        tip = QLabel("Select a category to view detailed reports.")
        tip.setWordWrap(True)
        tip.setStyleSheet("color: #666; font-style: italic; font-size: 8pt; margin-top: 10px;")
        layout.addWidget(tip)

    def _on_button_clicked(self, index):
        for i, btn in enumerate(self.buttons):
            btn.setChecked(i == index)
        self.categorySelected.emit(index)

class PlaceholderAnalytic(QWidget):
    """Generic view for analytics not yet implemented."""
    def __init__(self, title, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        label = QLabel(f"<h3>{title}</h3><p>This module is currently under development.</p>")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("color: #666;")
        layout.addWidget(label)

class AnalyticsDashboard(QWidget):
    """The central hub for project-wide financial and progress analytics."""
    def __init__(self, project_dir, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self.project_dir = project_dir
        self.setWindowTitle("Project Analytics Dashboard")
        
        self._init_ui()
        
        # Setup Analytics Hub Sidebar
        self.tools_pane = AnalyticsPane(self)
        self.tools_pane.categorySelected.connect(self.switch_analytic)

        if self.main_window:
            self.tools_dock = QDockWidget("Analytics Hub", self.main_window)
            self.tools_dock.setWidget(self.tools_pane)
            self.tools_dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
            self.main_window.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.tools_dock)
            
            if hasattr(self.main_window, 'project_dock'):
                self.main_window.splitDockWidget(self.main_window.project_dock, self.tools_dock, Qt.Orientation.Vertical)
            
            self.tools_dock.show()
            self.main_window.mdi_area.subWindowActivated.connect(self._on_mdi_subwindow_activated)
            self.destroyed.connect(self._cleanup_tools_dock)

        # Load first analytic by default
        self.switch_analytic(0)
            
    def _on_mdi_subwindow_activated(self, sub):
        if not hasattr(self, 'tools_dock') or not self.tools_dock: return
        if sub and sub.widget() == self:
            self.tools_dock.show()
            self.tools_dock.raise_()
        else:
            self.tools_dock.hide()

    def _cleanup_tools_dock(self):
        if self.main_window:
            try:
                if hasattr(self, 'tools_dock') and self.tools_dock:
                    self.main_window.removeDockWidget(self.tools_dock)
                    self.tools_dock.deleteLater()
                    self.tools_dock = None
            except RuntimeError: pass

    def _init_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        self.stack = QStackedWidget()
        self.layout.addWidget(self.stack)

    def switch_analytic(self, index):
        """Loads and switches to the selected analytic module."""
        # Clear existing stack (optional, or we could cache them)
        if self.stack.count() > 0:
            current = self.stack.currentWidget()
            self.stack.removeWidget(current)
            current.deleteLater()

        if index == 0:
            try:
                from analytics_project_performance import ProjectPerformanceAnalytic
                widget = ProjectPerformanceAnalytic(self.project_dir, self)
            except Exception as e:
                widget = PlaceholderAnalytic(f"Error loading Performance Dashboard: {e}")
        elif index == 1:
            try:
                from analytics_financial_executive import FinancialExecutiveAnalytic
                widget = FinancialExecutiveAnalytic(self.project_dir, self)
            except Exception as e:
                widget = PlaceholderAnalytic(f"Error loading Financial Dashboard: {e}")
        elif index == 2:
            widget = PlaceholderAnalytic("Pricing Confidence & Risk Assurance")
        elif index == 3:
            widget = PlaceholderAnalytic("Strategic Bidding & 'What-If' Analysis")
        elif index == 4:
            widget = PlaceholderAnalytic("Adjudication & Supply Chain Intelligence")
        elif index == 5:
            widget = PlaceholderAnalytic("Sustainability & Compliance (ESG)")
        elif index == 6:
            widget = PlaceholderAnalytic("Historical Benchmarking")
        elif index == 7:
            widget = PlaceholderAnalytic("Automated Value Engineering (VE) Finder")
        else:
            widget = PlaceholderAnalytic("Unknown Module")

        self.stack.addWidget(widget)
        self.stack.setCurrentWidget(widget)

    def refresh_data(self):
        """Passes the refresh command to the currently active analytic."""
        current = self.stack.currentWidget()
        if hasattr(current, 'refresh_data'):
            current.refresh_data()
