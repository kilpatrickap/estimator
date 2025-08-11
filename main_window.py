# main_window.py

from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QPushButton, QLabel,
                             QInputDialog, QFormLayout, QLineEdit, QDoubleSpinBox,
                             QDialog, QDialogButtonBox)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt
from database_dialog import DatabaseManagerDialog
from estimate_window import EstimateWindow


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Construction Estimating Software")
        self.setMinimumSize(400, 300)

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
        self.manage_db_btn = QPushButton("Manage Cost Database")
        self.manage_db_btn.setMinimumHeight(40)

        self.layout.addSpacing(20)
        self.layout.addWidget(self.new_estimate_btn)
        self.layout.addWidget(self.manage_db_btn)

        # Store window references to prevent garbage collection
        self.estimate_win = None
        self.db_dialog = None

        # Connect signals
        self.new_estimate_btn.clicked.connect(self.new_estimate)
        self.manage_db_btn.clicked.connect(self.manage_database)

    def new_estimate(self):
        dialog = NewEstimateDialog(self)
        if dialog.exec():
            estimate_data = dialog.get_data()
            # We must store the window in an instance variable
            self.estimate_win = EstimateWindow(estimate_data)
            self.estimate_win.show()

    def manage_database(self):
        # Pass self so the dialog is modal to this window
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