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
    # Load external stylesheet
    try:
        with open("styles.qss", "r") as f:
            app.setStyleSheet(f.read())
    except FileNotFoundError:
        print("Warning: styles.qss not found. Using default styles.")

    window = MainWindow()
    window.show()
    sys.exit(app.exec())