import os
import sys
import pytest
import sqlite3
import json
import shutil

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from report_generator import ExecutiveAnalyticsReportGenerator

@pytest.fixture
def temp_project_dir():
    """Sets up a temporary, high-fidelity project directory structured for analytics scanning."""
    base_dir = os.path.abspath(os.path.dirname(__file__))
    proj_dir = os.path.join(base_dir, "temp_test_project_rep")
    
    # Clean up any remnants just in case
    if os.path.exists(proj_dir):
        shutil.rmtree(proj_dir)
        
    os.makedirs(proj_dir)
    os.makedirs(os.path.join(proj_dir, "Project Database"))
    os.makedirs(os.path.join(proj_dir, "Priced BOQs"))
    os.makedirs(os.path.join(proj_dir, "PBOQ States"))
    
    # 1. Create and populate Project Database
    db_path = os.path.join(proj_dir, "Project Database", "project_test.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE estimates (
            id INTEGER PRIMARY KEY,
            project_name TEXT,
            client_name TEXT,
            currency TEXT,
            rate_code TEXT,
            net_total REAL
        )
    """)
    cursor.execute("""
        CREATE TABLE settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE tasks (
            id INTEGER PRIMARY KEY,
            estimate_id INTEGER,
            description TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE estimate_materials (
            id INTEGER PRIMARY KEY,
            task_id INTEGER,
            name TEXT,
            unit TEXT,
            quantity REAL,
            price REAL
        )
    """)
    cursor.execute("""
        CREATE TABLE estimate_labor (
            id INTEGER PRIMARY KEY,
            task_id INTEGER,
            name_trade TEXT,
            unit TEXT,
            hours REAL,
            rate REAL
        )
    """)
    
    cursor.execute("INSERT INTO estimates VALUES (1, 'Catering School Block', 'Atlantic Catering School Inc.', 'GHS (₵)', 'R10', 250.0)")
    cursor.execute("INSERT INTO settings VALUES ('overhead', '5.0')")
    cursor.execute("INSERT INTO settings VALUES ('profit', '10.0')")
    cursor.execute("INSERT INTO tasks VALUES (1, 1, 'Excavation & Earthworks')")
    cursor.execute("INSERT INTO estimate_materials VALUES (1, 1, 'Cement', 'bags', 100.0, 85.0)")
    cursor.execute("INSERT INTO estimate_labor VALUES (1, 1, 'Mason', 'hr', 80.0, 25.0)")
    
    conn.commit()
    conn.close()
    
    # 2. Create and populate Priced BOQs
    boq_path = os.path.join(proj_dir, "Priced BOQs", "boq1.db")
    conn_boq = sqlite3.connect(boq_path)
    cursor_boq = conn_boq.cursor()
    
    cursor_boq.execute("""
        CREATE TABLE pboq_items (
            sheet TEXT,
            description TEXT,
            quantity REAL,
            bill_rate REAL,
            bill_amount REAL,
            sub_package TEXT,
            sub_name TEXT,
            sub_rate REAL,
            isflagged INTEGER,
            rate_code TEXT,
            unit TEXT
        )
    """)
    cursor_boq.execute("""
        CREATE TABLE subcontractor_quotes (
            package_name TEXT,
            subcontractor_name TEXT,
            row_idx INTEGER,
            rate REAL
        )
    """)
    
    # Add dummy priced items to cover gross rates, plug rates, subs, etc.
    cursor_boq.execute("INSERT INTO pboq_items VALUES ('Sheet1', 'Concrete slab 1:2:4', 50.0, 150.0, 7500.0, 'Concrete Package', 'BuildCo Ltd', 140.0, 0, 'R10', 'm3')")
    cursor_boq.execute("INSERT INTO subcontractor_quotes VALUES ('Concrete Package', 'BuildCo Ltd', 1, 140.0)")
    cursor_boq.execute("INSERT INTO subcontractor_quotes VALUES ('Concrete Package', 'SubCon Inc', 1, 145.0)")
    
    conn_boq.commit()
    conn_boq.close()
    
    # 3. Create PBOQ States json files
    state_json_path = os.path.join(proj_dir, "PBOQ States", "boq1.db.json")
    mappings = {
        "mappings": {
            "desc": 0,
            "qty": 1,
            "bill_rate": 2,
            "bill_amount": 3,
            "sub_package": 4,
            "sub_name": 5,
            "sub_rate": 6,
            "isflagged": 7,
            "rate_code": 8,
            "unit": 9
        },
        "dummy_rate": 0.1
    }
    with open(state_json_path, 'w') as f:
        json.dump(mappings, f)
        
    parametric_json_path = os.path.join(proj_dir, "PBOQ States", "parametric_state.json")
    parametric_state = {
        "gfa": 250.0,
        "building_type_idx": 1,
        "region_idx": 0,
        "spec_idx": 1,
        "complexity_idx": 1,
        "site_conditions_idx": 0,
        "wet_areas": 3
    }
    with open(parametric_json_path, 'w') as f:
        json.dump(parametric_state, f)
        
    yield proj_dir
    
    # Cleanup after test runs
    if os.path.exists(proj_dir):
        try:
            shutil.rmtree(proj_dir)
        except Exception as e:
            print(f"Error deleting temp folder: {e}")

def test_executive_analytics_pdf_generation(temp_project_dir):
    """Verifies that ExecutiveAnalyticsReportGenerator parses databases successfully and compiles PDF report."""
    output_pdf_path = os.path.join(temp_project_dir, "Test_Executive_Analytics_Report.pdf")
    
    generator = ExecutiveAnalyticsReportGenerator(temp_project_dir)
    
    # 1. Test data gathering
    meta = generator._get_project_meta()
    assert meta['project_name'] == 'Catering School Block'
    assert meta['client_name'] == 'Atlantic Catering School Inc.'
    assert meta['currency_symbol'] == '₵'
    assert meta['overhead_rate'] == 5.0
    assert meta['profit_rate'] == 10.0
    
    data = generator._gather_analytics_data(meta)
    assert data['total_items'] == 1
    assert data['priced_items'] == 1
    assert data['flagged_items'] == 0
    # Base net cost = 250.0 (from master rates db R10 key) * 50.0 = 12500.0
    assert data['total_net_cost'] == 12500.0
    # Combined markups = 15%. Bid value = 12500 * 1.15 = 14375
    assert data['total_bid_value'] == pytest.approx(14375.0)
    
    # Verify the dynamic Unit column extraction and mapping
    assert len(data['all_items_flat']) == 1
    assert data['all_items_flat'][0]['unit'] == 'm3'
    
    # 2. Test PDF compilation
    success = generator.generate_report(output_pdf_path)
    assert success is True, "PDF generation failed"
    assert os.path.exists(output_pdf_path), "Generated PDF file does not exist"
    assert os.path.getsize(output_pdf_path) > 0, "Generated PDF file is empty"
