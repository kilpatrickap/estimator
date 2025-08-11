# database_dialog.py

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QTabWidget, QWidget, QPushButton,
                             QTableWidget, QTableWidgetItem, QHBoxLayout, QMessageBox,
                             QInputDialog, QLineEdit, QFormLayout, QDialogButtonBox)
from database import DatabaseManager


class DatabaseManagerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.db_manager = DatabaseManager()
        self.setWindowTitle("Manage Cost Database")
        self.setMinimumSize(600, 400)

        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # Create tabs
        self.materials_tab = QWidget()
        self.labor_tab = QWidget()
        self.tabs.addTab(self.materials_tab, "Materials")
        self.tabs.addTab(self.labor_tab, "Labor")

        # Setup UI for each tab
        self._setup_tab(self.materials_tab, "materials", ["ID", "Name", "Unit", "Price"])
        self._setup_tab(self.labor_tab, "labor", ["ID", "Trade", "Rate per Hour"])

    def _setup_tab(self, tab, table_name, headers):
        layout = QVBoxLayout(tab)
        table = QTableWidget()
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(table)
        setattr(self, f"{table_name}_table", table)

        btn_layout = QHBoxLayout()
        add_btn = QPushButton(f"Add {table_name.capitalize()[:-1]}")
        edit_btn = QPushButton(f"Edit Selected")
        delete_btn = QPushButton(f"Delete Selected")
        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(edit_btn)
        btn_layout.addWidget(delete_btn)
        layout.addLayout(btn_layout)

        # Connect signals
        add_btn.clicked.connect(lambda: self.add_item(table_name))
        edit_btn.clicked.connect(lambda: self.edit_item(table_name))
        delete_btn.clicked.connect(lambda: self.delete_item(table_name))

        self.load_data(table_name)

    def load_data(self, table_name):
        table = getattr(self, f"{table_name}_table")
        table.setRowCount(0)
        items = self.db_manager.get_items(table_name)
        for row_num, row_data in enumerate(items):
            table.insertRow(row_num)
            for col_num, data in enumerate(row_data):
                item = QTableWidgetItem(str(data))
                table.setItem(row_num, col_num, item)

    def add_item(self, table_name):
        dialog = ItemDialog(table_name, self)
        if dialog.exec():
            data = dialog.get_data()
            if not self.db_manager.add_item(table_name, data):
                QMessageBox.warning(self, "Error", "An item with this name already exists.")
            self.load_data(table_name)

    def edit_item(self, table_name):
        table = getattr(self, f"{table_name}_table")
        selected_row = table.currentRow()
        if selected_row < 0:
            QMessageBox.warning(self, "Selection Error", "Please select an item to edit.")
            return

        item_id = int(table.item(selected_row, 0).text())
        current_data = [table.item(selected_row, i).text() for i in range(1, table.columnCount())]

        dialog = ItemDialog(table_name, self, current_data)
        if dialog.exec():
            new_data = dialog.get_data()
            self.db_manager.update_item(table_name, item_id, new_data)
            self.load_data(table_name)

    def delete_item(self, table_name):
        table = getattr(self, f"{table_name}_table")
        selected_row = table.currentRow()
        if selected_row < 0:
            QMessageBox.warning(self, "Selection Error", "Please select an item to delete.")
            return

        item_id = int(table.item(selected_row, 0).text())
        item_name = table.item(selected_row, 1).text()

        reply = QMessageBox.question(self, "Confirm Delete", f"Are you sure you want to delete '{item_name}'?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.db_manager.delete_item(table_name, item_id)
            self.load_data(table_name)


class ItemDialog(QDialog):
    """A generic dialog to add/edit materials or labor."""

    def __init__(self, table_name, parent=None, data=None):
        super().__init__(parent)
        self.setWindowTitle(f"{'Edit' if data else 'Add'} {table_name.capitalize()[:-1]}")

        self.layout = QFormLayout(self)
        self.inputs = []

        if table_name == "materials":
            self.fields = [("Name", QLineEdit), ("Unit", QLineEdit), ("Price", QLineEdit)]
        else:  # labor
            self.fields = [("Trade", QLineEdit), ("Rate per Hour", QLineEdit)]

        for i, (label, widget_class) in enumerate(self.fields):
            widget = widget_class()
            if data:
                widget.setText(data[i])
            self.layout.addRow(label, widget)
            self.inputs.append(widget)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout.addWidget(self.button_box)

    def get_data(self):
        data = [widget.text() for widget in self.inputs]
        # Convert price/rate to float
        try:
            data[-1] = float(data[-1])
            return tuple(data)
        except ValueError:
            QMessageBox.warning(self, "Input Error", "Price/Rate must be a valid number.")
            return None