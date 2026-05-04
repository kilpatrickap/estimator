import os
import sqlite3
import json
import sys
from unittest.mock import MagicMock, patch

# Mock PyQt6
mock_qt = MagicMock()
sys.modules['PyQt6'] = mock_qt
sys.modules['PyQt6.QtWidgets'] = mock_qt
sys.modules['PyQt6.QtCore'] = mock_qt
sys.modules['PyQt6.QtGui'] = mock_qt
sys.modules['analytics_components'] = MagicMock()

sys.path.append(os.getcwd())
from analytics_financial_executive import FinancialExecutiveAnalytic

def setup_test_project(base_path):
    project_dir = os.path.join(base_path, "TestProject")
    os.makedirs(project_dir, exist_ok=True)
    
    pj_db_dir = os.path.join(project_dir, "Project Database")
    os.makedirs(pj_db_dir, exist_ok=True)
    
    pboq_dir = os.path.join(project_dir, "Priced BOQs")
    os.makedirs(pboq_dir, exist_ok=True)
    
    pboq_states_dir = os.path.join(project_dir, "PBOQ States")
    os.makedirs(pboq_states_dir, exist_ok=True)
    
    # 1. Master DB
    master_db = os.path.join(pj_db_dir, "Master.db")
    conn = sqlite3.connect(master_db)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE settings (key TEXT, value TEXT)")
    cursor.execute("INSERT INTO settings VALUES ('currency', 'USD ($)')")
    cursor.execute("CREATE TABLE estimates (id INTEGER PRIMARY KEY, rate_code TEXT, currency TEXT)")
    cursor.execute("INSERT INTO estimates (id, rate_code, currency) VALUES (1, 'R1', 'USD ($)')")
    cursor.execute("CREATE TABLE tasks (id INTEGER PRIMARY KEY, estimate_id INTEGER)")
    cursor.execute("INSERT INTO tasks (id, estimate_id) VALUES (10, 1)")
    cursor.execute("CREATE TABLE estimate_materials (task_id INTEGER, price REAL, quantity REAL)")
    cursor.execute("INSERT INTO estimate_materials VALUES (10, 50.0, 2.0)") # 100
    cursor.execute("CREATE TABLE estimate_labor (task_id INTEGER, rate REAL, hours REAL)")
    cursor.execute("INSERT INTO estimate_labor VALUES (10, 20.0, 5.0)") # 100
    conn.commit()
    conn.close()
    
    # 2. PBOQ DB
    pboq_db = os.path.join(pboq_dir, "BOQ1.db")
    conn = sqlite3.connect(pboq_db)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE pboq_items (Sheet TEXT, Description TEXT, Qty REAL, [Bill Amount] REAL, PlugRate REAL, PlugCode TEXT)")
    cursor.execute("INSERT INTO pboq_items VALUES ('S1', 'Item 1', 1.0, 300.0, 200.0, 'R1')")
    conn.commit()
    conn.close()
    
    return project_dir

def run_verification():
    print("Starting Analytics Verification...")
    temp_dir = "temp_verify"
    os.makedirs(temp_dir, exist_ok=True)
    project_path = setup_test_project(temp_dir)
    
    with patch.object(FinancialExecutiveAnalytic, '_init_ui'):
        analytic = FinancialExecutiveAnalytic(project_path)
        analytic.refresh_data()
        
        print(f"Detected Currency: {analytic.currency_symbol}")
        
        # Verify Bid Value
        bid_call = analytic.card_total_bid.update_value.call_args[0][0]
        print(f"Total Bid Card: {bid_call}")
        if "300.00" in bid_call:
            print("PASS: Bid aggregation correct.")
        else:
            print("FAIL: Bid aggregation incorrect.")
            
        # Verify Resource Distribution
        donut_data = analytic.donut_chart.set_data.call_args[0][0]
        print(f"Donut Data: {donut_data}")
        mat_val = next(v for l, v, c in donut_data if l == "Materials")
        lab_val = next(v for l, v, c in donut_data if l == "Labor")
        
        if mat_val == 100.0 and lab_val == 100.0:
            print("PASS: Resource drill-down correct.")
        else:
            print("FAIL: Resource drill-down incorrect.")

if __name__ == "__main__":
    run_verification()
