# PyTest/test_logger.py
"""
Unit tests for the centralized logging module (logger.py).
"""

import sys
import os
import logging
import tempfile
from unittest.mock import patch, MagicMock
import pytest
from logger import (
    get_log_dir,
    get_log_file_path,
    setup_logging,
    get_logger,
    setup_exception_hook,
    handle_uncaught_exception,
    qt_message_handler,
    get_recent_logs,
    open_log_directory,
    _SUPPRESSED_QT_PATTERNS,
)


def test_log_dir_and_path_resolution():
    log_dir = get_log_dir()
    assert os.path.exists(log_dir)
    log_file = get_log_file_path()
    assert log_file.endswith("estimator.log")
    assert os.path.dirname(log_file) == log_dir


def test_setup_logging_idempotent():
    # Calling setup_logging multiple times should not add duplicate handlers
    setup_logging()
    root = logging.getLogger()
    initial_handler_count = len(root.handlers)
    
    setup_logging()
    assert len(root.handlers) == initial_handler_count


def test_logger_writes_and_reads_recent():
    test_logger = get_logger("test_module")
    test_message = "Automated test diagnostic log message for Estimator Pro"
    test_logger.info(test_message)
    
    # Flush all root handlers
    for handler in logging.getLogger().handlers:
        handler.flush()
        
    recent = get_recent_logs(max_lines=50)
    assert test_message in recent


def test_qt_message_handler_suppresses_theme_warnings():
    from PyQt6.QtCore import QtMsgType

    mock_logger = MagicMock()
    with patch("logger.get_logger", return_value=mock_logger):
        # Harmless suppressed warning
        qt_message_handler(QtMsgType.QtWarningMsg, None, "OpenThemeData() failed for some control")
        mock_logger.warning.assert_not_called()

        # Regular warning
        qt_message_handler(QtMsgType.QtWarningMsg, None, "Actual real Qt layout warning")
        mock_logger.warning.assert_called_once()
        assert "Actual real Qt layout warning" in mock_logger.warning.call_args[0][0]


def test_qt_message_handler_levels():
    from PyQt6.QtCore import QtMsgType

    mock_logger = MagicMock()
    with patch("logger.get_logger", return_value=mock_logger):
        qt_message_handler(QtMsgType.QtCriticalMsg, None, "Critical Qt error")
        mock_logger.error.assert_called_once_with("Qt Critical: Critical Qt error")

        qt_message_handler(QtMsgType.QtFatalMsg, None, "Fatal Qt error")
        mock_logger.critical.assert_called_once_with("Qt Fatal: Fatal Qt error")

        qt_message_handler(QtMsgType.QtInfoMsg, None, "Informational Qt message")
        mock_logger.info.assert_called_once_with("Qt Info: Informational Qt message")


def test_handle_uncaught_exception():
    mock_logger = MagicMock()
    with patch("logger.get_logger", return_value=mock_logger), patch("sys.__excepthook__"):
        try:
            raise ValueError("Deliberate simulated crash error")
        except ValueError:
            exc_type, exc_val, exc_tb = sys.exc_info()
            handle_uncaught_exception(exc_type, exc_val, exc_tb)

        mock_logger.critical.assert_called_once()
        assert "UNCAUGHT APPLICATION EXCEPTION" in mock_logger.critical.call_args[0][0]
        assert "Deliberate simulated crash error" in mock_logger.critical.call_args[0][0]


def test_open_log_directory(monkeypatch):
    monkeypatch.setattr("sys.platform", "win32")
    with patch("os.startfile") as mock_startfile:
        success = open_log_directory()
        assert success is True
        mock_startfile.assert_called_once()
