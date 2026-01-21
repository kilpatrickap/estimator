# main_window.py

from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
                             QFormLayout, QLineEdit, QDialog, QComboBox, QDateEdit,
                             QDialogButtonBox, QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView, QSpacerItem,
                             QSizePolicy, QFrame, QListWidget, QListWidgetItem)
from PyQt6.QtGui import QFont, QDoubleValidator, QIcon
from PyQt6.QtCore import Qt, QDate
from database_dialog import DatabaseManagerDialog
from estimate_window import EstimateWindow
from database import DatabaseManager


from settings_dialog import SettingsDialog

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Construction Estimating Software")
        self.setMinimumSize(1200, 800)
        self.db_manager = DatabaseManager()

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        # Main Horizontal Layout: Sidebar + Content
        self.main_layout = QHBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self._setup_sidebar()
        self._setup_content_area()
        self.refresh_dashboard()

    def _setup_sidebar(self):
        self.sidebar = QWidget()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setFixedWidth(280)
        
        layout = QVBoxLayout(self.sidebar)
        layout.setContentsMargins(30, 40, 30, 40)
        layout.setSpacing(20)

        # Title
        title = QLabel("Estimator Pro")
        title.setObjectName("SidebarTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(title)

        subtitle = QLabel("Professional Construction\nCost Estimation")
        subtitle.setObjectName("SidebarSubtitle")
        layout.addWidget(subtitle)

        # Buttons
        self.new_estimate_btn = QPushButton("Create New Estimate")
        self.new_estimate_btn.setObjectName("SidebarBtn")
        
        self.load_estimate_btn = QPushButton("Load Saved Estimate")
        self.load_estimate_btn.setObjectName("SidebarBtn")
        
        self.manage_db_btn = QPushButton("Manage Cost Database")
        self.manage_db_btn.setObjectName("SidebarBtn")

        self.settings_btn = QPushButton("Settings")
        self.settings_btn.setObjectName("SidebarBtn")

        layout.addWidget(self.new_estimate_btn)
        layout.addWidget(self.load_estimate_btn)
        layout.addWidget(self.manage_db_btn)
        layout.addWidget(self.settings_btn)
        layout.addStretch(1)
        
        # Connect buttons
        self.new_estimate_btn.clicked.connect(self.new_estimate)
        self.load_estimate_btn.clicked.connect(self.load_estimate)
        self.manage_db_btn.clicked.connect(self.manage_database)
        self.settings_btn.clicked.connect(self.open_settings)

        self.main_layout.addWidget(self.sidebar)

    def _setup_content_area(self):
        self.content_widget = QWidget()
        self.content_widget.setStyleSheet("background-color: #f5f7f9;")
        
        layout = QVBoxLayout(self.content_widget)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(30)

        # Header
        header_layout = QHBoxLayout()
        header = QLabel("Dashboard")
        header.setStyleSheet("font-size: 28px; font-weight: bold; color: #424242;")
        header_layout.addWidget(header)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # Metrics Row
        self.metrics_container = QHBoxLayout()
        self.metrics_container.setSpacing(20)
        
        self.total_estimates_card = self._create_metric_card("Total Estimates", "0")
        self.total_value_card = self._create_metric_card("Total Value", "$0.00")
        
        self.metrics_container.addWidget(self.total_estimates_card)
        self.metrics_container.addWidget(self.total_value_card)
        self.metrics_container.addStretch(1) 
        
        layout.addLayout(self.metrics_container)

        # Recent Estimates Section
        section_label = QLabel("Recent Estimates")
        section_label.setObjectName("SectionHeader")
        layout.addWidget(section_label)

        self.recent_list = QListWidget()
        self.recent_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                background-color: white;
                padding: 10px;
            }
            QListWidget::item {
                padding: 15px;
                border-bottom: 1px solid #f0f0f0;
            }
            QListWidget::item:last {
                border-bottom: none;
            }
            QListWidget::item:hover {
                background-color: #f5f7f9;
            }
        """)
        self.recent_list.itemDoubleClicked.connect(self.open_recent_estimate)
        layout.addWidget(self.recent_list)

        self.main_layout.addWidget(self.content_widget)

    def _create_metric_card(self, label_text, value_text):
        card = QFrame()
        card.setObjectName("MetricCard")
        card.setFixedSize(220, 120)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 20, 20, 20)
        
        value = QLabel(value_text)
        value.setObjectName("MetricValue")
        label = QLabel(label_text)
        label.setObjectName("MetricLabel")
        
        card_layout.addWidget(value)
        card_layout.addWidget(label)
        card.value_label = value # Store reference to update later
        return card

    def refresh_dashboard(self):
        """Refreshes the metrics and recent list."""
        # Update Metrics
        count = self.db_manager.get_total_estimates_count()
        self.total_estimates_card.value_label.setText(str(count))
        
        total_value = self.db_manager.get_total_estimates_value()
        # Use simple formatting for now, assuming mostly one currency or just showing raw value
        # Ideally we'd segregate by currency, but for now let's just show the number
        self.total_value_card.value_label.setText(f"{total_value:,.2f}")

        # Update Recent List
        self.recent_list.clear()
        recents = self.db_manager.get_recent_estimates(5)
        
        if not recents:
            item = QListWidgetItem("No estimates found. Create a new one to get started!")
            item.setFlags(Qt.ItemFlag.NoItemFlags) # Make unselectable
            self.recent_list.addItem(item)
        else:
            for est in recents:
                # Store ID in UserRole to retrieve later
                item = QListWidgetItem(f"{est['project_name']} (Client: {est['client_name']})\n{est['date_created']}")
                item.setData(Qt.ItemDataRole.UserRole, est['id'])
                # Use a custom font or style if needed, but QSS handles most
                self.recent_list.addItem(item)

    def open_recent_estimate(self, item):
        est_id = item.data(Qt.ItemDataRole.UserRole)
        if est_id:
            estimate_obj = self.db_manager.load_estimate_details(est_id)
            if estimate_obj:
                self.estimate_win = EstimateWindow(estimate_object=estimate_obj)
                self.estimate_win.show()
                # Refresh dashboard when the estimate window closes could be a nice addition
            else:
                QMessageBox.critical(self, "Error", "Failed to load the selected estimate.")

    # --- Button Actions ---
    def open_settings(self):
        dialog = SettingsDialog(self)
        if dialog.exec():
            # If settings changed, maybe refresh dashboard or similar
            pass

    def new_estimate(self):
        dialog = NewEstimateDialog(self)
        if dialog.exec():
            estimate_data = dialog.get_data()
            self.estimate_win = EstimateWindow(estimate_data=estimate_data)
            self.estimate_win.show()
            self.refresh_dashboard()

    def load_estimate(self):
        dialog = LoadEstimateDialog(self)
        dialog.exec()
        if dialog.result() == QDialog.DialogCode.Accepted and dialog.selected_estimate_id:
            estimate_obj = self.db_manager.load_estimate_details(dialog.selected_estimate_id)
            if estimate_obj:
                self.estimate_win = EstimateWindow(estimate_object=estimate_obj)
                self.estimate_win.show()
                self.refresh_dashboard()
            else:
                QMessageBox.critical(self, "Error", "Failed to load the selected estimate.")
        else:
            self.refresh_dashboard() # In case they deleted something

    def manage_database(self):
        self.db_dialog = DatabaseManagerDialog(self)
        self.db_dialog.exec()


class NewEstimateDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.db_manager = DatabaseManager()
        self.setWindowTitle("New Project Details")
        self.setMinimumWidth(480)
        layout = QFormLayout(self)

        self.project_name = QLineEdit("New Project")
        self.location = QLineEdit("Project Location")
        
        self.project_date = QDateEdit()
        self.project_date.setCalendarPopup(True)
        self.project_date.setDisplayFormat("dd-MM-yy")
        self.project_date.setDate(QDate.currentDate())
        
        # Validator for numerical input
        pct_validator = QDoubleValidator(0.0, 100.0, 2)
        pct_validator.setNotation(QDoubleValidator.Notation.StandardNotation)

        # Load defaults from settings
        default_overhead = self.db_manager.get_setting('overhead', '15.00')
        default_profit = self.db_manager.get_setting('profit', '10.00')
        default_currency = self.db_manager.get_setting('currency', 'GHS (₵)')

        self.overhead = QLineEdit()
        self.overhead.setPlaceholderText("0.00%")
        self.overhead.setText(str(default_overhead))
        self.overhead.setValidator(pct_validator)
        
        self.profit = QLineEdit()
        self.profit.setPlaceholderText("0.00%")
        self.profit.setText(str(default_profit))
        self.profit.setValidator(pct_validator)

        self.currency = QComboBox()
        self.currency.addItems(["USD ($)", "EUR (€)", "GBP (£)", "JPY (¥)", "CAD ($)", "GHS (₵)", "CNY (¥)", "INR (₹)"])
        self.currency.setCurrentText(default_currency)

        layout.addRow("Project Name:", self.project_name)
        layout.addRow("Location:", self.location)
        layout.addRow("Project Date:", self.project_date)
        layout.addRow("Overhead (%):", self.overhead)
        layout.addRow("Profit Margin (%):", self.profit)
        layout.addRow("Currency:", self.currency)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def get_data(self):
        try:
            overhead_val = float(self.overhead.text())
        except ValueError:
            overhead_val = 0.0
            
        try:
            profit_val = float(self.profit.text())
        except ValueError:
            profit_val = 0.0

        return {
            "name": self.project_name.text(),
            "client": self.location.text(),
            "date": self.project_date.date().toString("yyyy-MM-dd"),
            "overhead": overhead_val,
            "profit": profit_val,
            "currency": self.currency.currentText()
        }


class EditEstimateDialog(QDialog):
    """A dialog to edit an estimate's project name, location, and date."""

    def __init__(self, project_name, location, project_date, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Estimate Details")
        self.setMinimumWidth(480)

        layout = QFormLayout(self)

        self.project_name_input = QLineEdit(project_name)
        self.location_input = QLineEdit(location)
        
        self.project_date_input = QDateEdit()
        self.project_date_input.setCalendarPopup(True)
        self.project_date_input.setDisplayFormat("dd-MM-yy")
        # Parse only the date part (first 10 chars) to handle strings with time
        qdate = QDate.fromString(project_date[:10], "yyyy-MM-dd")
        if qdate.isValid():
            self.project_date_input.setDate(qdate)
        else:
            self.project_date_input.setDate(QDate.currentDate())

        layout.addRow("Project Name:", self.project_name_input)
        layout.addRow("Location:", self.location_input)
        layout.addRow("Project Date:", self.project_date_input)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def get_data(self):
        """Returns the new project, location, and date."""
        return (
            self.project_name_input.text(), 
            self.location_input.text(),
            self.project_date_input.date().toString("yyyy-MM-dd")
        )


class LoadEstimateDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.db_manager = DatabaseManager()
        self.selected_estimate_id = None
        self.setWindowTitle("Load Estimate")
        self.setMinimumSize(1000, 700)

        layout = QVBoxLayout(self)
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["ID", "Project Name", "Location", "Date Created"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setMinimumSectionSize(100) # Ensure a reasonable minimum
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setShowGrid(True)
        self.table.setColumnHidden(0, True)
        layout.addWidget(self.table)

        self.table.doubleClicked.connect(self.accept_selection)

        self.load_estimates()

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Open | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.button(QDialogButtonBox.StandardButton.Open).setText("Load Selected")
        self.button_box.accepted.connect(self.accept_selection)
        self.button_box.rejected.connect(self.reject)

        self.edit_btn = QPushButton("Edit Selected")
        self.delete_btn = QPushButton("Delete Selected")
        self.duplicate_btn = QPushButton("Duplicate Selected")

        self.edit_btn.clicked.connect(self.edit_selected_estimate)
        self.delete_btn.clicked.connect(self.delete_selected_estimate)
        self.duplicate_btn.clicked.connect(self.duplicate_selected_estimate)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.edit_btn)
        button_layout.addWidget(self.delete_btn)
        button_layout.addWidget(self.duplicate_btn)
        button_layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        button_layout.addWidget(self.button_box)
        layout.addLayout(button_layout)

    def load_estimates(self):
        self.table.setRowCount(0)
        estimates = self.db_manager.get_saved_estimates_summary()
        self.table.setRowCount(len(estimates))
        for row, est in enumerate(estimates):
            self.table.setItem(row, 0, QTableWidgetItem(str(est['id'])))
            self.table.setItem(row, 1, QTableWidgetItem(est['project_name']))
            self.table.setItem(row, 2, QTableWidgetItem(est['client_name']))
            self.table.setItem(row, 3, QTableWidgetItem(est['date_created']))
        
        # Adjust widths
        for i in range(self.table.columnCount()):
            self.table.resizeColumnToContents(i)

    def _get_selected_estimate_info(self):
        """Helper to get the ID, project name, and client of the selected estimate."""
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "Selection Error", "Please select an estimate first.")
            return None, None, None, None

        row_index = selected_rows[0].row()
        est_id = int(self.table.item(row_index, 0).text())
        project_name = self.table.item(row_index, 1).text()
        client_name = self.table.item(row_index, 2).text()
        project_date = self.table.item(row_index, 3).text()
        return est_id, project_name, client_name, project_date

    def accept_selection(self):
        est_id, _, _, _ = self._get_selected_estimate_info()
        if est_id:
            self.selected_estimate_id = est_id
            self.accept()

    def edit_selected_estimate(self):
        est_id, project_name, location, project_date = self._get_selected_estimate_info()
        if not est_id:
            return

        dialog = EditEstimateDialog(project_name, location, project_date, self)
        if dialog.exec():
            new_project_name, new_location, new_date = dialog.get_data()
            if self.db_manager.update_estimate_metadata(est_id, new_project_name, new_location, new_date):
                QMessageBox.information(self, "Success", "Estimate details have been updated.")
                self.load_estimates()  # Refresh the list
            else:
                QMessageBox.critical(self, "Error", "Failed to update the estimate in the database.")

    def delete_selected_estimate(self):
        est_id, est_name, _, _ = self._get_selected_estimate_info()
        if not est_id:
            return

        reply = QMessageBox.question(self, "Confirm Delete",
                                     f"Are you sure you want to permanently delete '{est_name}'?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            if self.db_manager.delete_estimate(est_id):
                QMessageBox.information(self, "Success", f"'{est_name}' has been deleted.")
                self.load_estimates()
            else:
                QMessageBox.critical(self, "Error", "Failed to delete the estimate from the database.")

    def duplicate_selected_estimate(self):
        est_id, est_name, _, _ = self._get_selected_estimate_info()
        if not est_id:
            return

        if self.db_manager.duplicate_estimate(est_id):
            QMessageBox.information(self, "Success", f"Successfully created a copy of '{est_name}'.")
            self.load_estimates()
        else:
            QMessageBox.critical(self, "Error", "Failed to duplicate the estimate.")