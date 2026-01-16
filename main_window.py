# main_window.py

from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
                             QFormLayout, QLineEdit, QDialog,
                             QDialogButtonBox, QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView, QSpacerItem,
                             QSizePolicy)
from PyQt6.QtGui import QFont, QDoubleValidator
from PyQt6.QtCore import Qt
from database_dialog import DatabaseManagerDialog
from estimate_window import EstimateWindow
from database import DatabaseManager


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Construction Estimating Software")
        self.setMinimumSize(600, 450)
        self.db_manager = DatabaseManager()

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)
        self.layout.setContentsMargins(40, 40, 40, 40)
        
        self.layout.addStretch(1)

        title = QLabel("Estimator Pro")
        title_font = QFont()
        title_font.setPointSize(32)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: #2e7d32; margin-bottom: 10px;")
        self.layout.addWidget(title)

        subtitle = QLabel("Professional Construction Cost Estimation")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("color: #606266; font-size: 16px; margin-bottom: 30px;")
        self.layout.addWidget(subtitle)

        # Container for buttons to control their max width on large screens
        button_container = QWidget()
        button_layout = QVBoxLayout(button_container)
        button_layout.setSpacing(15)

        self.new_estimate_btn = QPushButton("Create New Estimate")
        self.new_estimate_btn.setMinimumHeight(50)

        self.load_estimate_btn = QPushButton("Load Saved Estimate")
        self.load_estimate_btn.setMinimumHeight(50)

        self.manage_db_btn = QPushButton("Manage Cost Database")
        self.manage_db_btn.setMinimumHeight(50)

        button_layout.addWidget(self.new_estimate_btn)
        button_layout.addWidget(self.load_estimate_btn)
        button_layout.addWidget(self.manage_db_btn)
        
        # Center the button container and limit its width
        hbox = QHBoxLayout()
        hbox.addStretch(1)
        hbox.addWidget(button_container, 2) # Take up 2 units, stretches take 1 each side
        hbox.addStretch(1)
        
        self.layout.addLayout(hbox)
        self.layout.addStretch(1)

        self.estimate_win = None
        self.db_dialog = None

        self.new_estimate_btn.clicked.connect(self.new_estimate)
        self.load_estimate_btn.clicked.connect(self.load_estimate)
        self.manage_db_btn.clicked.connect(self.manage_database)

    def new_estimate(self):
        dialog = NewEstimateDialog(self)
        if dialog.exec():
            estimate_data = dialog.get_data()
            self.estimate_win = EstimateWindow(estimate_data=estimate_data)
            self.estimate_win.show()

    def load_estimate(self):
        dialog = LoadEstimateDialog(self)
        dialog.exec()
        if dialog.result() == QDialog.DialogCode.Accepted and dialog.selected_estimate_id:
            estimate_obj = self.db_manager.load_estimate_details(dialog.selected_estimate_id)
            if estimate_obj:
                self.estimate_win = EstimateWindow(estimate_object=estimate_obj)
                self.estimate_win.show()
            else:
                QMessageBox.critical(self, "Error", "Failed to load the selected estimate.")

    def manage_database(self):
        self.db_dialog = DatabaseManagerDialog(self)
        self.db_dialog.exec()


class NewEstimateDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Project Details")
        self.setMinimumWidth(400)
        layout = QFormLayout(self)

        self.project_name = QLineEdit("New Project")
        self.client_name = QLineEdit("Client Name")
        
        # Validator for numerical input
        pct_validator = QDoubleValidator(0.0, 100.0, 2)
        pct_validator.setNotation(QDoubleValidator.Notation.StandardNotation)

        self.overhead = QLineEdit()
        self.overhead.setPlaceholderText("0.00%")
        self.overhead.setText("15.00")
        self.overhead.setValidator(pct_validator)
        
        self.profit = QLineEdit()
        self.profit.setPlaceholderText("0.00%")
        self.profit.setText("10.00")
        self.profit.setValidator(pct_validator)

        layout.addRow("Project Name:", self.project_name)
        layout.addRow("Client Name:", self.client_name)
        layout.addRow("Overhead (%):", self.overhead)
        layout.addRow("Profit Margin (%):", self.profit)

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
            "client": self.client_name.text(),
            "overhead": overhead_val,
            "profit": profit_val
        }


class EditEstimateDialog(QDialog):
    """A dialog to edit an estimate's project name and client."""

    def __init__(self, project_name, client_name, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Estimate Details")
        self.setMinimumWidth(400)

        layout = QFormLayout(self)

        self.project_name_input = QLineEdit(project_name)
        self.client_name_input = QLineEdit(client_name)

        layout.addRow("Project Name:", self.project_name_input)
        layout.addRow("Client Name:", self.client_name_input)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def get_data(self):
        """Returns the new project and client names."""
        return self.project_name_input.text(), self.client_name_input.text()


class LoadEstimateDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.db_manager = DatabaseManager()
        self.selected_estimate_id = None
        self.setWindowTitle("Load Estimate")
        self.setMinimumSize(600, 400)

        layout = QVBoxLayout(self)
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["ID", "Project Name", "Client", "Date Created"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setColumnHidden(0, True)
        layout.addWidget(self.table)

        self.table.doubleClicked.connect(self.accept_selection)

        self.load_estimates()

        # --- START OF FIX ---
        # Corrected the typo QDialogButton-Box to QDialogButtonBox
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Open | QDialogButtonBox.StandardButton.Cancel)
        # --- END OF FIX ---
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

    def _get_selected_estimate_info(self):
        """Helper to get the ID, project name, and client of the selected estimate."""
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "Selection Error", "Please select an estimate first.")
            return None, None, None

        row_index = selected_rows[0].row()
        est_id = int(self.table.item(row_index, 0).text())
        project_name = self.table.item(row_index, 1).text()
        client_name = self.table.item(row_index, 2).text()
        return est_id, project_name, client_name

    def accept_selection(self):
        est_id, _, _ = self._get_selected_estimate_info()
        if est_id:
            self.selected_estimate_id = est_id
            self.accept()

    def edit_selected_estimate(self):
        est_id, project_name, client_name = self._get_selected_estimate_info()
        if not est_id:
            return

        dialog = EditEstimateDialog(project_name, client_name, self)
        if dialog.exec():
            new_project_name, new_client_name = dialog.get_data()
            if self.db_manager.update_estimate_metadata(est_id, new_project_name, new_client_name):
                QMessageBox.information(self, "Success", "Estimate details have been updated.")
                self.load_estimates()  # Refresh the list
            else:
                QMessageBox.critical(self, "Error", "Failed to update the estimate in the database.")

    def delete_selected_estimate(self):
        est_id, est_name, _ = self._get_selected_estimate_info()
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
        est_id, est_name, _ = self._get_selected_estimate_info()
        if not est_id:
            return

        if self.db_manager.duplicate_estimate(est_id):
            QMessageBox.information(self, "Success", f"Successfully created a copy of '{est_name}'.")
            self.load_estimates()
        else:
            QMessageBox.critical(self, "Error", "Failed to duplicate the estimate.")