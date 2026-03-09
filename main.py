# main.py

import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, qInstallMessageHandler, QtMsgType
from main_window import MainWindow

# Filter out harmless Windows theme warnings (Python 3.14 + PyQt6 compatibility noise)
_SUPPRESSED_PATTERNS = ("OpenThemeData() failed", "External WM_DESTROY received")

def _qt_message_handler(msg_type, context, message):
    if message and any(pattern in message for pattern in _SUPPRESSED_PATTERNS):
        return  # Suppress known harmless warnings
    # Print all other messages normally
    if msg_type == QtMsgType.QtWarningMsg:
        print(f"Qt Warning: {message}", file=sys.stderr)
    elif msg_type == QtMsgType.QtCriticalMsg:
        print(f"Qt Critical: {message}", file=sys.stderr)
    elif msg_type == QtMsgType.QtFatalMsg:
        print(f"Qt Fatal: {message}", file=sys.stderr)
    elif msg_type == QtMsgType.QtInfoMsg:
        print(f"Qt Info: {message}", file=sys.stderr)

if __name__ == "__main__":
    # Suppress known harmless Qt warnings
    qInstallMessageHandler(_qt_message_handler)
    
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