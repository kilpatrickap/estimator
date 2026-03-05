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
    
    # Provide a comfortable default size (1400x767)
    # If the user has a smaller screen, it adapts by keeping at least a 100px margin around the edges.
    screen = app.primaryScreen().availableGeometry()
    width = min(1400, screen.width() - 100)
    height = min(767, screen.height() - 100)
    window.resize(width, height)
    
    window.show()
    sys.exit(app.exec())