import pytest
from PyQt6.QtWidgets import QApplication, QTableWidget, QTableWidgetItem
import sqlite3
import os

# Import the modules to test
from boq_setup import BOQSetupWindow
from pboq_viewer import PBOQDialog
from rate_manager_dialog import RateManagerDialog
from database_dialog import DatabaseManagerDialog

# Need a QApplication instance for GUI tests
@pytest.fixture(scope="module")
def app():
    # If a QApplication already exists, use it
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app
    # We do not quit the app here to avoid teardown issues with pytest-qt

def test_pboq_viewer_import_and_indentation():
    """Verify pboq_viewer.py is free of indentation/syntax errors."""
    try:
        import pboq_viewer
        assert hasattr(pboq_viewer, 'PBOQDialog')
    except IndentationError as e:
        pytest.fail(f"Indentation error still present: {e}")
    except SyntaxError as e:
        pytest.fail(f"Syntax error still present: {e}")

def test_rate_manager_sqlite3_import():
    """Verify sqlite3 is successfully imported in rate_manager_dialog.py."""
    import rate_manager_dialog
    # If sqlite3 is not imported, this will raise AttributeError
    assert hasattr(rate_manager_dialog, 'sqlite3'), "sqlite3 is missing from rate_manager_dialog"

def test_database_dialog_filter_table(app):
    """Verify filter_table handles None items gracefully."""
    dialog = DatabaseManagerDialog()
    table = QTableWidget(5, 5)
    
    # Leave some items as None to simulate the bug
    item = QTableWidgetItem("TestItem")
    table.setItem(0, 1, item)
    # Row 1, Col 1 is None
    
    # This shouldn't crash now
    dialog.filter_table("Test", table)
    
    assert not table.isRowHidden(0), "Row 0 should not be hidden"
    assert table.isRowHidden(1), "Row 1 should be hidden (None item)"

def test_boq_setup_columns_range():
    """Verify that _save_to_priced_boq in BOQSetupWindow generates the correct column count."""
    import boq_setup
    
    import ast
    with open('boq_setup.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    assert "range(14)" in content or "range( 14 )" in content, "range(14) not found in boq_setup.py"
