# main.py

import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from main_window import MainWindow

if __name__ == "__main__":
    # Ensure high DPI scaling is handled correctly
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    
    app = QApplication(sys.argv)

    # Apply a modern stylesheet for better look and feel and responsiveness
    app.setStyleSheet("""
        QWidget {
            font-size: 14px;
            font-family: "Segoe UI", "Roboto", "Helvetica Neue", sans-serif;
        }
        QMainWindow {
            background-color: #f5f7f9;
        }
        QPushButton {
            background-color: #2e7d32; /* Richer Green */
            color: white;
            padding: 10px 20px;
            border: none;
            border-radius: 6px;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #388e3c;
        }
        QPushButton:pressed {
            background-color: #1b5e20;
        }
        QTableWidget, QTreeWidget {
            background-color: white;
            border: 1px solid #dcdfe6;
            border-radius: 4px;
            gridline-color: #f1f1f1;
        }
        QHeaderView::section {
            background-color: #f5f7f9;
            padding: 8px;
            border: none;
            border-bottom: 2px solid #dcdfe6;
            font-weight: bold;
        }
        QLineEdit, QDoubleSpinBox {
            padding: 8px;
            border: 1px solid #dcdfe6;
            border-radius: 4px;
            background-color: white;
        }
        QLineEdit:focus, QDoubleSpinBox:focus {
            border: 1px solid #4caf50;
        }
        QTabWidget::pane {
            border: 1px solid #dcdfe6;
            border-radius: 4px;
            background-color: white;
        }
        QTabBar::tab {
            padding: 10px 20px;
            background-color: #f0f2f5;
            border: 1px solid #dcdfe6;
            border-bottom: none;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
            margin-right: 2px;
        }
        QTabBar::tab:selected {
            background-color: white;
            border-bottom: 2px solid #2e7d32;
        }
    """)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())