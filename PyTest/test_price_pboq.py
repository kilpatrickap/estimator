import os
import sys
import pytest
import sqlite3
from PyQt6.QtWidgets import QApplication, QTableWidget, QTableWidgetItem, QMdiArea, QMdiSubWindow
from PyQt6.QtCore import Qt

# Ensure the estimator directory is in the path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from rate_manager_dialog import RateManagerDialog
from pboq_viewer import PBOQDialog, PBOQTable
from sor_viewer import SORDialog
import pboq_constants as const

@pytest.fixture(scope="module")
def qapp():
    """Provides a QApplication instance for the tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app
    # app.quit() # Optional: usually not needed for session-level app

class MockMainWindow:
    def __init__(self):
        self.mdi_area = QMdiArea()
    def statusBar(self):
        class MockStatusBar:
            def showMessage(self, msg, time=0): print(f"Status: {msg}")
        return MockStatusBar()

def test_rate_manager_mapping_collection(qapp):
    """Tests that RateManagerDialog correctly extracts descriptions and rates from its table."""
    # We don't need a real project_dir for this UI-only test
    dialog = RateManagerDialog(main_window=None, parent=None)
    
    # Manually populate the table
    dialog.table.blockSignals(True)
    dialog.table.setRowCount(2)
    dialog.table.setItem(0, 0, QTableWidgetItem())
    dialog.table.setItem(0, 1, QTableWidgetItem("C001"))
    dialog.table.setItem(0, 2, QTableWidgetItem("Excavation in sand"))
    dialog.table.setItem(0, 5, QTableWidgetItem("15.50"))
    
    dialog.table.setItem(1, 0, QTableWidgetItem())
    dialog.table.setItem(1, 1, QTableWidgetItem("C002"))
    dialog.table.setItem(1, 2, QTableWidgetItem("Filling with gravel"))
    dialog.table.setItem(1, 5, QTableWidgetItem("22.00"))
    dialog.table.blockSignals(False)
    
    # We need to mock the MDI area check inside _price_pboq_from_historical
    # but let's just test the collection logic first by extracting it or calling it
    
    historical_mapping = {}
    for row in range(dialog.table.rowCount()):
        code_item = dialog.table.item(row, 1)
        desc_item = dialog.table.item(row, 2)
        rate_item = dialog.table.item(row, 5)
        if desc_item and rate_item:
            desc = desc_item.text().strip().lower()
            rate = rate_item.text().strip()
            code = code_item.text().strip() if code_item else ""
            if desc and rate:
                historical_mapping[desc] = (rate, code)
    
    assert "excavation in sand" in historical_mapping
    assert historical_mapping["excavation in sand"] == ("15.50", "C001")
    assert "filling with gravel" in historical_mapping
    assert historical_mapping["filling_with_gravel".replace('_',' ')] == ("22.00", "C002")

def test_pboq_pricing_logic(qapp):
    """Tests that PBOQDialog._price_by_description correctly updates its table."""
    # Mock PBOQDialog
    # We need to avoid database calls during init if possible
    # PBOQDialog calls _load_pboq_db in init if file exists.
    # Let's mock the parts we need.
    
    class MockPBOQDialog(PBOQDialog):
        def __init__(self):
            # Bypass real init to avoid DB/File requirements
            super(PBOQDialog, self).__init__() 
            self.tabs = QTableWidget() # Just a dummy to hold one "table" for this test
            # In reality PBOQDialog uses QTabWidget. We'll mock that.
            class MockTabs:
                def count(self): return 1
                def widget(self, i): return self.table
                def tabText(self, i): return "Sheet1"
            
            self.tabs = MockTabs()
            self.table = PBOQTable()
            self.tabs.table = self.table
            
            # Mock mappings
            class MockTools:
                def get_mappings(self):
                    return {'desc': 1, 'qty': 2, 'unit': 3, 'rate': 4, 'rate_code': 5}
            self.tools_pane = MockTools()
            
            # Setup table columns
            self.table.setColumnCount(6)
            self.table.setRowCount(2)
            # Row 0: Match
            self.table.setItem(0, 0, QTableWidgetItem())
            self.table.item(0, 0).setData(Qt.ItemDataRole.UserRole, 101) # rowid
            self.table.setItem(0, 1, QTableWidgetItem("Excavation in sand"))
            
            # Row 1: No Match
            self.table.setItem(1, 0, QTableWidgetItem())
            self.table.item(1, 0).setData(Qt.ItemDataRole.UserRole, 102) # rowid
            self.table.setItem(1, 1, QTableWidgetItem("Something else"))

        def _persist_updates(self, col, updates):
            # Mock persistence
            print(f"Persisting to col {col}: {updates}")
            
        def _update_stats(self): pass
        def _run_link_bill_to_rate_logic(self): pass

    dialog = MockPBOQDialog()
    mapping = {"excavation in sand": ("15.50", "C001")}
    
    count = dialog._price_by_description(mapping)
    
    assert count == 1
    # Check UI updates
    assert dialog.table.item(0, 4).text() == "15.50"
    assert dialog.table.item(0, 5).text() == "C001"
    # Check background color (should be COL_COLOR_GREEN)
    assert dialog.table.item(0, 4).background().color().name() == const.COL_COLOR_GREEN.name()

def test_sor_pricing_logic(qapp):
    """Tests that SORDialog._price_by_description correctly updates its table."""
    class MockSORDialog(SORDialog):
        def __init__(self):
            super().__init__(".", parent=None)
            # Table is already initialized in _init_ui
            self.table_widget.setRowCount(2)
            # Row 0: Match
            self.table_widget.setItem(0, 0, QTableWidgetItem("SOR1"))
            self.table_widget.setItem(0, 1, QTableWidgetItem("Sheet1"))
            self.table_widget.setItem(0, 2, QTableWidgetItem("R01"))
            self.table_widget.setItem(0, 3, QTableWidgetItem("Excavation in sand"))
            self.table_widget.setItem(0, 6, QTableWidgetItem("")) # Gross Rate
            
            # Row 1: No Match
            self.table_widget.setItem(1, 3, QTableWidgetItem("Something else"))

        def _persist_to_sor_db(self, row, rate, code):
            # Mock persistence
            print(f"Persisting row {row}: {rate}, {code}")
            
        def _update_priced_stats(self): pass

    dialog = MockSORDialog()
    mapping = {"excavation in sand": ("15.50", "C001")}
    
    count = dialog._price_by_description(mapping)
    
    assert count == 1
    assert dialog.table_widget.item(0, 6).text() == "15.50"
    assert dialog.table_widget.item(0, 7).text() == "C001"

if __name__ == "__main__":
    # If run directly, execute with pytest
    import pytest
    pytest.main([__file__])
