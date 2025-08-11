# main.py

import sys
from PyQt6.QtWidgets import QApplication
from main_window import MainWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Apply a simple stylesheet for better look and feel
    app.setStyleSheet("""
        QWidget {
            font-size: 14px;
        }
        QPushButton {
            background-color: #4CAF50; /* Green */
            color: white;
            padding: 8px;
            border: none;
            border-radius: 4px;
        }
        QPushButton:hover {
            background-color: #45a049;
        }
        QPushButton:pressed {
            background-color: #3e8e41;
        }
        QTableWidget {
            gridline-color: #d0d0d0;
        }
        QHeaderView::section {
            background-color: #e0e0e0;
            padding: 4px;
            border: 1px solid #d0d0d0;
        }
    """)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())