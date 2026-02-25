# main_window.py

from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
                             QFormLayout, QLineEdit, QDialog, QComboBox, QDateEdit,
                             QDialogButtonBox, QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView, QSpacerItem,
                             QSizePolicy, QFrame, QListWidget, QListWidgetItem, QMdiArea, QMdiSubWindow,
                             QStatusBar, QSlider, QRadioButton, QButtonGroup, QSpinBox, QGroupBox,
                             QGraphicsDropShadowEffect, QGraphicsOpacityEffect)
from PyQt6.QtGui import QFont, QDoubleValidator, QAction, QColor
from PyQt6.QtCore import Qt, QDate, QSize
from database_dialog import DatabaseManagerDialog
from estimate_window import EstimateWindow
from database import DatabaseManager
from chart_widget import DashboardChart
from settings_dialog import SettingsDialog
from rate_manager_dialog import RateManagerDialog
from rate_buildup_dialog import RateBuildUpDialog
from edit_item_dialog import EditItemDialog
from currency_conversion_dialog import CurrencyConversionDialog
import copy


class DashboardWidget(QWidget):
    """Dashboard content to be displayed in the MDI area."""
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.db_manager = DatabaseManager()
        self._setup_ui()
        self.refresh_dashboard()

    def _setup_ui(self):
        self.setStyleSheet("background-color: #f5f7f9;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(30)

        # Header
        header = QLabel("Dashboard")
        header.setStyleSheet("font-size: 28px; font-weight: bold; color: #424242;")
        layout.addWidget(header)

        # Metrics Row
        self.metrics_container = QHBoxLayout()
        self.metrics_container.setSpacing(20)
        
        self.total_estimates_card = self._create_metric_card("Total Estimates", "0")
        self.total_value_card = self._create_metric_card("Total Value", "$0.00")
        
        self.metrics_container.addWidget(self.total_estimates_card)
        self.metrics_container.addWidget(self.total_value_card)
        self.metrics_container.addStretch(1) 
        layout.addLayout(self.metrics_container)
        
        # Chart
        self.chart = DashboardChart()
        layout.addWidget(self.chart)

        # Recent Estimates List
        layout.addWidget(QLabel("Recent Estimates", objectName="SectionHeader"))
        self.recent_list = QListWidget()
        self.recent_list.setStyleSheet("""
            QListWidget { border: 1px solid #e0e0e0; border-radius: 8px; background-color: white; padding: 10px; }
            QListWidget::item { padding: 15px; border-bottom: 1px solid #f0f0f0; }
            QListWidget::item:last { border-bottom: none; }
            QListWidget::item:hover { background-color: #f5f7f9; }
        """)
        self.recent_list.itemDoubleClicked.connect(self.open_recent_estimate)
        layout.addWidget(self.recent_list)

    def _create_metric_card(self, label_text, value_text):
        """Helper to create a stylized metric card."""
        card = QFrame()
        card.setObjectName("MetricCard")
        card.setFixedSize(220, 120)
        card_layout = QVBoxLayout(card)
        
        value = QLabel(value_text, objectName="MetricValue")
        label = QLabel(label_text, objectName="MetricLabel")
        
        card_layout.addWidget(value)
        card_layout.addWidget(label)
        card.value_label = value 
        return card

    def refresh_dashboard(self):
        """Updates metrics, chart, and recent estimates list."""
        count = self.db_manager.get_total_estimates_count()
        total_val = self.db_manager.get_total_estimates_value()
        
        self.total_estimates_card.value_label.setText(str(count))
        self.total_value_card.value_label.setText(f"{total_val:,.2f}")

        # Update List and Chart
        self.recent_list.clear()
        recents = self.db_manager.get_recent_estimates(5)
        chart_data = []
        
        if not recents:
            item = QListWidgetItem("No estimates found. Create one to get started.")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.recent_list.addItem(item)
        else:
            for est in recents:
                val = est['grand_total'] or 0.0
                chart_data.append((est['project_name'][:10], val))
                
                item = QListWidgetItem(f"{est['project_name']} (Client: {est['client_name']})\n{est['date_created']}")
                item.setData(Qt.ItemDataRole.UserRole, est['id'])
                self.recent_list.addItem(item)
                
        self.chart.set_data(list(reversed(chart_data)))

    def open_recent_estimate(self, item):
        est_id = item.data(Qt.ItemDataRole.UserRole)
        if est_id:
            self.main_window._load_and_show_estimate(est_id)


class MainWindow(QMainWindow):
    """Main application window using MDI architecture."""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Construction Estimating Software")
        self.setMinimumSize(1400, 900)
        self.db_manager = DatabaseManager()

        # Main Layout Structure
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # 1. Top Navigation Bar
        self._setup_navbar()

        # 2. MDI Area
        self.mdi_area = QMdiArea()
        self.mdi_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.mdi_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.mdi_area.setViewMode(QMdiArea.ViewMode.SubWindowView)
        self.mdi_area.setTabsClosable(True)
        self.mdi_area.setTabsMovable(True)
        # Apply a subtle background to the workspace
        self.mdi_area.setStyleSheet("QMdiArea { background-color: #eceff1; }")
        
        self.main_layout.addWidget(self.mdi_area)
        
        # 3. Status Bar (Zoom Controls)
        self._setup_statusbar()
        
        # Open Dashboard on launch
        self.show_dashboard()

        # Connect active window change to update toolbar state
        self.mdi_area.subWindowActivated.connect(self._update_toolbar_state)
        
        # Track zoom scale for relative window resizing
        self.last_zoom_scale = 1.0

    def _get_color_for_rate(self, rate_code):
        if not rate_code: return "transparent"
        import hashlib
        hash_val = int(hashlib.md5(str(rate_code).encode()).hexdigest()[:6], 16)
        r = (hash_val & 0xFF0000) >> 16
        g = (hash_val & 0x00FF00) >> 8
        b = hash_val & 0x0000FF
        # Make pastel
        r = (r + 255) // 2
        g = (g + 255) // 2
        b = (b + 255) // 2
        return f"#{r:02x}{g:02x}{b:02x}"

    def _setup_navbar(self):
        """Creates the premium top navigation bar."""
        self.navbar = QFrame()
        self.navbar.setObjectName("TopNavBar")
        self.navbar.setFixedHeight(80) 
        self.navbar.setStyleSheet("""
            QFrame#TopNavBar {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1b5e20, stop:1 #2e7d32);
                border-bottom: 2px solid #1b5e20;
            }
            QPushButton {
                background-color: transparent;
                color: white;
                border: none;
                font-weight: 600;
                padding: 5px 15px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.2);
            }
            QPushButton:pressed {
                background-color: rgba(255, 255, 255, 0.3);
            }
            QPushButton#ActionBtn {
                background-color: rgba(255, 255, 255, 0.15);
                border: 1px solid rgba(255, 255, 255, 0.3);
            }
            QPushButton#ActionBtn:hover {
                background-color: rgba(255, 255, 255, 0.25);
            }
            QLabel {
                color: white;
                font-weight: bold;
            }
        """)

        layout = QHBoxLayout(self.navbar)
        layout.setContentsMargins(20, 10, 20, 10)
        layout.setSpacing(15)

        # Branding
        layout.addWidget(QLabel("Estimator Pro"))
        
        line = QFrame()
        line.setFrameShape(QFrame.Shape.VLine)
        line.setStyleSheet("background-color: rgba(255,255,255,0.3);")
        layout.addWidget(line)

        # Navigation Buttons
        nav_items = [
            ("Dashboard", self.show_dashboard),
            ("Create New Estimate", self.new_estimate),
            ("Load Estimate", self.load_estimate),
            ("Cost Database", self.manage_database),
            ("Rate Database", self.manage_rate_database),
            ("Settings", self.open_settings)
        ]

        for text, slot in nav_items:
            btn = QPushButton(text)
            btn.clicked.connect(slot)
            layout.addWidget(btn)

        layout.addStretch()

        # Action Buttons (Undo/Redo/Save)
        self.undo_btn = QPushButton("Undo")
        self.undo_btn.setObjectName("ActionBtn")
        self.undo_btn.setShortcut("Ctrl+Z")
        self.undo_btn.clicked.connect(self.trigger_undo)
        
        self.redo_btn = QPushButton("Redo")
        self.redo_btn.setObjectName("ActionBtn")
        self.redo_btn.setShortcut("Ctrl+Y")
        self.redo_btn.clicked.connect(self.trigger_redo)

        self.save_btn = QPushButton("Save")
        self.save_btn.setObjectName("ActionBtn")
        self.save_btn.setShortcut("Ctrl+S")
        self.save_btn.clicked.connect(self.trigger_save)

        # Disable initially
        self.undo_btn.setEnabled(False)
        self.redo_btn.setEnabled(False)
        self.save_btn.setEnabled(False)

        layout.addWidget(self.undo_btn)
        layout.addWidget(self.redo_btn)
        layout.addWidget(self.save_btn)

        self.main_layout.addWidget(self.navbar)

    def show_dashboard(self):
        """Shows or activates the dashboard."""
        # Check if already exists
        for sub in self.mdi_area.subWindowList():
            if isinstance(sub.widget(), DashboardWidget):
                self.mdi_area.setActiveSubWindow(sub)
                sub.widget().refresh_dashboard()
                return
        
        # Create new
        dashboard = DashboardWidget(self)
        sub = self.mdi_area.addSubWindow(dashboard)
        sub.setWindowTitle("Dashboard")
        sub.showMaximized()

    def new_estimate(self):
        dialog = NewEstimateDialog(self)
        if dialog.exec():
            est_window = EstimateWindow(estimate_data=dialog.get_data(), main_window=self) 
            self._add_estimate_window(est_window)

    def load_estimate(self):
        dialog = LoadEstimateDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selected_estimate_id:
            self._load_and_show_estimate(dialog.selected_estimate_id)

    def _load_and_show_estimate(self, est_id):
        # Check if already open
        for sub in self.mdi_area.subWindowList():
            widget = sub.widget()
            if isinstance(widget, EstimateWindow) and widget.estimate.id == est_id:
                self.mdi_area.setActiveSubWindow(sub)
                return

        estimate_obj = self.db_manager.load_estimate_details(est_id)
        if estimate_obj:
            est_window = EstimateWindow(estimate_object=estimate_obj, main_window=self)
            self._add_estimate_window(est_window)
        else:
            QMessageBox.critical(self, "Error", "Failed to load estimate.")

    def open_rate_buildup_window(self, estimate_obj):
        """Opens a rate build-up in an MDI window."""
        # Check if already open
        for sub in self.mdi_area.subWindowList():
            widget = sub.widget()
            if isinstance(widget, RateBuildUpDialog) and widget.estimate.id == estimate_obj.id:
                self.mdi_area.setActiveSubWindow(sub)
                return

        def refresh_manager():
            for s in self.mdi_area.subWindowList():
                if isinstance(s.widget(), RateManagerDialog):
                    s.widget().load_rates()

        buildup_win = RateBuildUpDialog(estimate_obj, main_window=self)
        sub = self.mdi_area.addSubWindow(buildup_win)
        
        # Color code border
        color = self._get_color_for_rate(estimate_obj.rate_code)
        if color != "transparent":
            sub.setStyleSheet(f"QMdiSubWindow {{ border: 4px solid {color}; background-color: #ffffff; }}")
            
        buildup_win.stateChanged.connect(self._update_toolbar_state)
        buildup_win.dataCommitted.connect(refresh_manager)
        sub.resize(800, 634)
        self._apply_zoom_to_subwindow(sub)
        sub.show()

    def open_edit_item_window(self, item_data, item_type, currency, parent_window, custom_title=None, custom_name_label=None):
        """Opens the resource editor as an MDI sub-window."""
        # Check if already open (simple check, maybe improve later to allow multiple diff items)
        # For now, just open a new one
        
        # Take snapshot of parent BEFORE opening (or at least store it in the window)
        # Actually, we need to push to undo stack ONLY if saved.
        # But we need the snapshot of BEFORE the edits.
        
        # Store snapshot on the parent window logic? 
        # RateBuildUpDialog handles its own undo stack. We should let it handle the push.
        
        edit_win = EditItemDialog(item_data, item_type, currency, parent=parent_window, is_modal=False, custom_name_label=custom_name_label)
        
        if custom_title:
            edit_win.setWindowTitle(custom_title)
        else:
            parent_code = "Estimate"
            if hasattr(parent_window, 'estimate') and hasattr(parent_window.estimate, 'rate_code') and parent_window.estimate.rate_code:
                parent_code = f"Rate: {parent_window.estimate.rate_code}"
            elif hasattr(parent_window, 'estimate') and hasattr(parent_window.estimate, 'project_name') and parent_window.estimate.project_name:
                parent_code = f"Project: {parent_window.estimate.project_name}"
            
            item_name = item_data.get('name') or item_data.get('trade') or item_data.get('description') or 'New Item'
            auto_title = f"{item_type.capitalize()}: {item_name} [{parent_code}]"
            edit_win.setWindowTitle(auto_title)
        
        # Capture snapshot of parent's estimate state *before* any potential changes
        if hasattr(parent_window, 'estimate'):
             edit_win.snapshot = copy.deepcopy(parent_window.estimate)
        
        sub = self.mdi_area.addSubWindow(edit_win)
        
        # Color code border
        color = "transparent"
        if hasattr(parent_window, 'estimate') and hasattr(parent_window.estimate, 'rate_code'):
            color = self._get_color_for_rate(parent_window.estimate.rate_code)
        if color != "transparent":
            sub.setStyleSheet(f"QMdiSubWindow {{ border: 4px solid {color}; background-color: #ffffff; }}")
        
        def on_save():
            # When EditItemDialog saves, it updates the item_data dict in place.
            # We need to notify the parent window to push the snapshot and refresh.
            try:
                if hasattr(parent_window, 'undo_stack'):
                    parent_window.undo_stack.append(edit_win.snapshot)
                    parent_window.redo_stack.clear()
                
                # Update the snapshot for the NEXT save operation (if window stays open)
                if hasattr(parent_window, 'estimate'):
                    edit_win.snapshot = copy.deepcopy(parent_window.estimate)
                
                if hasattr(parent_window, 'refresh_view'):
                    parent_window.refresh_view()
                    
                if hasattr(parent_window, 'stateChanged'):
                    parent_window.stateChanged.emit()
            except RuntimeError:
                pass
                
        edit_win.dataCommitted.connect(on_save)
        edit_win.stateChanged.connect(self._update_toolbar_state)
        sub.resize(420, 450)
        self._apply_zoom_to_subwindow(sub)
        sub.show()

    def _add_estimate_window(self, est_window):
        sub = self.mdi_area.addSubWindow(est_window)
        est_window.stateChanged.connect(self._update_toolbar_state)
        sub.resize(1100, 700)
        self._apply_zoom_to_subwindow(sub)
        sub.show()

    def manage_database(self):
        for sub in self.mdi_area.subWindowList():
            if isinstance(sub.widget(), DatabaseManagerDialog):
                self.mdi_area.setActiveSubWindow(sub)
                return
        
        dialog = DatabaseManagerDialog(self)
        sub = self.mdi_area.addSubWindow(dialog)
        dialog.stateChanged.connect(self._update_toolbar_state)
        dialog.resourceUpdated.connect(self._broadcast_library_update)
        sub.resize(950, 650)
        self._apply_zoom_to_subwindow(sub)
        sub.show()

    def show_resource_in_database(self, table_name, resource_name):
        """Opens the cost database and highlights a specific resource."""
        db_sub = None
        for sub in self.mdi_area.subWindowList():
            if isinstance(sub.widget(), DatabaseManagerDialog):
                db_sub = sub
                break
        
        if not db_sub:
            self.manage_database()
            # Find the newly created subwindow
            for sub in self.mdi_area.subWindowList():
                if isinstance(sub.widget(), DatabaseManagerDialog):
                    db_sub = sub
                    break
        
        if db_sub:
            self.mdi_area.setActiveSubWindow(db_sub)
            db_sub.widget().highlight_resource(table_name, resource_name)
        
    def _broadcast_library_update(self, table, name, val, curr):
        """Notifies all open rate windows about a resource update in the library."""
        from database import DatabaseManager
        from PyQt6.QtWidgets import QMessageBox
        
        db_costs = self.db_manager
        db_rates = DatabaseManager("construction_rates.db")
        
        costs_affected = db_costs.get_estimates_using_resource(table, name)
        rates_affected = db_rates.get_estimates_using_resource(table, name)
        
        total_affected = len(costs_affected) + len(rates_affected)
        auto_update = False
        
        if total_affected > 0:
            reply = QMessageBox.question(
                self, 
                "Update Dependent Rates and Estimates",
                f"The resource '{name}' is used in {total_affected} saved estimate(s)/rate(s).\n\n"
                f"Do you want to update all of them to the new rate and currency: {curr} {val:,.2f}?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                db_costs.update_resource_in_all_estimates(table, name, val, curr)
                db_rates.update_resource_in_all_estimates(table, name, val, curr)
                
                # Force recalculation for nested composite rates and historical totals
                db_costs.recalculate_all_estimates()
                db_rates.recalculate_all_estimates()
                
                auto_update = True
        
        for sub in self.mdi_area.subWindowList():
            widget = sub.widget()
            if hasattr(widget, 'handle_library_update'):
                widget.handle_library_update(table, name, val, curr, auto_update=auto_update)
            elif hasattr(widget, 'load_rates'):
                # Refresh Historical Rates view if open
                widget.load_rates()

    def manage_rate_database(self):
        for sub in self.mdi_area.subWindowList():
            if isinstance(sub.widget(), RateManagerDialog):
                self.mdi_area.setActiveSubWindow(sub)
                return
        
        # Pass self (MainWindow) to RateManagerDialog so it can open RateBuildUpDialog in MDI
        dialog = RateManagerDialog(self) 
        sub = self.mdi_area.addSubWindow(dialog)
        sub.resize(900, 550)
        self._apply_zoom_to_subwindow(sub)
        sub.show()

    def show_rate_in_database(self, rate_code):
        """Opens the rate database and highlights a specific rate."""
        rate_sub = None
        for sub in self.mdi_area.subWindowList():
            if isinstance(sub.widget(), RateManagerDialog):
                rate_sub = sub
                break
        
        if not rate_sub:
            self.manage_rate_database()
            # Find the newly created subwindow
            for sub in self.mdi_area.subWindowList():
                if isinstance(sub.widget(), RateManagerDialog):
                    rate_sub = sub
                    break
        
        if rate_sub:
            self.mdi_area.setActiveSubWindow(rate_sub)
            rate_sub.widget().highlight_rate(rate_code)

    def open_settings(self):
        for sub in self.mdi_area.subWindowList():
            if isinstance(sub.widget(), SettingsDialog):
                self.mdi_area.setActiveSubWindow(sub)
                return
                
        dialog = SettingsDialog(self)
        sub = self.mdi_area.addSubWindow(dialog)
        sub.resize(500, 600)
        self._apply_zoom_to_subwindow(sub)
        sub.show()

    # --- Global Action Handlers ---
    
    def _get_active_estimate_window(self):
        sub = self.mdi_area.activeSubWindow()
        if sub:
            widget = sub.widget()
            if isinstance(widget, EstimateWindow) or isinstance(widget, RateBuildUpDialog) or isinstance(widget, EditItemDialog) or isinstance(widget, CurrencyConversionDialog):
                return widget
        return None

    def _apply_zoom_to_subwindow(self, sub):
        """Applies the current global zoom scale to a newly added subwindow."""
        if not hasattr(self, 'last_zoom_scale') or self.last_zoom_scale == 1.0:
            return
            
        ratio = self.last_zoom_scale
        # Scale current size by the total accumulated zoom
        new_w = int(sub.width() * ratio)
        new_h = int(sub.height() * ratio)
        
        # Scale minimum size
        widget = sub.widget()
        if widget:
            min_w = int(widget.minimumWidth() * ratio)
            min_h = int(widget.minimumHeight() * ratio)
            widget.setMinimumSize(min_w, min_h)
            
            # Ensure subwindow is large enough to contain the scaled widget (with padding for title bar/borders)
            new_w = max(new_w, min_w + 30)
            new_h = max(new_h, min_h + 50)
        
        sub.resize(new_w, new_h)

    def trigger_undo(self):
        win = self._get_active_estimate_window()
        if win: win.undo()

    def trigger_redo(self):
        win = self._get_active_estimate_window()
        if win: win.redo()

    def trigger_save(self):
        win = self._get_active_estimate_window()
        if win: 
            if hasattr(win, 'save_estimate'):
                win.save_estimate()
            elif hasattr(win, 'save_changes'):
                win.save_changes()
            elif hasattr(win, 'save'):
                win.save()

    def _setup_statusbar(self):
        """Creates the Excel-style bottom bar with zoom controls."""
        sb = self.statusBar()
        sb.setStyleSheet("QStatusBar { background-color: #f3f3f3; border-top: 1px solid #dcdfe6; color: #555; }")
        
        # Ready Message
        sb.showMessage("Ready")
        
        # Accessibility Info
        acc_label = QLabel("Accessibility: Good to go")
        acc_label.setContentsMargins(20, 0, 0, 0)
        acc_label.setObjectName("StatusAccInfo")
        sb.addWidget(acc_label)
        
        # Permanent Zoom Controls Widget
        zoom_container = QWidget()
        zoom_layout = QHBoxLayout(zoom_container)
        zoom_layout.setContentsMargins(0, 0, 10, 0)
        zoom_layout.setSpacing(8)
        
        # Display settings icon (placeholder)
        display_label = QLabel("Display Settings")
        display_label.setObjectName("StatusDisplayInfo")
        zoom_layout.addWidget(display_label)
        
        # Minus button
        minus_btn = QPushButton("-")
        minus_btn.setFixedSize(18, 18)
        minus_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        minus_btn.setStyleSheet("background: transparent; color: #333; font-weight: bold; border: none;")
        minus_btn.clicked.connect(lambda: self.zoom_slider.setValue(self.zoom_slider.value() - 1))
        zoom_layout.addWidget(minus_btn)
        
        # Slider (Discrete steps: 0=50%, 1=75%, 2=100%)
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(0, 2)
        self.zoom_slider.setValue(2) # Default 100%
        self.zoom_slider.setSingleStep(1)
        self.zoom_slider.setPageStep(1)
        self.zoom_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.zoom_slider.setTickInterval(1)
        self.zoom_slider.setFixedWidth(100)
        self.zoom_slider.setContentsMargins(0, 0, 0, 0)
        self.zoom_slider.valueChanged.connect(self._handle_zoom)
        zoom_layout.addWidget(self.zoom_slider)
        
        # Plus button
        plus_btn = QPushButton("+")
        plus_btn.setFixedSize(18, 18)
        plus_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        plus_btn.setStyleSheet("background: transparent; color: #333; font-weight: bold; border: none;")
        plus_btn.clicked.connect(lambda: self.zoom_slider.setValue(self.zoom_slider.value() + 1))
        zoom_layout.addWidget(plus_btn)
        
        # Zoom Percent label (Clickable)
        self.zoom_btn = QPushButton("100%")
        self.zoom_btn.setFixedWidth(55)
        self.zoom_btn.setFlat(True)
        self.zoom_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.zoom_btn.setObjectName("StatusZoomLabel")
        self.zoom_btn.clicked.connect(self._open_zoom_dialog)
        zoom_layout.addWidget(self.zoom_btn)
        
        sb.addPermanentWidget(zoom_container)

    def _open_zoom_dialog(self):
        """Opens the Excel-style zoom dialog."""
        zoom_values = [50, 75, 100]
        current_zoom = zoom_values[self.zoom_slider.value()]
        dialog = ZoomDialog(current_zoom, self)
        if dialog.exec():
            new_zoom = dialog.get_zoom_value()
            # Map back to slider index
            if new_zoom in zoom_values:
                self.zoom_slider.setValue(zoom_values.index(new_zoom))
            else:
                # Fallback to closest preset for the bar
                closest = min(zoom_values, key=lambda x: abs(x - new_zoom))
                self.zoom_slider.setValue(zoom_values.index(closest))

    def _handle_zoom(self, index):
        """Scales the UI by dynamically updating the application's global stylesheet."""
        zoom_values = [50, 75, 100]
        value = zoom_values[index]
        
        self.zoom_btn.setText(f"{value}%")
        scale = value / 100.0
        
        # Ensure we have the original style loaded
        if not hasattr(self, '_original_style'):
            import os
            style_path = os.path.join(os.path.dirname(__file__), "styles.qss")
            try:
                with open(style_path, "r") as f:
                    self._original_style = f.read()
            except:
                self._original_style = ""

        if self._original_style:
            import re
            from PyQt6.QtWidgets import QApplication
            
            def scale_value(match):
                attr = match.group(1)
                num = float(match.group(2))
                unit = match.group(3)
                scaled = round(num * scale, 1)
                
                # Intelligent limits for specific attributes
                if 'font-size' in attr:
                    if unit == 'pt': scaled = max(6.0, min(scaled, 24.0))
                    elif unit == 'px': scaled = max(8.0, min(scaled, 36.0))
                return f"{attr}: {scaled}{unit};"

            # Scale typography and geometry (padding, margin, width, border-radius)
            props = "font-size|padding|margin|border-radius|border-width|width|height"
            new_style = re.sub(rf"({props}):\s*([\d\.]+)(pt|px);", scale_value, self._original_style)
            
            # Apply to app
            app = QApplication.instance()
            if app:
                app.setStyleSheet(new_style)

            # Scale open MDI windows with grace
            ratio = scale / self.last_zoom_scale
            for sub in self.mdi_area.subWindowList():
                # Scale current size
                new_w = int(sub.width() * ratio)
                new_h = int(sub.height() * ratio)
                
                # Scale minimum size to prevent layout break at high zoom
                widget = sub.widget()
                if widget:
                    min_w = int(widget.minimumWidth() * ratio)
                    min_h = int(widget.minimumHeight() * ratio)
                    widget.setMinimumSize(min_w, min_h)
                
                sub.resize(new_w, new_h)
            
            self.last_zoom_scale = scale

    def _update_toolbar_state(self):
        """Updates enable/disable state of global actions based on active window."""
        win = self._get_active_estimate_window()
        
        active_sub = self.mdi_area.activeSubWindow()
        
        # Visually dim inactive windows and glow the active one
        for sub in self.mdi_area.subWindowList():
            if sub == active_sub:
                shadow = QGraphicsDropShadowEffect()
                shadow.setBlurRadius(40)
                # Parse color from border if available, otherwise default
                color_str = "#00c896" # Default glow color
                style = sub.styleSheet()
                import re
                match = re.search(r'border:\s*4px\s+solid\s+(#[0-9a-fA-F]{6})', style)
                if match:
                    color_str = match.group(1)
                shadow.setColor(QColor(color_str))
                shadow.setOffset(0, 0)
                sub.setGraphicsEffect(shadow)
            else:
                sub.setGraphicsEffect(None) # Remove shadows/effects for inactive
                
        if active_sub and active_sub.widget():
            title = active_sub.widget().windowTitle()
            import re
            clean_title = re.sub(r'<[^>]+>', '', title)
            self.statusBar().showMessage(f"Active: {clean_title}")
        else:
            self.statusBar().showMessage("Ready")
            
        if win:
            self.save_btn.setEnabled(True)
            if hasattr(win, 'undo_stack'):
                self.undo_btn.setEnabled(len(win.undo_stack) > 0)
                self.redo_btn.setEnabled(len(win.redo_stack) > 0)
            elif isinstance(win, EditItemDialog):
                # For text editing, we delegate to the text widget's undo stack
                self.undo_btn.setEnabled(win.qty_input.document().isUndoAvailable())
                self.redo_btn.setEnabled(win.qty_input.document().isRedoAvailable())
            elif isinstance(win, CurrencyConversionDialog):
                # Exchange rates don't have undo stack yet, but we enable save
                self.undo_btn.setEnabled(False)
                self.redo_btn.setEnabled(False)
            else:
                # Database Manager or others without undo stack
                self.undo_btn.setEnabled(False)
                self.redo_btn.setEnabled(False)
        else:
            self.undo_btn.setEnabled(False)
            self.redo_btn.setEnabled(False)
            self.save_btn.setEnabled(False)


class NewEstimateDialog(QDialog):
    """Dialog for project initialization."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.db_manager = DatabaseManager()
        self.setWindowTitle("New Project Details")
        self.setMinimumWidth(400)
        
        layout = QFormLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)

        self.project_name = QLineEdit("New Project")
        self.location = QLineEdit("Location")
        self.project_date = QDateEdit(calendarPopup=True, displayFormat="dd-MM-yy", date=QDate.currentDate())
        
        validator = QDoubleValidator(0.0, 100.0, 2, notation=QDoubleValidator.Notation.StandardNotation)
        
        self.overhead = QLineEdit(self.db_manager.get_setting('overhead', '15.00'))
        self.overhead.setValidator(validator)
        self.profit = QLineEdit(self.db_manager.get_setting('profit', '10.00'))
        self.profit.setValidator(validator)
        
        self.currency = QComboBox()
        self.currency.addItems(["USD ($)", "EUR (€)", "GBP (£)", "JPY (¥)", "CAD ($)", "GHS (₵)", "CNY (¥)", "INR (₹)"])
        self.currency.setCurrentText(self.db_manager.get_setting('currency', 'GHS (₵)'))

        layout.addRow("Project Name:", self.project_name)
        layout.addRow("Location:", self.location)
        layout.addRow("Project Date:", self.project_date)
        layout.addRow("Overhead (%):", self.overhead)
        layout.addRow("Profit (%):", self.profit)
        layout.addRow("Currency:", self.currency)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def get_data(self):
        return {
            "name": self.project_name.text(),
            "client": self.location.text(),
            "date": self.project_date.date().toString("yyyy-MM-dd"),
            "overhead": float(self.overhead.text() or 0),
            "profit": float(self.profit.text() or 0),
            "currency": self.currency.currentText()
        }


class EditEstimateDialog(QDialog):
    """Dialog for metadata updates."""
    def __init__(self, project_name, location, project_date, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Estimate Details")
        self.setMinimumWidth(400)
        layout = QFormLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)

        self.project_name_input = QLineEdit(project_name)
        self.location_input = QLineEdit(location)
        self.project_date_input = QDateEdit(calendarPopup=True, displayFormat="dd-MM-yy")
        
        qdate = QDate.fromString(project_date[:10], "yyyy-MM-dd")
        self.project_date_input.setDate(qdate if qdate.isValid() else QDate.currentDate())

        layout.addRow("Project Name:", self.project_name_input)
        layout.addRow("Location:", self.location_input)
        layout.addRow("Project Date:", self.project_date_input)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def get_data(self):
        return (
            self.project_name_input.text(), 
            self.location_input.text(),
            self.project_date_input.date().toString("yyyy-MM-dd")
        )


class LoadEstimateDialog(QDialog):
    """Dialog for browsing and managing saved estimates."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.db_manager = DatabaseManager()
        self.selected_estimate_id = None
        self.setWindowTitle("Load Estimate")
        self.setMinimumSize(800, 500)

        layout = QVBoxLayout(self)
        self.table = QTableWidget(columnCount=4)
        self.table.setHorizontalHeaderLabels(["ID", "Project Name", "Location", "Date Created"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setDefaultSectionSize(22)
        self.table.setWordWrap(False)
        self.table.setColumnHidden(0, True)
        self.table.doubleClicked.connect(self.accept_selection)
        layout.addWidget(self.table)

        # Actions
        btn_layout = QHBoxLayout()
        for text, slot in [("Edit", self.edit_selected), ("Delete", self.delete_selected), ("Duplicate", self.duplicate_selected)]:
            btn = QPushButton(text)
            btn.clicked.connect(slot)
            btn_layout.addWidget(btn)
        
        btn_layout.addStretch()
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Open | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Open).setText("Load Selected")
        buttons.accepted.connect(self.accept_selection)
        buttons.rejected.connect(self.reject)
        btn_layout.addWidget(buttons)
        layout.addLayout(btn_layout)

        self.load_estimates()

    def load_estimates(self):
        self.table.setRowCount(0)
        estimates = self.db_manager.get_saved_estimates_summary()
        self.table.setRowCount(len(estimates))
        for row, est in enumerate(estimates):
            self.table.setItem(row, 0, QTableWidgetItem(str(est['id'])))
            self.table.setItem(row, 1, QTableWidgetItem(est['project_name']))
            self.table.setItem(row, 2, QTableWidgetItem(est['client_name']))
            self.table.setItem(row, 3, QTableWidgetItem(est['date_created']))
        self.table.resizeColumnsToContents()
        self.table.resizeRowsToContents()

    def _get_selection(self):
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            QMessageBox.warning(self, "Selection Error", "Please select an estimate.")
            return None
        row = selected[0].row()
        return {
            "id": int(self.table.item(row, 0).text()),
            "name": self.table.item(row, 1).text(),
            "location": self.table.item(row, 2).text(),
            "date": self.table.item(row, 3).text()
        }

    def accept_selection(self):
        sel = self._get_selection()
        if sel:
            self.selected_estimate_id = sel['id']
            self.accept()

    def edit_selected(self):
        sel = self._get_selection()
        if not sel: return
        dialog = EditEstimateDialog(sel['name'], sel['location'], sel['date'], self)
        if dialog.exec():
            name, loc, date = dialog.get_data()
            if self.db_manager.update_estimate_metadata(sel['id'], name, loc, date):
                self.load_estimates()

    def delete_selected(self):
        sel = self._get_selection()
        if not sel: return
        if QMessageBox.question(self, "Delete", f"Delete '{sel['name']}'?") == QMessageBox.StandardButton.Yes:
            if self.db_manager.delete_estimate(sel['id']):
                self.load_estimates()

    def duplicate_selected(self):
        sel = self._get_selection()
        if not sel: return
        if self.db_manager.duplicate_estimate(sel['id']):
            self.load_estimates()


class ZoomDialog(QDialog):
    """Excel-style zoom magnification dialog."""
    def __init__(self, current_zoom, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Zoom")
        self.setFixedSize(220, 240)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        
        group = QGroupBox("Magnification")
        group_layout = QVBoxLayout(group)
        group_layout.setSpacing(5)
        
        self.radio_group = QButtonGroup(self)
        
        presets = [100, 75, 50]
        self.radios = {}
        
        for p in presets:
            rb = QRadioButton(f"{p}%")
            self.radio_group.addButton(rb, p)
            group_layout.addWidget(rb)
            self.radios[p] = rb
            if p == current_zoom:
                rb.setChecked(True)
        
        # Custom option
        custom_layout = QHBoxLayout()
        self.custom_rb = QRadioButton("Custom:")
        self.radio_group.addButton(self.custom_rb, 0)
        custom_layout.addWidget(self.custom_rb)
        
        self.spin = QSpinBox()
        self.spin.setRange(50, 100)
        self.spin.setSuffix("%")
        self.spin.setValue(current_zoom)
        # Style the spinbox to be smaller
        self.spin.setFixedWidth(70)
        custom_layout.addWidget(self.spin)
        group_layout.addLayout(custom_layout)
        
        # Logic to check custom if spin is changed
        self.spin.valueChanged.connect(lambda: self.custom_rb.setChecked(True))
        
        if current_zoom not in presets:
            self.custom_rb.setChecked(True)
            
        layout.addWidget(group)
        
        # Buttons
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def get_zoom_value(self):
        if self.custom_rb.isChecked():
            return self.spin.value()
        return self.radio_group.checkedId()