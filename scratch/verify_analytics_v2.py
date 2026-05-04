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
    project_dir = os.path.join(base_path, "TestProject_v2")
    if os.path.exists(project_dir):
        import shutil
        shutil.rmtree(project_dir)
    os.makedirs(project_dir, exist_ok=True)
    
    pj_db_dir = os.path.join(project_dir, "Project Database")
    os.makedirs(pj_db_dir, exist_ok=True)
    
    pboq_dir = os.path.join(project_dir, "Priced BOQs")
    os.makedirs(pboq_dir, exist_ok=True)
    
    # 1. Master DB with diverse buildups
    master_db = os.path.join(pj_db_dir, "Master.db")
    conn = sqlite3.connect(master_db)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE settings (key TEXT, value TEXT)")
    cursor.execute("INSERT INTO settings VALUES ('currency', 'GHS (₵)')")
    
    cursor.execute("CREATE TABLE estimates (id INTEGER PRIMARY KEY, rate_code TEXT, net_total REAL)")
    # R1: 50% Mat, 50% Lab
    cursor.execute("INSERT INTO estimates (id, rate_code, net_total) VALUES (1, 'R1', 200.0)")
    # R2: 100% Plant
    cursor.execute("INSERT INTO estimates (id, rate_code, net_total) VALUES (2, 'R2', 500.0)")
    
    cursor.execute("CREATE TABLE tasks (id INTEGER PRIMARY KEY, estimate_id INTEGER)")
    cursor.execute("CREATE TABLE estimate_materials (task_id INTEGER, price REAL, quantity REAL)")
    cursor.execute("CREATE TABLE estimate_labor (task_id INTEGER, rate REAL, hours REAL)")
    cursor.execute("CREATE TABLE estimate_equipment (task_id INTEGER, rate REAL, hours REAL)")
    cursor.execute("CREATE TABLE estimate_plant (task_id INTEGER, rate REAL, hours REAL)")
    cursor.execute("CREATE TABLE estimate_indirect_costs (task_id INTEGER, amount REAL)")
    cursor.execute("INSERT INTO tasks (id, estimate_id) VALUES (10, 1), (20, 2)")
    
    # R1: 50% Mat, 50% Lab
    cursor.execute("INSERT INTO estimate_materials (task_id, price, quantity) VALUES (10, 100.0, 1.0)")
    cursor.execute("INSERT INTO estimate_labor (task_id, rate, hours) VALUES (10, 100.0, 1.0)")
    
    # R2 Resources
    cursor.execute("INSERT INTO estimate_plant (task_id, rate, hours) VALUES (20, 500.0, 1.0)")
    
    # R3: Subcontractor in buildup
    cursor.execute("INSERT INTO estimates (id, rate_code, net_total) VALUES (3, 'R3', 1000.0)")
    cursor.execute("CREATE TABLE estimate_sub_rates (estimate_id INTEGER, quantity REAL)")
    cursor.execute("INSERT INTO estimate_sub_rates (estimate_id, quantity) VALUES (3, 1000.0)")
    
    conn.commit()
    conn.close()
    
    # 2. PBOQ DB
    pboq_db = os.path.join(pboq_dir, "BOQ_Complex.db")
    conn = sqlite3.connect(pboq_db)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE pboq_items (
            Sheet TEXT, Description TEXT, Column_2 TEXT, [Bill Amount] TEXT, 
            PlugRate TEXT, PlugCode TEXT, GrossRate TEXT, [Rate Code] TEXT
        )
    """)
    # Row 1: Plug R1 (1.0 Qty, 300 Bill, 200 Cost) -> 100 Mat, 100 Lab
    cursor.execute("INSERT INTO pboq_items VALUES ('S1', 'Item 1', '1.0', '300.0', '200.0', 'R1', '0', '')")
    # Row 2: Gross R2 (2.0 Qty, 1200 Bill, 1000 Cost) -> 1000 Plant
    cursor.execute("INSERT INTO pboq_items VALUES ('S1', 'Item 2', '2.0', '1200.0', '0', '', '500.0', 'R2')")
    # Row 3: Summary Item (SHOULD BE EXCLUDED)
    cursor.execute("INSERT INTO pboq_items VALUES ('S1', 'Subtotal Collection', '0', '1500.0', '0', '', '0', '')")
    # Row 4: Subbie R3 (1.0 Qty, 1500 Bill, 1000 Cost) -> 1000 Sub
    cursor.execute("INSERT INTO pboq_items VALUES ('S2', 'Item 3', '1.0', '1500.0', '1000.0', 'R3', '0', '')")
    
    conn.commit()
    conn.close()
    
    return project_dir

def run_verification():
    print("Starting Comprehensive Analytics Verification...")
    temp_dir = "temp_verify_v2"
    os.makedirs(temp_dir, exist_ok=True)
    project_path = setup_test_project(temp_dir)
    
    # We need to mock _to_float because it's used in refresh_data
    # But since we are testing the actual class, we'll just let it run.
    
    with patch.object(FinancialExecutiveAnalytic, '_init_ui'):
        analytic = FinancialExecutiveAnalytic(project_path)
        # Mock mappings to help detection
        analytic._get_pboq_mapping = MagicMock(return_value={'qty': 2, 'bill_amount': 3, 'desc': 1})
        
        analytic.refresh_data()
        
        # Verify Bid Value (Excluding Summary)
        # 300 + 1200 + 1500 = 3000. (The 1500 summary should be ignored)
        bid_call = analytic.card_total_bid.update_value.call_args[0][0]
        print(f"Total Bid Card: {bid_call}")
        if "3,000.00" in bid_call:
            print("PASS: Bid aggregation correctly excluded summary items.")
        else:
            print("FAIL: Bid aggregation incorrect.")
            
        # Verify Resource Distribution
        donut_data = analytic.donut_chart.set_data.call_args[0][0]
        print(f"Donut Data: {donut_data}")
        # Mat: 100 (from R1)
        # Lab: 100 (from R1)
        # Plant/Equip: 1000 (from R2)
        # Sub: 1000 (from R3)
        
        res = {l: v for l, v, c in donut_data}
        print(f"Aggregated Resources: {res}")
        
        if res.get('Materials') == 100.0 and res.get('Labor') == 100.0 and res.get('Plant/Equip') == 1000.0 and res.get('Sub-Contract') == 1000.0:
            print("PASS: Detailed resource breakdown from both Plug and Gross codes is correct.")
        else:
            print("FAIL: Resource breakdown incorrect.")

if __name__ == "__main__":
    run_verification()
