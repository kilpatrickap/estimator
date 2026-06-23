# main.py

import sys
import os
import time
from PyQt6.QtWidgets import QApplication, QDialog
from PyQt6.QtCore import Qt, qInstallMessageHandler, QtMsgType
from main_window import MainWindow

# Suppressed patterns for Windows Qt theme compatibility
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
    
    # 1. Detect if running inside pytest or automated testing environments
    is_testing = (
        "pytest" in sys.modules or 
        "_pytest" in sys.modules or 
        os.environ.get("PYTEST_CURRENT_TEST") is not None
    )

    app = QApplication(sys.argv)

    # Apply a modern stylesheet for better look and feel and responsiveness
    # Load external stylesheet
    try:
        with open("styles.qss", "r") as f:
            app.setStyleSheet(f.read())
    except FileNotFoundError:
        print("Warning: styles.qss not found. Using default styles.")

    # 2. Database Connection Retry Loop (Ghost Process Lock Prevention)
    db_ok = False
    if not is_testing:
        from database import DatabaseManager
        for attempt in range(3):
            try:
                # Instantiating DatabaseManager will check database existence and migrate/init schemas.
                db = DatabaseManager()
                db_ok = True
                break
            except Exception as e:
                print(f"Database connection attempt {attempt+1} failed: {e}", file=sys.stderr)
                time.sleep(0.5)

    # 3. Present Trial Gating Splash Screen (unless in testing mode or if DB initialization failed)
    if not is_testing and db_ok:
        from trial_splash import TrialSplashDialog
        splash = TrialSplashDialog()
        if splash.exec() != QDialog.DialogCode.Accepted:
            # Splash closed or failed probabilistic roll. Terminate process.
            sys.exit(0)

    # 4. Launch MainWindow
    window = MainWindow()
    
    # Provide a comfortable default size (1400x767)
    # If the user has a smaller screen, it adapts by keeping at least a 100px margin around the edges.
    screen = app.primaryScreen().availableGeometry()
    width = min(1400, screen.width() - 100)
    height = min(767, screen.height() - 100)
    window.resize(width, height)
    
    window.show()
    sys.exit(app.exec())