import os
import sqlite3
import json
import sys
from unittest.mock import MagicMock

# Mock PyQt6
mock_qt = MagicMock()
sys.modules['PyQt6'] = mock_qt
sys.modules['PyQt6.QtWidgets'] = mock_qt
sys.modules['PyQt6.QtCore'] = mock_qt
sys.modules['PyQt6.QtGui'] = mock_qt
sys.modules['analytics_components'] = MagicMock()

sys.path.append(os.getcwd())
from analytics_financial_executive import FinancialExecutiveAnalytic

class TestableAnalytic(FinancialExecutiveAnalytic):
    def __init__(self, project_dir):
        self.project_dir = project_dir
        self.pboq_folder = os.path.join(self.project_dir, "Priced BOQs")
        self.pj_db_dir = os.path.join(self.project_dir, "Project Database")
        self.currency_symbol = "$" 
        self.overhead_rate = 0.0
        self.profit_rate = 0.0
        self._rate_cache = {}
        self.card_total_bid = MagicMock()
        self.card_total_cost = MagicMock()
        self.card_margin = MagicMock()
        self.card_overhead = MagicMock()
        self.donut_chart = MagicMock()
        self.pareto_chart = MagicMock()
        self.bridge_chart = MagicMock()
        self._clear_table = MagicMock()
        self._add_table_row = MagicMock()

def setup_overhead_test_project(base_path):
    project_dir = os.path.join(base_path, "OverheadProject")
    if os.path.exists(project_dir):
        import shutil
        shutil.rmtree(project_dir)
    os.makedirs(project_dir)
    os.makedirs(os.path.join(project_dir, "Project Database"))
    os.makedirs(os.path.join(project_dir, "Priced BOQs"))
    
    # 1. Master DB with 10% Overhead and 5% Profit settings
    master_path = os.path.join(project_dir, "Project Database", "Master.db")
    conn = sqlite3.connect(master_path)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE settings (key TEXT, value TEXT)")
    cursor.execute("INSERT INTO settings VALUES ('currency', 'USD ($)')")
    cursor.execute("INSERT INTO settings VALUES ('overhead', '10.0')")
    cursor.execute("INSERT INTO settings VALUES ('profit', '5.0')")
    
    # Simple estimate with 100 cost
    cursor.execute("CREATE TABLE estimates (id INTEGER PRIMARY KEY, rate_code TEXT, net_total REAL)")
    cursor.execute("INSERT INTO estimates (id, rate_code, net_total) VALUES (1, 'R1', 100.0)")
    cursor.execute("CREATE TABLE tasks (id INTEGER PRIMARY KEY, estimate_id INTEGER)")
    cursor.execute("INSERT INTO tasks (id, estimate_id) VALUES (10, 1)")
    cursor.execute("CREATE TABLE estimate_materials (task_id INTEGER, price REAL, quantity REAL)")
    cursor.execute("INSERT INTO estimate_materials VALUES (10, 100.0, 1.0)")
    cursor.execute("CREATE TABLE estimate_labor (task_id INTEGER, rate REAL, hours REAL)")
    cursor.execute("CREATE TABLE estimate_plant (task_id INTEGER, rate REAL, hours REAL)")
    cursor.execute("CREATE TABLE estimate_equipment (task_id INTEGER, rate REAL, hours REAL)")
    cursor.execute("CREATE TABLE estimate_indirect_costs (task_id INTEGER, amount REAL)")
    cursor.execute("CREATE TABLE estimate_sub_rates (estimate_id INTEGER, quantity REAL)")
    conn.commit()
    conn.close()
    
    # 2. BOQ DB: 1 unit, 100 cost, 115 bill (15% markup)
    boq_path = os.path.join(project_dir, "Priced BOQs", "BOQ.db")
    conn = sqlite3.connect(boq_path)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE pboq_items (Sheet TEXT, Description TEXT, Qty TEXT, [Bill Amount] TEXT, PlugRate TEXT, PlugCode TEXT)")
    cursor.execute("INSERT INTO pboq_items VALUES ('S1', 'Item 1', '1', '115.0', '100.0', 'R1')")
    conn.commit()
    conn.close()
    
    return project_dir

def verify_overhead_logic():
    print("Verifying Overhead Percentage Logic...")
    temp_dir = "temp_overhead"
    os.makedirs(temp_dir, exist_ok=True)
    project_path = setup_overhead_test_project(temp_dir)
    
    analytic = TestableAnalytic(project_path)
    analytic.refresh_data()
    
    # Check Settings Load
    print(f"Loaded Overhead Rate: {analytic.overhead_rate}%")
    assert analytic.overhead_rate == 10.0
    
    # Check Aggregation
    # Cost = 100, Bid = 115.
    # Overhead Amount = 100 * 0.10 = 10.
    # Overhead % of Bid = (10 / 115) * 100 = 8.695%
    # Profit Amount = 15 - 10 = 5.
    # Profit % of Bid = (5 / 115) * 100 = 4.347%
    
    overhead_call = analytic.card_overhead.update_value.call_args[0][0]
    profit_call = analytic.card_margin.update_value.call_args[0][0]
    
    print(f"Overhead Card: {overhead_call}")
    print(f"Profit Card: {profit_call}")
    
    assert "8.70%" in overhead_call
    assert "4.35%" in profit_call
    
    print("\nOVERHEAD VERIFICATION PASSED!")

if __name__ == "__main__":
    verify_overhead_logic()
