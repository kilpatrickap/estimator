# main_window.py

from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
                             QFormLayout, QLineEdit, QDialog, QComboBox, QDateEdit,
                             QDialogButtonBox, QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView, QSpacerItem,
                             QSizePolicy, QFrame, QListWidget, QListWidgetItem, QMdiArea, QMdiSubWindow, QMenuBar,
                             QStatusBar, QSlider, QRadioButton, QButtonGroup, QSpinBox, QGroupBox,
                             QGraphicsDropShadowEffect, QGraphicsOpacityEffect)
from PyQt6.QtGui import QFont, QDoubleValidator, QAction, QColor
from PyQt6.QtCore import Qt, QDate, QSize
from database_dialog import DatabaseManagerDialog
from estimate_window import EstimateWindow
from database import DatabaseManager
from settings_dialog import SettingsDialog
from rate_manager_dialog import RateManagerDialog
from rate_buildup_dialog import RateBuildUpDialog
from edit_item_dialog import EditItemDialog
from currency_conversion_dialog import CurrencyConversionDialog
import copy
import os



class RestrictedSubWindow(QMdiSubWindow):
    def moveEvent(self, event):
        if self.pos().y() < 0:
            self.move(self.pos().x(), 0)
        super().moveEvent(event)

class RestrictedMdiArea(QMdiArea):
    def addSubWindow(self, widget, flags=Qt.WindowType.SubWindow):
        if isinstance(widget, QMdiSubWindow):
            return super().addSubWindow(widget)
        sub = RestrictedSubWindow()
        sub.setWidget(widget)
        super().addSubWindow(sub)
        return sub

class MainWindow(QMainWindow):
    """Main application window using MDI architecture."""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Construction Estimating Software")
        self.setMinimumSize(1024, 700) # Reduced to make it responsive on smaller screens
        self.db_manager = DatabaseManager()

        # Main Layout Structure
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # Build Standard Window Menu Bar (Added to layout above the custom navbar)
        self._setup_menubar()

        # 1. Top Navigation Bar
        self._setup_navbar()

        # Place the standard app menubar underneath the custom navbar 
        # This catches the MDI minimize, restore, and close buttons
        self.main_layout.addWidget(self.menuBar())

        # 2. MDI Area
        self.mdi_area = RestrictedMdiArea()
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
        
        # 4. Project Pane
        self._setup_project_pane()
        
        # Connect active window change to update toolbar state
        self.mdi_area.subWindowActivated.connect(self._update_toolbar_state)
        
        # Track zoom scale for relative window resizing
        self.last_zoom_scale = 1.0

    def _setup_project_pane(self):
        from PyQt6.QtWidgets import QDockWidget, QTreeView
        from PyQt6.QtGui import QFileSystemModel
        from PyQt6.QtCore import Qt, QDir
        import os
        
        self.project_dock = QDockWidget("Project", self)
        self.project_dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.project_dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetClosable | QDockWidget.DockWidgetFeature.DockWidgetFloatable | QDockWidget.DockWidgetFeature.DockWidgetMovable)
        
        self.project_tree = QTreeView()
        self.project_model = QFileSystemModel()
        self.project_model.setFilter(QDir.Filter.AllDirs | QDir.Filter.Files | QDir.Filter.NoDotAndDotDot)
        
        last_dir = self.db_manager.get_setting('last_project_dir', '')
        if last_dir and os.path.exists(last_dir):
            self.project_model.setRootPath(last_dir)
            self.project_dock.setWindowTitle(f"Project: {os.path.basename(last_dir)}")
        else:
            self.project_model.setRootPath("")
            
        self.project_tree.setModel(self.project_model)
        
        if last_dir and os.path.exists(last_dir):
            self.project_tree.setRootIndex(self.project_model.index(last_dir))
        
        # Hide unneeded columns (Size, Type, Date Modified)
        self.project_tree.setColumnHidden(1, True)
        self.project_tree.setColumnHidden(2, True)
        self.project_tree.setColumnHidden(3, True)
        self.project_tree.setHeaderHidden(True)
        
        self.project_dock.setWidget(self.project_tree)
        self.project_dock.setMaximumHeight(180)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.project_dock)

    def _update_project_pane_directory(self, project_dir):
        import os
        self.project_model.setRootPath(project_dir)
        self.project_tree.setRootIndex(self.project_model.index(project_dir))
        self.db_manager.set_setting('last_project_dir', project_dir)
        self.project_dock.setWindowTitle(f"Project: {os.path.basename(project_dir)}")

    def _setup_menubar(self):
        """Creates the standard top application menu bar."""
        # Standalone horizontal menu bar to sit above the ribbon toolbar
        menubar = QMenuBar()
        self.main_layout.addWidget(menubar)
        
        # File Menu
        file_menu = menubar.addMenu("File")
        
        new_action = self._create_action("New Project...", "Ctrl+N", self.new_estimate)
        file_menu.addAction(new_action)
        
        load_action = self._create_action("Load Project...", "Ctrl+O", self.load_estimate)
        file_menu.addAction(load_action)
        
        file_menu.addSeparator()
        
        save_action = self._create_action("Save Current", "Ctrl+S", self.trigger_save)
        file_menu.addAction(save_action)
        
        file_menu.addSeparator()
        
        settings_action = self._create_action("Settings...", None, self.open_settings)
        file_menu.addAction(settings_action)
        
        exit_action = self._create_action("Exit", "Alt+F4", self.close)
        file_menu.addAction(exit_action)
        
        # Edit Menu
        edit_menu = menubar.addMenu("Edit")
        
        undo_action = self._create_action("Undo", "Ctrl+Z", self.trigger_undo)
        edit_menu.addAction(undo_action)
        
        redo_action = self._create_action("Redo", "Ctrl+Y", self.trigger_redo)
        edit_menu.addAction(redo_action)
        
        # Windows Menu
        window_menu = menubar.addMenu("Window")
        
        db_action = self._create_action("Resources", None, self.manage_database)
        window_menu.addAction(db_action)
        
        rate_db_action = self._create_action("Libraries", None, self.manage_rate_database)
        window_menu.addAction(rate_db_action)

        # View Menu
        view_menu = menubar.addMenu("View")
        self.toggle_toolbar_action = self._create_action("Toggle Toolbar", "Ctrl+T", self.toggle_toolbar)
        self.toggle_toolbar_action.setCheckable(True)
        self.toggle_toolbar_action.setChecked(True)
        view_menu.addAction(self.toggle_toolbar_action)

    def _create_action(self, text, shortcut, slot):
        action = QAction(text, self)
        if shortcut:
            action.setShortcut(shortcut)
        action.triggered.connect(slot)
        return action

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
        self.navbar_container = QWidget()
        self.navbar_container_layout = QVBoxLayout(self.navbar_container)
        self.navbar_container_layout.setContentsMargins(0, 0, 0, 0)
        self.navbar_container_layout.setSpacing(0)

        self.navbar = QFrame()
        self.navbar.setObjectName("TopNavBar")
        # Reduced height from 80 to 45
        self.navbar.setFixedHeight(45) 
        self.navbar.setStyleSheet("""
            QFrame#TopNavBar {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1b5e20, stop:1 #2e7d32);
                border-bottom: 2px solid #1b5e20;
            }
            QPushButton {
                background-color: transparent;
                color: #ffff00;
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
                color: #ffff00;
                font-weight: bold;
            }
        """)

        layout = QHBoxLayout(self.navbar)
        # Reduced margins
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(10)

        # Branding
        branding_label = QLabel("Estimator Pro")
        
        branding_label.setStyleSheet("font-size: 14px; color: #ffff00;")
        layout.addWidget(branding_label)
        
        line = QFrame()
        line.setFrameShape(QFrame.Shape.VLine)
        line.setStyleSheet("background-color: rgba(255,255,255,0.3);")
        layout.addWidget(line)

        # Navigation Buttons
        nav_items = [
            ("New Project", self.new_estimate),
            ("Load Project", self.load_estimate),
            ("Resources", self.manage_database),
            ("Libraries", self.manage_rate_database),
            ("Settings", self.open_settings),
            ("BOQ Setup", self.open_boq_setup),
            ("SOR", self.open_sor_dialog),
            ("PBOQ", self.open_pboq_dialog)
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

        self.navbar_container_layout.addWidget(self.navbar)

        # Ribbon toggle button (small flap underneath)
        self.ribbon_toggle_btn = QPushButton("≡")
        self.ribbon_toggle_btn.setObjectName("RibbonToggleBtn")
        self.ribbon_toggle_btn.setFixedSize(40, 6) # Made as thin as possible
        self.ribbon_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.ribbon_toggle_btn.setToolTip("Toggle Toolbar (Ctrl+T)")
        self.ribbon_toggle_btn.setStyleSheet("""
            QPushButton#RibbonToggleBtn {
                background: #2e7d32;
                color: white;
                border: none;
                border-bottom-left-radius: 4px;
                border-bottom-right-radius: 4px;
                font-size: 6px; /* Extremely small */
                padding: 0px;
            }
            QPushButton#RibbonToggleBtn:hover {
                background: #1b5e20;
            }
        """)
        self.ribbon_toggle_btn.clicked.connect(self.toggle_toolbar)

        # Container for the toggle button to right-align it
        toggle_container = QWidget()
        toggle_layout = QHBoxLayout(toggle_container)
        toggle_layout.setContentsMargins(0, 0, 20, 0) # Add 20px right margin so it doesn't touch the very edge
        toggle_layout.setSpacing(0)
        toggle_layout.addStretch()
        toggle_layout.addWidget(self.ribbon_toggle_btn)
        # Removed the right stretch so it sits on the right side
        
        self.navbar_container_layout.addWidget(toggle_container)

        self.main_layout.addWidget(self.navbar_container)

    def toggle_toolbar(self):
        is_visible = self.navbar.isVisible()
        self.navbar.setVisible(not is_visible)
        
        if hasattr(self, 'toggle_toolbar_action'):
            self.toggle_toolbar_action.setChecked(self.navbar.isVisible())

    def new_estimate(self):
        dialog = NewEstimateDialog(self)
        if dialog.exec():
            data = dialog.get_data()
            est_window = EstimateWindow(estimate_data=data, main_window=self)
            
            # Instantly persist this newly minted estimate into the project DB so it's not "empty"
            est_window.db_manager.save_estimate(est_window.estimate)
            
            import os
            if data.get('db_path'):
                new_project_dir = os.path.dirname(os.path.dirname(data['db_path']))
                self._update_project_pane_directory(new_project_dir)

            self._add_estimate_window(est_window)

    def load_estimate(self):
        from PyQt6.QtWidgets import QFileDialog
        import os
        file_path, _ = QFileDialog.getOpenFileName(self, "Open Project", "", "Project Files (*.db);;All Files (*)")
        if file_path:
            # Update the project pane whenever a project is loaded
            project_dir = os.path.dirname(os.path.dirname(file_path)) if os.path.basename(os.path.dirname(file_path)) == "Project Database" else os.path.dirname(file_path)
            self._update_project_pane_directory(project_dir)

            from database import DatabaseManager
            temp_db = DatabaseManager(file_path)
            summaries = temp_db.get_saved_estimates_summary()
            
            if summaries:
                # We assume a project DB holds one main estimate
                self._load_and_show_estimate(summaries[0]['id'], db_path=file_path)
            # Removed the "Empty Project" warning to satisfy prior request of updating pane instead.

    def _load_and_show_estimate(self, est_id, db_path=None):
        db_path = db_path or "construction_costs.db"
        
        # Check if already open
        for sub in self.mdi_area.subWindowList():
            widget = sub.widget()
            if isinstance(widget, EstimateWindow) and widget.estimate.id == est_id and getattr(widget, 'db_path', None) == db_path:
                sub.showNormal()
                sub.show()
                sub.widget().show()
                sub.raise_()
                self.mdi_area.setActiveSubWindow(sub)
                return

        from database import DatabaseManager
        temp_db = DatabaseManager(db_path)
        estimate_obj = temp_db.load_estimate_details(est_id)
        if estimate_obj:
            est_window = EstimateWindow(estimate_object=estimate_obj, main_window=self, db_path=db_path)
            self._add_estimate_window(est_window)
        else:
            QMessageBox.critical(self, "Error", "Failed to load project from the file.")

    def open_rate_buildup_window(self, estimate_obj, db_path=None):
        """Opens a rate build-up in an MDI window."""
        # Check if already open
        for sub in self.mdi_area.subWindowList():
            widget = sub.widget()
            if isinstance(widget, RateBuildUpDialog) and widget.estimate.id == estimate_obj.id:
                sub.showNormal(); sub.show(); sub.raise_(); self.mdi_area.setActiveSubWindow(sub); return

        def refresh_manager():
            for s in self.mdi_area.subWindowList():
                w = s.widget()
                if type(w).__name__ == 'RateManagerDialog':
                    if hasattr(w, 'load_rates'): w.load_rates()
                    if hasattr(w, 'load_project_rates'): w.load_project_rates()

        buildup_win = RateBuildUpDialog(estimate_obj, main_window=self, db_path=db_path)
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
                sub.showNormal()
                sub.show()
                sub.widget().show()
                sub.raise_()
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
        """Opens the resources and highlights a specific resource."""
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
            db_sub.showNormal()
            db_sub.show()
            db_sub.widget().show()
            db_sub.raise_()
            self.mdi_area.setActiveSubWindow(db_sub)
            db_sub.widget().highlight_resource(table_name, resource_name)
        
    def _broadcast_library_update(self, table, name, val, curr, unit=""):
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
            unit_msg = f" @ {unit}" if unit else ""
            reply = QMessageBox.question(
                self, 
                "Update Dependent Rates and Estimates",
                f"The resource '{name}' is used in {total_affected} saved estimate(s)/rate(s).\n\n"
                f"Do you want to update all of them to the new rate, currency, and unit: {curr} {val:,.2f}{unit_msg}?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                db_costs.update_resource_in_all_estimates(table, name, val, curr, new_unit=unit)
                db_rates.update_resource_in_all_estimates(table, name, val, curr, new_unit=unit)
                
                # Force recalculation for nested composite rates and historical totals
                db_costs.recalculate_all_estimates()
                db_rates.recalculate_all_estimates()
                
                auto_update = True
        
        for sub in self.mdi_area.subWindowList():
            widget = sub.widget()
            if hasattr(widget, 'handle_library_update'):
                widget.handle_library_update(table, name, val, curr, unit, auto_update=auto_update)
            elif hasattr(widget, 'load_rates'):
                # Refresh Historical Rates view if open
                widget.load_rates()

    def manage_rate_database(self):
        for sub in self.mdi_area.subWindowList():
            if isinstance(sub.widget(), RateManagerDialog):
                sub.showNormal()
                sub.show()
                sub.widget().show()
                sub.raise_()
                self.mdi_area.setActiveSubWindow(sub)
                return
        
        # Pass self (MainWindow) to RateManagerDialog so it can open RateBuildUpDialog in MDI
        dialog = RateManagerDialog(self) 
        sub = self.mdi_area.addSubWindow(dialog)
        sub.resize(900, 550)
        self._apply_zoom_to_subwindow(sub)
        sub.show()

    def show_rate_in_database(self, rate_code):
        """Opens the libraries and highlights a specific rate."""
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
            rate_sub.showNormal()
            rate_sub.show()
            rate_sub.widget().show()
            rate_sub.raise_()
            self.mdi_area.setActiveSubWindow(rate_sub)
            rate_sub.widget().highlight_rate(rate_code)

    def open_settings(self):
        active_est = self._get_active_estimate_window()
        import os
        from PyQt6.QtWidgets import QMessageBox
        
        db_path = None
        estimate_obj = None
        library_path = ""
        project_dir = ""
        
        project_dir_fallback = self.db_manager.get_setting('last_project_dir', '')
        
        if active_est and type(active_est).__name__ == "EstimateWindow":
            db_path = active_est.db_path
            estimate_obj = active_est.estimate
            library_path = active_est.library_path
            project_dir = os.path.dirname(db_path) if db_path else ""
            if project_dir and os.path.basename(project_dir) == "Project Database":
                project_dir = os.path.dirname(project_dir)
        else:
            project_dir = project_dir_fallback
            if project_dir and os.path.exists(project_dir):
                db_dir = os.path.join(project_dir, "Project Database")
                if os.path.exists(db_dir):
                    dbs = [f for f in os.listdir(db_dir) if f.endswith('.db')]
                    if dbs:
                        db_path = os.path.join(db_dir, dbs[0])
                        from database import DatabaseManager
                        temp_db = DatabaseManager(db_path)
                        summaries = temp_db.get_saved_estimates_summary()
                        if summaries:
                            estimate_obj = temp_db.load_estimate_details(summaries[0]['id'])
                            library_path = temp_db.get_setting('library_path', '')

        # Check if settings window already open
        for sub in self.mdi_area.subWindowList():
            if isinstance(sub.widget(), SettingsDialog):
                sub.showNormal()
                sub.show()
                sub.widget().show()
                sub.raise_()
                self.mdi_area.setActiveSubWindow(sub)
                return

        dialog = SettingsDialog(estimate_obj, project_dir, library_path, self)
        if dialog.exec():
            data = dialog.get_project_data()
            if data:
                import re
                if estimate_obj:
                    estimate_obj.project_name = data['name']
                    estimate_obj.client_name = data['client']
                    estimate_obj.date = data['date']
                    estimate_obj.overhead_percent = data['overhead']
                    estimate_obj.profit_margin_percent = data['profit']
                    estimate_obj.currency = data['currency']
                
                if active_est and type(active_est).__name__ == "EstimateWindow":
                    active_est.save_state()
                    active_est.library_path = data['library_path']
                    if estimate_obj:
                        match = re.search(r'\((.*?)\)', estimate_obj.currency)
                        active_est.currency_symbol = match.group(1) if match else "$"
                        active_est.db_manager.save_estimate(estimate_obj)
                    active_est.db_manager.set_setting('library_path', data['library_path'])
                    active_est.refresh_view()
                    active_est.setWindowTitle(f"Estimate: {data['name']}")
                else:
                    if db_path:
                        from database import DatabaseManager
                        temp_db = DatabaseManager(db_path)
                        if estimate_obj:
                            temp_db.save_estimate(estimate_obj)
                        temp_db.set_setting('library_path', data['library_path'])
                        temp_db.set_setting('overhead', str(data['overhead']))
                        temp_db.set_setting('profit', str(data['profit']))
                        temp_db.set_setting('currency', data['currency'])

    def open_boq_setup(self):
        active_est = self._get_active_estimate_window()
        
        import os
        project_dir = ""
        if active_est and type(active_est).__name__ == "EstimateWindow":
            db_path = active_est.db_path
            project_dir = os.path.dirname(db_path) if db_path else ""
        else:
            project_dir = self.db_manager.get_setting('last_project_dir', '')
            if not project_dir or not os.path.exists(project_dir):
                from PyQt6.QtWidgets import QFileDialog
                project_dir = QFileDialog.getExistingDirectory(self, "Select Project Directory", "")
                if not project_dir: return
            
        if project_dir and os.path.basename(project_dir) == "Project Database":
            project_dir = os.path.dirname(project_dir)
            
        if not project_dir or not os.path.exists(project_dir):
            QMessageBox.warning(self, "Error", "Project directory is invalid.")
            return
            
        boq_dir = os.path.join(project_dir, "Imported BOQs")
        boq_files = []
        if os.path.exists(boq_dir):
            boq_files = [f for f in os.listdir(boq_dir) if f.lower().endswith(('.xlsx', '.xls'))]
            
        if not boq_files:
            QMessageBox.information(self, "No BOQs", "No Excel BOQ files found in this project 'Imported BOQs' directory.\nPlease import them via Project Settings or New Project Dialog.")
            return
            
        # Automatically bypass dialog and select the most recently modified BOQ
        boq_files.sort(key=lambda f: os.path.getmtime(os.path.join(boq_dir, f)), reverse=True)
        target_boq = boq_files[0]
            
        full_path = os.path.join(boq_dir, target_boq)
        
        from boq_setup import BOQSetupWindow
        # Check if already open
        for sub in self.mdi_area.subWindowList():
            if isinstance(sub.widget(), BOQSetupWindow) and sub.widget().boq_file_path == full_path:
                sub.showNormal()
                sub.show()
                sub.widget().show()
                sub.raise_()
                self.mdi_area.setActiveSubWindow(sub)
                return
                
        dialog = BOQSetupWindow(full_path, active_est, self, project_dir=project_dir)
        sub = self.mdi_area.addSubWindow(dialog)
        sub.resize(1050, 500)
        self._apply_zoom_to_subwindow(sub)
        sub.show()

    def open_sor_dialog(self):
        active_est = self._get_active_estimate_window()
            
        import os
        project_dir = ""
        if active_est and type(active_est).__name__ == "EstimateWindow":
            db_path = active_est.db_path
            project_dir = os.path.dirname(db_path) if db_path else ""
        else:
            project_dir = self.db_manager.get_setting('last_project_dir', '')
            if not project_dir or not os.path.exists(project_dir):
                from PyQt6.QtWidgets import QFileDialog
                project_dir = QFileDialog.getExistingDirectory(self, "Select Project Directory", "")
                if not project_dir: return
            
        if project_dir and os.path.basename(project_dir) == "Project Database":
            project_dir = os.path.dirname(project_dir)
            
        if not project_dir or not os.path.exists(project_dir):
            QMessageBox.warning(self, "Error", "Project directory is invalid.")
            return
            
        from sor_viewer import SORDialog
        for sub in self.mdi_area.subWindowList():
            if isinstance(sub.widget(), SORDialog) and sub.widget().project_dir == project_dir:
                sub.showNormal()
                sub.show()
                sub.widget().show()
                sub.raise_()
                self.mdi_area.setActiveSubWindow(sub)
                return
                
        dialog = SORDialog(project_dir, self)
        sub = self.mdi_area.addSubWindow(dialog)
        sub.resize(1050, 500)
        self._apply_zoom_to_subwindow(sub)
        sub.show()
        
    def open_pboq_dialog(self):
        active_est = self._get_active_estimate_window()
            
        import os
        project_dir = ""
        if active_est and type(active_est).__name__ == "EstimateWindow":
            db_path = active_est.db_path
            project_dir = os.path.dirname(db_path) if db_path else ""
        else:
            project_dir = self.db_manager.get_setting('last_project_dir', '')
            if not project_dir or not os.path.exists(project_dir):
                from PyQt6.QtWidgets import QFileDialog
                project_dir = QFileDialog.getExistingDirectory(self, "Select Project Directory", "")
                if not project_dir: return
            
        if project_dir and os.path.basename(project_dir) == "Project Database":
            project_dir = os.path.dirname(project_dir)
            
        if not project_dir or not os.path.exists(project_dir):
            QMessageBox.warning(self, "Error", "Project directory is invalid.")
            return
            
        from pboq_viewer import PBOQDialog
        for sub in self.mdi_area.subWindowList():
            if isinstance(sub.widget(), PBOQDialog) and sub.widget().project_dir == project_dir:
                sub.showNormal()
                sub.show()
                sub.widget().show()
                sub.raise_()
                self.mdi_area.setActiveSubWindow(sub)
                return
                
        dialog = PBOQDialog(project_dir, self)
        sub = self.mdi_area.addSubWindow(dialog)
        sub.resize(1050, 500)
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
            
            # Apply Zebra stripe custom color globally
            zebra_color = self.db_manager.get_setting("color_zebra") or "#e8f5e9"
            new_style += f"""
                QTableWidget, QTreeWidget, QListWidget {{
                    alternate-background-color: {zebra_color};
                }}
            """
            
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
            
        # Update Project Pane
        import os
        if win and getattr(win, 'db_path', None):
            pdir = os.path.dirname(win.db_path)
            if pdir and os.path.basename(pdir) == "Project Database":
                pdir = os.path.dirname(pdir)
            if pdir and os.path.exists(pdir):
                self.db_manager.set_setting('last_project_dir', pdir)
                self.project_model.setRootPath(pdir)
                self.project_tree.setRootIndex(self.project_model.index(pdir))
                
                if self.project_dock.isHidden():
                    self.project_dock.show()


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
        
        self.overhead = QLineEdit('15.00')
        self.overhead.setValidator(validator)
        self.profit = QLineEdit('10.00')
        self.profit.setValidator(validator)
        
        self.currency = QComboBox()
        self.currency.addItems(["USD ($)", "EUR (€)", "GBP (£)", "JPY (¥)", "CAD ($)", "GHS (₵)", "CNY (¥)", "INR (₹)"])
        self.currency.setCurrentText('GHS (₵)')

        self.library_layout = QHBoxLayout()
        self.library_path = QLineEdit()
        self.library_path.setReadOnly(True)
        self.library_btn = QPushButton("Browse...")
        self.library_btn.clicked.connect(self._browse_library)
        self.library_layout.addWidget(self.library_path)
        self.library_layout.addWidget(self.library_btn)
        self.library_files = []

        self.project_dir_layout = QHBoxLayout()
        self.project_dir_path = QLineEdit()
        self.project_dir_path.setReadOnly(True)
        self.project_dir_btn = QPushButton("Browse...")
        self.project_dir_btn.clicked.connect(self._browse_project_dir)
        self.project_dir_layout.addWidget(self.project_dir_path)
        self.project_dir_layout.addWidget(self.project_dir_btn)

        self.boq_layout = QHBoxLayout()
        self.boq_path = QLineEdit()
        self.boq_path.setReadOnly(True)
        self.boq_btn = QPushButton("Browse...")
        self.boq_btn.clicked.connect(self._browse_boq)
        self.boq_layout.addWidget(self.boq_path)
        self.boq_layout.addWidget(self.boq_btn)
        self.boq_files = []

        layout.addRow("Project Name:", self.project_name)
        layout.addRow("Location:", self.location)
        layout.addRow("Project Date:", self.project_date)
        layout.addRow("Overhead (%):", self.overhead)
        layout.addRow("Profit (%):", self.profit)
        layout.addRow("Currency:", self.currency)
        layout.addRow("Library(ies):", self.library_layout)
        layout.addRow("Project Directory:", self.project_dir_layout)
        layout.addRow("Import Excel BOQs:", self.boq_layout)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _browse_library(self):
        from PyQt6.QtWidgets import QFileDialog
        import os
        file_paths, _ = QFileDialog.getOpenFileNames(self, "Select Library(ies)", "", "Database Files (*.db);;All Files (*)")
        if file_paths:
            self.library_files = file_paths
            names = [os.path.basename(f) for f in file_paths]
            self.library_path.setText(", ".join(names))

    def _browse_project_dir(self):
        from PyQt6.QtWidgets import QFileDialog
        dir_path = QFileDialog.getExistingDirectory(self, "Select Project Directory", "")
        if dir_path:
            self.project_dir_path.setText(dir_path)

    def _browse_boq(self):
        from PyQt6.QtWidgets import QFileDialog
        import os
        file_paths, _ = QFileDialog.getOpenFileNames(self, "Select Excel BOQ(s)", "", "Excel Files (*.xlsx *.xls);;All Files (*)")
        if file_paths:
            self.boq_files = file_paths
            names = [os.path.basename(f) for f in file_paths]
            self.boq_path.setText(", ".join(names))

    def accept(self):
        project_name = self.project_name.text().strip()
        selected_dir = self.project_dir_path.text().strip()
        if project_name and selected_dir:
            import os
            import shutil
            new_project_path = os.path.join(selected_dir, project_name)
            try:
                os.makedirs(new_project_path, exist_ok=True)
                # Copy libraries if selected
                if hasattr(self, 'library_files') and self.library_files:
                    lib_dir = os.path.join(new_project_path, "Imported Library")
                    os.makedirs(lib_dir, exist_ok=True)
                    for lib_file in self.library_files:
                        if os.path.exists(lib_file):
                            lib_filename = os.path.basename(lib_file)
                            new_lib_path = os.path.join(lib_dir, lib_filename)
                            shutil.copy2(lib_file, new_lib_path)
                
                if hasattr(self, 'boq_files') and self.boq_files:
                    boq_dir = os.path.join(new_project_path, "Imported BOQs")
                    os.makedirs(boq_dir, exist_ok=True)
                    for boq_file in self.boq_files:
                        if os.path.exists(boq_file):
                            boq_filename = os.path.basename(boq_file)
                            shutil.copy2(boq_file, os.path.join(boq_dir, boq_filename))
            except Exception as e:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(self, "Error", f"Failed to initialize project directory:\n{e}")
                return
        super().accept()

    def get_data(self):
        import os
        project_dir = self.project_dir_path.text().strip()
        project_name = self.project_name.text().strip()
        db_path = None
        if project_dir and project_name:
            db_dir = os.path.join(project_dir, project_name, "Project Database")
            os.makedirs(db_dir, exist_ok=True)
            db_path = os.path.join(db_dir, f"{project_name}.db")

        return {
            "name": project_name,
            "client": self.location.text(),
            "date": self.project_date.date().toString("yyyy-MM-dd"),
            "overhead": float(self.overhead.text() or 0),
            "profit": float(self.profit.text() or 0),
            "currency": self.currency.currentText(),
            "library_path": self.library_path.text(),
            "project_dir": project_dir,
            "boq_files": getattr(self, 'boq_files', []),
            "db_path": db_path
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
        self.setWindowTitle("Load Project")
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