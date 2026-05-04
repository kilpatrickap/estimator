import os
import sqlite3
import json
import sys
from unittest.mock import MagicMock

# Mock PyQt6 completely
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
        # DO NOT call super().__init__ to avoid UI errors
        self.project_dir = project_dir
        self.pboq_folder = os.path.join(self.project_dir, "Priced BOQs")
        self.pj_db_dir = os.path.join(self.project_dir, "Project Database")
        self.currency_symbol = "$" 
        self._rate_cache = {}
        # Mocks for UI components
        self.card_total_bid = MagicMock()
        self.card_total_cost = MagicMock()
        self.card_margin = MagicMock()
        self.donut_chart = MagicMock()
        self.pareto_chart = MagicMock()
        self.bridge_chart = MagicMock()
        self._clear_table = MagicMock()
        self._add_table_row = MagicMock()

def setup_mock_project(base_path):
    project_dir = os.path.join(base_path, "MeticulousProject_v4")
    if os.path.exists(project_dir):
        import shutil
        shutil.rmtree(project_dir)
    os.makedirs(project_dir)
    os.makedirs(os.path.join(project_dir, "Project Database"))
    os.makedirs(os.path.join(project_dir, "Priced BOQs"))
    os.makedirs(os.path.join(project_dir, "PBOQ States"))
    
    # 1. Master DB
    master_path = os.path.join(project_dir, "Project Database", "Master.db")
    conn = sqlite3.connect(master_path)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE settings (key TEXT, value TEXT)")
    cursor.execute("INSERT INTO settings VALUES ('currency', 'USD ($)')")
    cursor.execute("CREATE TABLE estimates (id INTEGER PRIMARY KEY, rate_code TEXT, net_total REAL)")
    cursor.execute("INSERT INTO estimates (id, rate_code, net_total) VALUES (1, 'R1', 1000.0)")
    cursor.execute("INSERT INTO estimates (id, rate_code, net_total) VALUES (2, 'R2', 500.0)")
    cursor.execute("CREATE TABLE tasks (id INTEGER PRIMARY KEY, estimate_id INTEGER)")
    cursor.execute("INSERT INTO tasks (id, estimate_id) VALUES (10, 1), (20, 2)")
    cursor.execute("CREATE TABLE estimate_materials (task_id INTEGER, price REAL, quantity REAL)")
    cursor.execute("INSERT INTO estimate_materials VALUES (10, 700.0, 1.0)")
    cursor.execute("CREATE TABLE estimate_labor (task_id INTEGER, rate REAL, hours REAL)")
    cursor.execute("INSERT INTO estimate_labor VALUES (10, 300.0, 1.0)")
    cursor.execute("CREATE TABLE estimate_plant (task_id INTEGER, rate REAL, hours REAL)")
    cursor.execute("INSERT INTO estimate_plant (task_id, rate, hours) VALUES (20, 500.0, 1.0)")
    cursor.execute("CREATE TABLE estimate_equipment (task_id INTEGER, rate REAL, hours REAL)")
    cursor.execute("CREATE TABLE estimate_indirect_costs (task_id INTEGER, amount REAL)")
    cursor.execute("CREATE TABLE estimate_sub_rates (estimate_id INTEGER, quantity REAL)")
    conn.commit()
    conn.close()
    
    # 2. BOQ DB
    boq_path = os.path.join(project_dir, "Priced BOQs", "BOQ.db")
    conn = sqlite3.connect(boq_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE pboq_items (
            Sheet TEXT, Description TEXT, Qty TEXT, [Bill Amount] TEXT, 
            PlugRate TEXT, PlugCode TEXT, GrossRate TEXT, [Rate Code] TEXT
        )
    """)
    # Item A: 1500 Bill, 1000 Cost (700 Mat, 300 Lab)
    cursor.execute("INSERT INTO pboq_items VALUES ('S1', 'Item A', '1', '1500', '1000', 'R1', '', '')")
    # Item B: 800 Bill, 500 Cost (500 Plant)
    cursor.execute("INSERT INTO pboq_items VALUES ('S1', 'Item B', '1', '800', '', '', '500', 'R2')")
    # Item C: Summary (SHOULD BE EXCLUDED)
    cursor.execute("INSERT INTO pboq_items VALUES ('S1', 'Summary Row', '0', '2300', '', '', '', '')")
    conn.commit()
    conn.close()
    return project_dir

def run_meticulous_verification():
    print("Starting Meticulous Verification (Subclass approach)...")
    temp_dir = "temp_meticulous_v4"
    os.makedirs(temp_dir, exist_ok=True)
    project_path = setup_mock_project(temp_dir)
    
    analytic = TestableAnalytic(project_path)
    analytic.refresh_data()
    
    # 1. Verify Bid
    bid_call = analytic.card_total_bid.update_value.call_args[0][0]
    print(f"Total Bid Card: {bid_call}")
    assert "2,300.00" in bid_call
    
    # 2. Verify Cost
    cost_call = analytic.card_total_cost.update_value.call_args[0][0]
    print(f"Total Cost Card: {cost_call}")
    assert "1,500.00" in cost_call
    
    # 3. Verify Ratios
    donut_data = analytic.donut_chart.set_data.call_args[0][0]
    res = {l: v for l, v, c in donut_data}
    print(f"Aggregated Resources: {res}")
    assert res.get('Materials') == 700.0
    assert res.get('Labor') == 300.0
    assert res.get('Plant/Equip') == 500.0
    
    # 4. Summary Exclusion
    pareto_data = analytic.pareto_chart.set_data.call_args[0][0]
    descs = [d for d, v, c in pareto_data]
    print(f"Pareto items: {descs}")
    assert "Summary Row" not in descs
    
    print("\nMETICULOUS VERIFICATION PASSED!")

if __name__ == "__main__":
    run_meticulous_verification()
