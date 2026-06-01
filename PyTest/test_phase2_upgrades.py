import os
import sys
import pytest
import sqlite3
import json
import shutil
import base64

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import DatabaseManager
import ai_tools
from ai_worker import AICopilotWorker

@pytest.fixture
def temp_project_dir(request):
    """Sets up a temporary, high-fidelity project directory structured for analytics scanning."""
    base_dir = os.path.abspath(os.path.dirname(__file__))
    test_name = request.node.name.replace("[", "_").replace("]", "_")
    proj_dir = os.path.join(base_dir, f"temp_test_project_phase2_{test_name}")
    
    # Clean up any remnants just in case
    if os.path.exists(proj_dir):
        try:
            shutil.rmtree(proj_dir)
        except Exception:
            pass
        
    os.makedirs(proj_dir, exist_ok=True)
    os.makedirs(os.path.join(proj_dir, "Project Database"), exist_ok=True)
    os.makedirs(os.path.join(proj_dir, "Priced BOQs"), exist_ok=True)
    os.makedirs(os.path.join(proj_dir, "PBOQ States"), exist_ok=True)
    
    # 1. Create and populate Project Database
    db_path = os.path.join(proj_dir, "Project Database", "project_test.db")
    from orm_models import Base
    from sqlalchemy import create_engine
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("INSERT INTO estimates (id, project_name, client_name, currency, rate_code, net_total, overhead_percent, profit_margin_percent) VALUES (1, 'Phase 2 Unique High-Fidelity Test Est Recipe Description', 'Test Client Inc.', 'GHS (₵)', 'R10', 250.0, 5.0, 10.0)")
    cursor.execute("INSERT INTO settings (key, value) VALUES ('overhead', '5.0')")
    cursor.execute("INSERT INTO settings (key, value) VALUES ('profit', '10.0')")
    cursor.execute("INSERT INTO tasks (id, estimate_id, description) VALUES (1, 1, 'Excavation & Earthworks')")
    cursor.execute("INSERT INTO estimate_materials (id, task_id, name, unit, quantity, price) VALUES (1, 1, 'Cement', 'bags', 100.0, 85.0)")
    cursor.execute("INSERT INTO estimate_labor (id, task_id, name_trade, unit, hours, rate) VALUES (1, 1, 'Mason', 'hr', 80.0, 25.0)")
    
    conn.commit()
    conn.close()
    engine.dispose()
    
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
    
    cursor_boq.execute("INSERT INTO pboq_items VALUES ('Sheet1', 'Concrete slab 1:2:4', 50.0, 150.0, 7500.0, 'Concrete Package', 'BuildCo Ltd', 140.0, 0, 'R10', 'm3')")
    cursor_boq.execute("INSERT INTO subcontractor_quotes VALUES ('Concrete Package', 'BuildCo Ltd', 1, 140.0)")
    cursor_boq.execute("INSERT INTO subcontractor_quotes VALUES ('Concrete Package', 'SubCon Inc', 1, 145.0)")
    
    conn_boq.commit()
    conn_boq.close()
    
    yield proj_dir
    
    # Cleanup after test runs
    import gc
    gc.collect()
    if os.path.exists(proj_dir):
        try:
            shutil.rmtree(proj_dir)
        except Exception as e:
            print(f"Error deleting temp folder: {e}")

def test_generate_report_tool(temp_project_dir):
    """Verifies that generate_report tool executes successfully via ai_tools."""
    res = ai_tools.generate_report(temp_project_dir)
    assert res["status"] == "success"
    assert "Executive_Project_Intelligence_Report.pdf" in res["file_path"]
    assert os.path.exists(res["file_path"])

def test_get_subcontractor_quotes_tool(temp_project_dir):
    """Verifies that get_subcontractor_quotes retrieves expected quotes."""
    quotes = ai_tools.get_subcontractor_quotes(temp_project_dir)
    assert len(quotes) == 2
    assert quotes[0]["package"] == "Concrete Package"
    assert quotes[0]["subcontractor"] == "BuildCo Ltd"
    # Total quoted = qty * rate = 50 * 140 = 7000
    assert quotes[0]["total_quoted"] == 7000.0

def test_run_what_if_scenario_tool(temp_project_dir):
    """Verifies that run_what_if_scenario models adjustments ephemerally."""
    # Before total net = 100 * 85 + 80 * 25 = 8500 + 2000 = 10500
    # Apply +10% to materials -> Cement price 85 * 1.1 = 93.5 -> Materials total = 9350 -> After net = 11350
    res = ai_tools.run_what_if_scenario(temp_project_dir, "materials", "Cement", "+10%")
    assert len(res["matched_items"]) == 1
    assert res["matched_items"][0]["name"] == "Cement"
    assert res["before"]["net_total"] == pytest.approx(10500.0)
    assert res["after"]["net_total"] == pytest.approx(11350.0)
    
    # Verify markup: overhead 5% -> 10500 * 0.05 = 525. profit 10% -> (10500 + 525) * 0.10 = 1102.5. Grand total = 12127.5
    assert res["before"]["grand_total"] == pytest.approx(12127.5)
    
    # Verify database remains unmodified (Cement still 85.0)
    db_path = os.path.join(temp_project_dir, "Project Database", "project_test.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT price FROM estimate_materials WHERE name='Cement'")
    assert cursor.fetchone()[0] == 85.0
    conn.close()

def test_recommend_composite_buildup_tool(temp_project_dir):
    """Verifies recommend_composite_buildup successfully finds and parses recipe matches."""
    res = ai_tools.recommend_composite_buildup("Unique High-Fidelity Test Est", "m3", temp_project_dir)
    assert res["matched_rate_code"] == "R10"
    assert res["description"] == "Phase 2 Unique High-Fidelity Test Est Recipe Description"
    assert len(res["materials"]) == 1
    assert res["materials"][0]["name"] == "Cement"
    assert res["materials"][0]["qty"] == 100.0
