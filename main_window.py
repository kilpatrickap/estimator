# main_window.py

from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
                             QFormLayout, QLineEdit, QDialog, QComboBox, QDateEdit,
                             QDialogButtonBox, QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView, QSpacerItem,
                             QSizePolicy, QFrame, QListWidget, QListWidgetItem)
from PyQt6.QtGui import QFont, QDoubleValidator
from PyQt6.QtCore import Qt, QDate
from database_dialog import DatabaseManagerDialog
from estimate_window import EstimateWindow
from database import DatabaseManager
from chart_widget import DashboardChart
from settings_dialog import SettingsDialog


class MainWindow(QMainWindow):
    """Main dashboard for the estimating software."""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Construction Estimating Software")
        self.setMinimumSize(1200, 800)
        self.db_manager = DatabaseManager()

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QHBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self._setup_sidebar()
        self._setup_content_area()
        self.refresh_dashboard()

    def _setup_sidebar(self):
        """Creates the sidebar with primary navigation."""
        self.sidebar = QWidget()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setFixedWidth(280)
        
        layout = QVBoxLayout(self.sidebar)
        layout.setContentsMargins(30, 40, 30, 40)
        layout.setSpacing(20)

        # Title Section
        title = QLabel("Estimator Pro")
        title.setObjectName("SidebarTitle")
        layout.addWidget(title)

        subtitle = QLabel("Professional Construction\nCost Estimation")
        subtitle.setObjectName("SidebarSubtitle")
        layout.addWidget(subtitle)

        # Navigation Buttons
        nav_actions = [
            ("Create New Estimate", self.new_estimate),
            ("Load Saved Estimate", self.load_estimate),
            ("Manage Cost Database", self.manage_database),
            ("Settings", self.open_settings)
        ]

        for text, slot in nav_actions:
            btn = QPushButton(text)
            btn.setObjectName("SidebarBtn")
            btn.clicked.connect(slot)
            layout.addWidget(btn)

        layout.addStretch(1)
        self.main_layout.addWidget(self.sidebar)

    def _setup_content_area(self):
        """Creates the main dashboard content area."""
        self.content_widget = QWidget()
        self.content_widget.setStyleSheet("background-color: #f5f7f9;")
        
        layout = QVBoxLayout(self.content_widget)
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

        self.main_layout.addWidget(self.content_widget)

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
        # Update Stats
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
            self._load_and_show_estimate(est_id)

    def _load_and_show_estimate(self, est_id):
        estimate_obj = self.db_manager.load_estimate_details(est_id)
        if estimate_obj:
            self.estimate_win = EstimateWindow(estimate_object=estimate_obj)
            self.estimate_win.show()
        else:
            QMessageBox.critical(self, "Error", "Failed to load estimate.")

    def open_settings(self):
        SettingsDialog(self).exec()

    def new_estimate(self):
        dialog = NewEstimateDialog(self)
        if dialog.exec():
            self.estimate_win = EstimateWindow(estimate_data=dialog.get_data())
            self.estimate_win.show()
            self.refresh_dashboard()

    def load_estimate(self):
        dialog = LoadEstimateDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selected_estimate_id:
            self._load_and_show_estimate(dialog.selected_estimate_id)
            self.refresh_dashboard()
        else:
            self.refresh_dashboard()

    def manage_database(self):
        DatabaseManagerDialog(self).exec()


class NewEstimateDialog(QDialog):
    """Dialog for project initialization."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.db_manager = DatabaseManager()
        self.setWindowTitle("New Project Details")
        self.setMinimumWidth(480)
        
        layout = QFormLayout(self)
        layout.setSpacing(15)

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
        self.setMinimumWidth(480)
        layout = QFormLayout(self)

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
        self.setMinimumSize(1000, 700)

        layout = QVBoxLayout(self)
        self.table = QTableWidget(columnCount=4)
        self.table.setHorizontalHeaderLabels(["ID", "Project Name", "Location", "Date Created"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.setWordWrap(True)
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