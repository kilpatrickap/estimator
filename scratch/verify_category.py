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

def setup_category_test_project(base_path):
    project_dir = os.path.join(base_path, "CategoryProject")
    if os.path.exists(project_dir):
        import shutil
        shutil.rmtree(project_dir)
    os.makedirs(project_dir)
    os.makedirs(os.path.join(project_dir, "Project Database"))
    os.makedirs(os.path.join(project_dir, "Priced BOQs"))
    
    # 1. Master DB (No specific prelim rate)
    master_path = os.path.join(project_dir, "Project Database", "Master.db")
    conn = sqlite3.connect(master_path)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE settings (key TEXT, value TEXT)")
    cursor.execute("INSERT INTO settings VALUES ('currency', 'USD ($)')")
    cursor.execute("CREATE TABLE estimates (id INTEGER PRIMARY KEY, rate_code TEXT, net_total REAL)")
    cursor.execute("CREATE TABLE tasks (id INTEGER PRIMARY KEY, estimate_id INTEGER)")
    cursor.execute("CREATE TABLE estimate_materials (task_id INTEGER, price REAL, quantity REAL)")
    cursor.execute("CREATE TABLE estimate_labor (task_id INTEGER, rate REAL, hours REAL)")
    cursor.execute("CREATE TABLE estimate_plant (task_id INTEGER, rate REAL, hours REAL)")
    cursor.execute("CREATE TABLE estimate_equipment (task_id INTEGER, rate REAL, hours REAL)")
    cursor.execute("CREATE TABLE estimate_indirect_costs (task_id INTEGER, amount REAL)")
    cursor.execute("CREATE TABLE estimate_sub_rates (estimate_id INTEGER, quantity REAL)")
    conn.commit()
    conn.close()
    
    # 2. BOQ DB: One normal item and one item with PlugCategory='Preliminaries'
    boq_path = os.path.join(project_dir, "Priced BOQs", "BOQ.db")
    conn = sqlite3.connect(boq_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE pboq_items (
            Sheet TEXT, Description TEXT, Qty TEXT, [Bill Amount] TEXT, 
            PlugRate TEXT, PlugCode TEXT, PlugCategory TEXT
        )
    """)
    # Item 1: Normal Material Item (Fallback to Mat)
    cursor.execute("INSERT INTO pboq_items VALUES ('S1', 'Steel', '1', '100', '80', 'R1', '')")
    # Item 2: Preliminaries (Should go to Risk/Indirect and cost=bill)
    cursor.execute("INSERT INTO pboq_items VALUES ('S1', 'Site Office', '0', '500', '', '', 'Preliminaries')")
    conn.commit()
    conn.close()
    
    return project_dir

def verify_category_logic():
    print("Verifying Pricing Category Logic (Preliminaries)...")
    temp_dir = "temp_category"
    os.makedirs(temp_dir, exist_ok=True)
    project_path = setup_category_test_project(temp_dir)
    
    analytic = TestableAnalytic(project_path)
    analytic.refresh_data()
    
    # Total Bid = 100 (Steel) + 500 (Site Office) = 600
    # Total Cost = 80 (Steel) + 500 (Site Office Prelim Cost recovery) = 580
    
    bid_call = analytic.card_total_bid.update_value.call_args[0][0]
    cost_call = analytic.card_total_cost.update_value.call_args[0][0]
    print(f"Total Bid: {bid_call}, Total Cost: {cost_call}")
    assert "600.00" in bid_call
    assert "580.00" in cost_call
    
    # Donut Data: Should have Risk/Indirect = 500
    donut_data = analytic.donut_chart.set_data.call_args[0][0]
    res = {l: v for l, v, c in donut_data}
    print(f"Aggregated Resources: {res}")
    assert res.get('Risk/Indirect') == 500.0
    assert res.get('Materials') == 80.0
    
    print("\nCATEGORY VERIFICATION PASSED!")

if __name__ == "__main__":
    verify_category_logic()
