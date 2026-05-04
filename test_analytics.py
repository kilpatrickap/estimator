import os
import sqlite3
import json
import pytest
from unittest.mock import MagicMock, patch

# Mocking PyQt6 components to test logic without a GUI
import sys
from unittest.mock import MagicMock
mock_qt = MagicMock()
sys.modules['PyQt6'] = mock_qt
sys.modules['PyQt6.QtWidgets'] = mock_qt
sys.modules['PyQt6.QtCore'] = mock_qt
sys.modules['PyQt6.QtGui'] = mock_qt
sys.modules['analytics_components'] = MagicMock()

# Import the class to test
# We need to bypass the PyQt6 inheritance for pure logic testing if possible, 
# or just mock the UI methods.
from analytics_financial_executive import FinancialExecutiveAnalytic

@pytest.fixture
def temp_project(tmp_path):
    """Creates a mock project structure."""
    project_dir = tmp_path / "TestProject"
    project_dir.mkdir()
    
    pj_db_dir = project_dir / "Project Database"
    pj_db_dir.mkdir()
    
    pboq_dir = project_dir / "Priced BOQs"
    pboq_dir.mkdir()
    
    pboq_states_dir = project_dir / "PBOQ States"
    pboq_states_dir.mkdir()
    
    # 1. Create Master DB
    master_db = pj_db_dir / "Master.db"
    conn = sqlite3.connect(master_db)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE settings (key TEXT, value TEXT)")
    cursor.execute("INSERT INTO settings VALUES ('currency', 'USD ($)')")
    
    cursor.execute("CREATE TABLE estimates (id INTEGER PRIMARY KEY, rate_code TEXT, currency TEXT)")
    cursor.execute("INSERT INTO estimates (id, rate_code, currency) VALUES (1, 'R1', 'USD ($)')")
    
    cursor.execute("CREATE TABLE tasks (id INTEGER PRIMARY KEY, estimate_id INTEGER)")
    cursor.execute("INSERT INTO tasks (id, estimate_id) VALUES (10, 1)")
    
    cursor.execute("CREATE TABLE estimate_materials (task_id INTEGER, price REAL, quantity REAL)")
    cursor.execute("INSERT INTO estimate_materials VALUES (10, 50.0, 2.0)") # 100 cost
    
    cursor.execute("CREATE TABLE estimate_labor (task_id INTEGER, rate REAL, hours REAL)")
    cursor.execute("INSERT INTO estimate_labor VALUES (10, 20.0, 5.0)") # 100 cost
    
    conn.commit()
    conn.close()
    
    # 2. Create PBOQ DB
    pboq_db = pboq_dir / "BOQ1.db"
    conn = sqlite3.connect(pboq_db)
    cursor = conn.cursor()
    # Mocking a common PBOQ structure
    cursor.execute("CREATE TABLE pboq_items (Sheet TEXT, Description TEXT, Qty REAL, [Bill Amount] REAL, PlugRate REAL, PlugCode TEXT)")
    # Item 1: Using PlugRate 'R1' (Total cost 200, but composed of 100 Mat, 100 Lab)
    cursor.execute("INSERT INTO pboq_items VALUES ('S1', 'Item 1', 1.0, 300.0, 200.0, 'R1')")
    conn.commit()
    conn.close()
    
    return str(project_dir)

def test_financial_aggregation(temp_project):
    """Verifies that the financial dashboard correctly aggregates data and performs deep drill-down."""
    # We mock the __init__ to avoid UI initialization errors
    with patch.object(FinancialExecutiveAnalytic, '_init_ui'):
        analytic = FinancialExecutiveAnalytic(temp_project)
        
        # Manually trigger refresh
        analytic.refresh_data()
        
        # Check Currency
        assert analytic.currency_symbol == "$ "
        
        # Check Metric Cards (Mocks)
        # In our implementation, card_total_bid.update_value is called
        analytic.card_total_bid.update_value.assert_called()
        # The value should be '300.00'
        call_args = analytic.card_total_bid.update_value.call_args[0][0]
        assert "300.00" in call_args
        
        # Check Cost
        call_args_cost = analytic.card_total_cost.update_value.call_args[0][0]
        assert "200.00" in call_args_cost
        
        # Check Resource Distribution (Donut)
        # Total cost is 200. R1 ratio is 50% Mat, 50% Lab.
        # So we expect 100 Mat and 100 Lab.
        analytic.donut_chart.set_data.assert_called()
        data = analytic.donut_chart.set_data.call_args[0][0]
        
        # data is a list of tuples: (label, value, color)
        mat_val = next(v for l, v, c in data if l == "Materials")
        lab_val = next(v for l, v, c in data if l == "Labor")
        
        assert mat_val == 100.0
        assert lab_val == 100.0
