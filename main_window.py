# main_window.py

from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
                             QFormLayout, QLineEdit, QDoubleSpinBox, QDialog,
                             QDialogButtonBox, QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView, QSpacerItem,
                             QSizePolicy)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt
from database_dialog import DatabaseManagerDialog
from estimate_window import EstimateWindow
from database import DatabaseManager


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Construction Estimating Software")
        self.setMinimumSize(400, 350)
        self.db_manager = DatabaseManager()

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("Estimator Pro")
        font = QFont()
        font.setPointSize(24)
        font.setBold(True)
        title.setFont(font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(title)

        self.new_estimate_btn = QPushButton("Create New Estimate")
        self.new_estimate_btn.setMinimumHeight(40)

        self.load_estimate_btn = QPushButton("Load Saved Estimate")
        self.load_estimate_btn.setMinimumHeight(40)

        self.manage_db_btn = QPushButton("Manage Cost Database")
        self.manage_db_btn.setMinimumHeight(40)

        self.layout.addSpacing(20)
        self.layout.addWidget(self.new_estimate_btn)
        self.layout.addWidget(self.load_estimate_btn)
        self.layout.addWidget(self.manage_db_btn)

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
        layout = QFormLayout(self)

        self.project_name = QLineEdit("New Project")
        self.client_name = QLineEdit("Client Name")
        self.overhead = QDoubleSpinBox()
        self.overhead.setRange(0, 100)
        self.overhead.setValue(15)
        self.overhead.setSuffix("%")
        self.profit = QDoubleSpinBox()
        self.profit.setRange(0, 100)
        self.profit.setValue(10)
        self.profit.setSuffix("%")

        layout.addRow("Project Name:", self.project_name)
        layout.addRow("Client Name:", self.client_name)
        layout.addRow("Overhead:", self.overhead)
        layout.addRow("Profit Margin:", self.profit)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def get_data(self):
        return {
            "name": self.project_name.text(),
            "client": self.client_name.text(),
            "overhead": self.overhead.value(),
            "profit": self.profit.value()
        }


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
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnHidden(0, True)
        layout.addWidget(self.table)

        # Double-clicking a row is the same as selecting and clicking Load
        self.table.doubleClicked.connect(self.accept_selection)

        self.load_estimates()

        # --- START OF CHANGE: Add Delete/Duplicate buttons ---
        # Standard buttons (Load/Cancel)
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Open | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.button(QDialogButtonBox.StandardButton.Open).setText("Load Selected")
        self.button_box.accepted.connect(self.accept_selection)
        self.button_box.rejected.connect(self.reject)

        # Custom action buttons
        self.delete_btn = QPushButton("Delete Selected")
        self.duplicate_btn = QPushButton("Duplicate Selected")
        self.delete_btn.clicked.connect(self.delete_selected_estimate)
        self.duplicate_btn.clicked.connect(self.duplicate_selected_estimate)

        # Arrange buttons in a layout
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.delete_btn)
        button_layout.addWidget(self.duplicate_btn)
        button_layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        button_layout.addWidget(self.button_box)
        layout.addLayout(button_layout)
        # --- END OF CHANGE ---

    def load_estimates(self):
        self.table.setRowCount(0)  # Clear table before loading
        estimates = self.db_manager.get_saved_estimates_summary()
        self.table.setRowCount(len(estimates))
        for row, est in enumerate(estimates):
            self.table.setItem(row, 0, QTableWidgetItem(str(est['id'])))
            self.table.setItem(row, 1, QTableWidgetItem(est['project_name']))
            self.table.setItem(row, 2, QTableWidgetItem(est['client_name']))
            self.table.setItem(row, 3, QTableWidgetItem(est['date_created']))

    def _get_selected_estimate_info(self):
        """Helper to get the ID and name of the selected estimate."""
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "Selection Error", "Please select an estimate first.")
            return None, None

        row_index = selected_rows[0].row()
        est_id = int(self.table.item(row_index, 0).text())
        est_name = self.table.item(row_index, 1).text()
        return est_id, est_name

    def accept_selection(self):
        est_id, _ = self._get_selected_estimate_info()
        if est_id:
            self.selected_estimate_id = est_id
            self.accept()

    def delete_selected_estimate(self):
        est_id, est_name = self._get_selected_estimate_info()
        if not est_id:
            return

        reply = QMessageBox.question(self, "Confirm Delete",
                                     f"Are you sure you want to permanently delete '{est_name}'?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            if self.db_manager.delete_estimate(est_id):
                QMessageBox.information(self, "Success", f"'{est_name}' has been deleted.")
                self.load_estimates()  # Refresh the list
            else:
                QMessageBox.critical(self, "Error", "Failed to delete the estimate from the database.")

    def duplicate_selected_estimate(self):
        est_id, est_name = self._get_selected_estimate_info()
        if not est_id:
            return

        if self.db_manager.duplicate_estimate(est_id):
            QMessageBox.information(self, "Success", f"Successfully created a copy of '{est_name}'.")
            self.load_estimates()  # Refresh to show the new copy
        else:
            QMessageBox.critical(self, "Error", "Failed to duplicate the estimate.")