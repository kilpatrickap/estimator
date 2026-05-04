import os
import sqlite3
import json
import pytest
import sys
from unittest.mock import MagicMock, patch

# Mock PyQt6
mock_qt = MagicMock()
sys.modules['PyQt6'] = mock_qt
sys.modules['PyQt6.QtWidgets'] = mock_qt
sys.modules['PyQt6.QtCore'] = mock_qt
sys.modules['PyQt6.QtGui'] = mock_qt
sys.modules['analytics_components'] = MagicMock()

# Ensure we can import the module
sys.path.append(os.getcwd())
from analytics_financial_executive import FinancialExecutiveAnalytic

class MockMetricCard:
    def __init__(self):
        self.update_value = MagicMock()

class MockChart:
    def __init__(self):
        self.set_data = MagicMock()

@pytest.fixture
def mock_project(tmp_path):
    project_dir = tmp_path / "MeticulousProject"
    project_dir.mkdir()
    
    (project_dir / "Project Database").mkdir()
    (project_dir / "Priced BOQs").mkdir()
    (project_dir / "PBOQ States").mkdir()
    
    # 1. Master DB
    master_path = project_dir / "Project Database" / "Master.db"
    conn = sqlite3.connect(master_path)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE settings (key TEXT, value TEXT)")
    cursor.execute("INSERT INTO settings VALUES ('currency', 'GHS (₵)')")
    
    cursor.execute("CREATE TABLE estimates (id INTEGER PRIMARY KEY, rate_code TEXT, net_total REAL)")
    # R1: 60% Mat, 40% Lab
    cursor.execute("INSERT INTO estimates (id, rate_code, net_total) VALUES (1, 'R1', 100.0)")
    # R2: 100% Plant
    cursor.execute("INSERT INTO estimates (id, rate_code, net_total) VALUES (2, 'R2', 50.0)")
    
    cursor.execute("CREATE TABLE tasks (id INTEGER PRIMARY KEY, estimate_id INTEGER)")
    cursor.execute("INSERT INTO tasks (id, estimate_id) VALUES (10, 1), (20, 2)")
    
    cursor.execute("CREATE TABLE estimate_materials (task_id INTEGER, price REAL, quantity REAL)")
    cursor.execute("INSERT INTO estimate_materials VALUES (10, 60.0, 1.0)")
    
    cursor.execute("CREATE TABLE estimate_labor (task_id INTEGER, rate REAL, hours REAL)")
    cursor.execute("INSERT INTO estimate_labor VALUES (10, 40.0, 1.0)")
    
    cursor.execute("CREATE TABLE estimate_plant (task_id INTEGER, rate REAL, hours REAL)")
    cursor.execute("INSERT INTO estimate_plant (task_id, rate, hours) VALUES (20, 50.0, 1.0)")
    
    cursor.execute("CREATE TABLE estimate_equipment (task_id INTEGER, rate REAL, hours REAL)")
    cursor.execute("CREATE TABLE estimate_indirect_costs (task_id INTEGER, amount REAL)")
    cursor.execute("CREATE TABLE estimate_sub_rates (estimate_id INTEGER, quantity REAL)")
    
    conn.commit()
    conn.close()
    
    # 2. BOQ DB
    boq_path = project_dir / "Priced BOQs" / "BOQ.db"
    conn = sqlite3.connect(boq_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE pboq_items (
            Sheet TEXT, Description TEXT, Qty TEXT, [Bill Amount] TEXT, 
            PlugRate TEXT, PlugCode TEXT, GrossRate TEXT, [Rate Code] TEXT
        )
    """)
    # Item A: Plug R1. 10 units. Bill 1500, Cost 1000 (10*100). 600 Mat, 400 Lab.
    cursor.execute("INSERT INTO pboq_items VALUES ('S1', 'Item A', '10', '1500', '100', 'R1', '', '')")
    # Item B: Gross R2. 1 unit. Bill 80, Cost 50. 50 Plant.
    cursor.execute("INSERT INTO pboq_items VALUES ('S1', 'Item B', '1', '80', '', '', '50', 'R2')")
    # Item C: Summary (SHOULD BE EXCLUDED)
    cursor.execute("INSERT INTO pboq_items VALUES ('S1', 'To Collection', '0', '1580', '', '', '', '')")
    
    conn.commit()
    conn.close()
    
    return str(project_dir)

def test_refresh_data_meticulous(mock_project):
    # Setup Analytic with Mocks
    with patch.object(FinancialExecutiveAnalytic, '_init_ui'):
        analytic = FinancialExecutiveAnalytic(mock_project)
        
        # Inject Mock UI components
        analytic.card_total_bid = MockMetricCard()
        analytic.card_total_cost = MockMetricCard()
        analytic.card_margin = MockMetricCard()
        analytic.donut_chart = MockChart()
        analytic.pareto_chart = MockChart()
        analytic.bridge_chart = MockChart()
        analytic._clear_table = MagicMock()
        analytic._add_table_row = MagicMock()
        
        # Run refresh
        analytic.refresh_data()
        
        # 1. VERIFY BID (1500 + 80 = 1580. Summary ignored)
        bid_val = analytic.card_total_bid.update_value.call_args[0][0]
        assert "1,580.00" in bid_val
        
        # 2. VERIFY COST (1000 + 50 = 1050)
        cost_val = analytic.card_total_cost.update_value.call_args[0][0]
        assert "1,050.00" in cost_val
        
        # 3. VERIFY MARGIN (1580 - 1050 = 530. 530/1580 = 33.54%)
        margin_val = analytic.card_margin.update_value.call_args[0][0]
        assert "33.54%" in margin_val
        
        # 4. VERIFY DONUT DATA (600 Mat, 400 Lab, 50 Plant)
        donut_data = analytic.donut_chart.set_data.call_args[0][0]
        res_map = {l: v for l, v, c in donut_data}
        assert res_map['Materials'] == 600.0
        assert res_map['Labor'] == 400.0
        assert res_map['Plant/Equip'] == 50.0
        
        # 5. VERIFY PARETO (Item A should be top)
        pareto_data = analytic.pareto_chart.set_data.call_args[0][0]
        assert pareto_data[0][0] == "Item A"
        assert pareto_data[0][1] == 1500.0
        
        # 6. VERIFY NO SUMMARY IN PARETO
        descs = [d for d, v, c in pareto_data]
        assert "To Collection" not in descs

if __name__ == "__main__":
    pytest.main([__file__])
