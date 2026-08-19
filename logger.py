# logger.py
"""
Centralized logging system for Estimator Pro.

Provides rotating file logging, console streaming, uncaught exception trapping,
and Qt framework message redirection.
"""

import sys
import os
import logging
from logging.handlers import RotatingFileHandler
import traceback
import subprocess
from typing import Optional

# Suppressed patterns for Windows Qt theme / window manager compatibility
_SUPPRESSED_QT_PATTERNS = (
    "OpenThemeData() failed",
    "External WM_DESTROY received",
    "QWindowsWindow::setGeometry: Unable to set geometry",
)

_LOG_FORMAT = "%(asctime)s [%(levelname)s] [%(name)s:%(lineno)d] - %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
_DEFAULT_LOG_FILE = "estimator.log"
_MAX_BYTES = 5 * 1024 * 1024  # 5 MB per file
_BACKUP_COUNT = 5              # Keep 5 historical log backups


def get_log_dir() -> str:
    """
    Resolves the log directory.
    - Packaged/Frozen EXE: %APPDATA%/EstimatorPro/logs/ (or executable directory fallback)
    - Development mode: <project_root>/logs/
    """
    if getattr(sys, "frozen", False):
        appdata = os.environ.get("APPDATA")
        if appdata:
            log_dir = os.path.join(appdata, "EstimatorPro", "logs")
        else:
            exe_dir = os.path.dirname(sys.executable)
            log_dir = os.path.join(exe_dir, "logs")
    else:
        project_root = os.path.dirname(os.path.abspath(__file__))
        log_dir = os.path.join(project_root, "logs")

    try:
        os.makedirs(log_dir, exist_ok=True)
    except Exception as e:
        # Fallback to current working directory if permissions fail
        log_dir = os.path.join(os.getcwd(), "logs")
        os.makedirs(log_dir, exist_ok=True)

    return log_dir


def get_log_file_path() -> str:
    """Returns the full absolute path to the active estimator.log file."""
    return os.path.join(get_log_dir(), _DEFAULT_LOG_FILE)


def setup_logging(log_level: int = logging.INFO, log_to_console: bool = True) -> logging.Logger:
    """
    Initializes root logging with a RotatingFileHandler and optional console handler.
    Safe to call multiple times without duplicating handlers.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Check if our custom handlers are already installed
    has_file_handler = any(
        isinstance(h, RotatingFileHandler) and getattr(h, "_is_estimator_handler", False)
        for h in root_logger.handlers
    )

    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    if not has_file_handler:
        log_path = get_log_file_path()
        try:
            file_handler = RotatingFileHandler(
                log_path,
                maxBytes=_MAX_BYTES,
                backupCount=_BACKUP_COUNT,
                encoding="utf-8"
            )
            file_handler.setLevel(log_level)
            file_handler.setFormatter(formatter)
            file_handler._is_estimator_handler = True
            root_logger.addHandler(file_handler)
        except Exception as e:
            sys.stderr.write(f"Failed to initialize rotating file log handler: {e}\n")

    has_stream_handler = any(
        isinstance(h, logging.StreamHandler) and not isinstance(h, RotatingFileHandler) and getattr(h, "_is_estimator_handler", False)
        for h in root_logger.handlers
    )

    if log_to_console and not has_stream_handler:
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setLevel(log_level)
        stream_handler.setFormatter(formatter)
        stream_handler._is_estimator_handler = True
        root_logger.addHandler(stream_handler)

    return logging.getLogger("estimator")


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Retrieves a logger instance for a given module or subcomponent.
    If logging has not yet been initialized, performs a minimal setup.
    """
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        setup_logging()
    
    logger_name = f"estimator.{name}" if name and not name.startswith("estimator") else (name or "estimator")
    return logging.getLogger(logger_name)


def handle_uncaught_exception(exc_type, exc_value, exc_traceback):
    """
    Global exception hook that records fatal unhandled crashes to the log file.
    """
    if issubclass(exc_type, KeyboardInterrupt):
        # Allow Ctrl+C to terminate cleanly without alarming logs
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    logger = get_logger("crash_handler")
    tb_lines = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    logger.critical(f"UNCAUGHT APPLICATION EXCEPTION:\n{tb_lines}")

    # Call original system exception hook for standard terminal notification
    sys.__excepthook__(exc_type, exc_value, exc_traceback)


def setup_exception_hook():
    """Installs the uncaught exception hook."""
    sys.excepthook = handle_uncaught_exception


def qt_message_handler(msg_type, context, message):
    """
    Qt message handler that redirects Qt framework messages to Python's logging module
    while filtering out known harmless OS / styling warnings.
    """
    if message and any(pattern in message for pattern in _SUPPRESSED_QT_PATTERNS):
        return

    qt_logger = get_logger("qt")
    try:
        from PyQt6.QtCore import QtMsgType
        if msg_type == QtMsgType.QtWarningMsg:
            qt_logger.warning(f"Qt Warning: {message}")
        elif msg_type == QtMsgType.QtCriticalMsg:
            qt_logger.error(f"Qt Critical: {message}")
        elif msg_type == QtMsgType.QtFatalMsg:
            qt_logger.critical(f"Qt Fatal: {message}")
        elif msg_type == QtMsgType.QtInfoMsg:
            qt_logger.info(f"Qt Info: {message}")
        elif msg_type == QtMsgType.QtDebugMsg:
            qt_logger.debug(f"Qt Debug: {message}")
        else:
            qt_logger.info(f"Qt: {message}")
    except Exception:
        # Fallback if QtMsgType is unavailable
        qt_logger.warning(f"Qt Message: {message}")


def open_log_directory() -> bool:
    """
    Opens the log directory in the operating system's native file explorer.
    Returns True if launched successfully, False otherwise.
    """
    log_dir = get_log_dir()
    if not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)

    try:
        if sys.platform == "win32":
            os.startfile(log_dir)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", log_dir])
        else:
            subprocess.Popen(["xdg-open", log_dir])
        return True
    except Exception as e:
        logger = get_logger("system")
        logger.error(f"Failed to open log directory '{log_dir}': {e}")
        return False


def get_recent_logs(max_lines: int = 100) -> str:
    """
    Reads the last N lines from the active log file.
    Useful for diagnostic dialogs, bug reports, and support viewers.
    """
    log_path = get_log_file_path()
    if not os.path.exists(log_path):
        return "No log file found."

    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
            return "".join(lines[-max_lines:])
    except Exception as e:
        return f"Error reading log file: {e}"
