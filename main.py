import sys
import os
import time
import ctypes
from PyQt6.QtWidgets import QApplication, QDialog
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import Qt, qInstallMessageHandler
from main_window import MainWindow
from version import APP_VERSION
from logger import setup_logging, setup_exception_hook, qt_message_handler, get_logger

if __name__ == "__main__":
    # 0. Initialize centralized logging and exception hook
    setup_logging()
    setup_exception_hook()
    log = get_logger("main")
    log.info(f"--- Estimator Pro v{APP_VERSION} starting up (Python {sys.version.split()[0]} on {sys.platform}) ---")

    # Set explicit AppUserModelID on Windows so the taskbar displays the custom icon properly
    if sys.platform == "win32":
        try:
            myappid = f"consar.estimatorpro.desktop.v{APP_VERSION}"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception as e:
            log.debug(f"Could not set AppUserModelID: {e}")

    # Suppress known harmless Qt warnings and redirect to Python logger
    qInstallMessageHandler(qt_message_handler)
    
    # Ensure high DPI scaling is handled correctly
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    
    # 1. Detect if running inside pytest or automated testing environments
    is_testing = (
        "pytest" in sys.modules or 
        "_pytest" in sys.modules or 
        os.environ.get("PYTEST_CURRENT_TEST") is not None
    )

    app = QApplication(sys.argv)

    # Set application icon (cascades to all windows and dialogs)
    base_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    icon_path = os.path.join(base_dir, "app_icon.ico")
    if not os.path.exists(icon_path):
        icon_path = "app_icon.ico"
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
        log.info(f"Application icon loaded from: {icon_path}")
    else:
        log.warning("app_icon.ico not found.")

    # Apply a modern stylesheet for better look and feel and responsiveness
    # Load external stylesheet
    try:
        style_path = os.path.join(base_dir, "styles.qss") if os.path.exists(os.path.join(base_dir, "styles.qss")) else "styles.qss"
        with open(style_path, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())
            log.info("Loaded custom stylesheet (styles.qss)")
    except FileNotFoundError:
        log.warning("styles.qss not found. Using default styles.")

    # 2. Database Connection Retry Loop (Ghost Process Lock Prevention)
    db_ok = False
    if not is_testing:
        from database import DatabaseManager
        for attempt in range(3):
            try:
                # Instantiating DatabaseManager will check database existence and migrate/init schemas.
                db = DatabaseManager()
                db_ok = True
                log.info(f"Database initialized successfully: {db.db_file}")
                break
            except Exception as e:
                log.error(f"Database connection attempt {attempt+1} failed: {e}", exc_info=True)
                time.sleep(0.5)

    # 3. Present Trial Gating Splash Screen (unless in testing mode or if DB initialization failed)
    if not is_testing and db_ok:
        from trial_splash import TrialSplashDialog
        splash = TrialSplashDialog()
        if splash.exec() != QDialog.DialogCode.Accepted:
            # Splash closed or failed probabilistic roll. Terminate process.
            log.info("Application closed from splash screen.")
            sys.exit(0)

    # 4. Launch MainWindow
    log.info("Initializing MainWindow...")
    window = MainWindow()
    
    # Provide a comfortable default size (1400x767)
    # If the user has a smaller screen, it adapts by keeping at least a 100px margin around the edges.
    screen = app.primaryScreen().availableGeometry()
    width = min(1400, screen.width() - 100)
    height = min(767, screen.height() - 100)
    window.resize(width, height)
    
    window.show()
    log.info("MainWindow displayed. Entering Qt event loop.")
    sys.exit(app.exec())