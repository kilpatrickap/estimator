
import os
import sqlite3
import json
import pytest
import re
import shutil
from margin_migrator_dialog import MarginMigrationWorker
from pboq_logic import PBOQLogic

@pytest.fixture
def test_project(tmp_path):
    """Set up a mock project structure with a PBOQ database."""
    project_dir = tmp_path / "TestProject"
    project_dir.mkdir()
    
    pboq_dir = project_dir / "Priced BOQs"
    pboq_dir.mkdir()
    
    # Create PBOQ database
    db_path = pboq_dir / "PBOQ_Test.db"
    conn = sqlite3.connect(db_path)
    PBOQLogic.ensure_schema(conn)
    
    # Insert test data
    cursor = conn.cursor()
    # Row 1: Plug Rate with Formula
    cursor.execute("""
        INSERT INTO pboq_items (Sheet, PlugCode, PlugRate, PlugFormula, PlugFactor, "Column 0")
        VALUES ('Sheet1', 'P-FORMULA', '100.00', '=100', '1.0', 'Item 1')
    """)
    # Row 2: Plug Rate without Formula (Static)
    cursor.execute("""
        INSERT INTO pboq_items (Sheet, PlugCode, PlugRate, PlugFactor, "Column 0")
        VALUES ('Sheet1', 'P-STATIC', '200.00', '1.0', 'Item 2')
    """)
    conn.commit()
    conn.close()
    
    # Create PBOQ State for mappings
    states_dir = project_dir / "PBOQ States"
    states_dir.mkdir()
    state_file = states_dir / "PBOQ_Test.db.json"
    state_data = {
        "mappings": {
            "plug_rate": -1,
            "plug_code": -1,
            "rate_code": -1,
            "rate": -1,
            "bill_rate": -1,
            "bill_amount": 2,
            "qty": 1,
            "ref": 0
        }
    }
    with open(state_file, 'w') as f:
        json.dump(state_data, f)
        
    return project_dir, db_path

def test_plug_rates_updated_on_factor_change(test_project):
    """Verify that plug rates are updated when the adjustment factor changes."""
    project_dir, db_path = test_project
    
    # Initial state verification
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT PlugRate, PlugFactor FROM pboq_items WHERE PlugCode='P-FORMULA'")
    row1 = cursor.fetchone()
    assert row1[0] == '100.00'
    assert row1[1] == '1.0'
    
    cursor.execute("SELECT PlugRate, PlugFactor FROM pboq_items WHERE PlugCode='P-STATIC'")
    row2 = cursor.fetchone()
    assert row2[0] == '200.00'
    assert row2[1] == '1.0'
    conn.close()
    
    # Run Migration Worker
    # old_factor=1.0, new_factor=1.2 (20% increase)
    worker = MarginMigrationWorker(
        project_dir=str(project_dir),
        old_overhead=10.0,
        old_profit=5.0,
        new_overhead=10.0,
        new_profit=5.0,
        old_factor=1.0,
        new_factor=1.2
    )
    
    # We call the internal method directly to avoid thread overhead in test
    worker._migrate_pboq_gross_rates(scale_factor=1.2)
    
    # Verify results
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Row 1 (Formula-based): scaled_plug = base_sum (100) * new_factor (1.2) = 120.00
    cursor.execute("SELECT PlugRate, PlugFactor FROM pboq_items WHERE PlugCode='P-FORMULA'")
    row1_after = cursor.fetchone()
    assert row1_after[0] == '120.00'
    assert float(row1_after[1].replace(',', '')) == 1.2
    
    # Row 2 (Static-based): scaled_plug = numeric_val (200) * scale_factor (1.2) = 240.00
    cursor.execute("SELECT PlugRate, PlugFactor FROM pboq_items WHERE PlugCode='P-STATIC'")
    row2_after = cursor.fetchone()
    assert row2_after[0] == '240.00'
    assert float(row2_after[1].replace(',', '')) == 1.2
    
    conn.close()

def test_plug_rates_updated_on_factor_decrease(test_project):
    """Verify that plug rates are updated when the adjustment factor decreases."""
    project_dir, db_path = test_project
    
    # Run Migration Worker
    # old_factor=1.0, new_factor=0.5 (50% decrease)
    worker = MarginMigrationWorker(
        project_dir=str(project_dir),
        old_overhead=10.0,
        old_profit=5.0,
        new_overhead=10.0,
        new_profit=5.0,
        old_factor=1.0,
        new_factor=0.5
    )
    
    worker._migrate_pboq_gross_rates(scale_factor=0.5)
    
    # Verify results
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Row 1: 100 * 0.5 = 50.00
    cursor.execute("SELECT PlugRate, PlugFactor FROM pboq_items WHERE PlugCode='P-FORMULA'")
    row1_after = cursor.fetchone()
    assert row1_after[0] == '50.00'
    assert float(row1_after[1].replace(',', '')) == 0.5
    
    conn.close()

def test_plug_linked_bill_rate_updated(test_project):
    """Verify that Bill Rate and Bill Amount linked to Plug Rate are updated."""
    project_dir, db_path = test_project
    
    # Set up linking in database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    # PBOQLogic.ensure_schema already adds "Bill Rate" and "Bill Amount"
    cursor.execute("UPDATE pboq_items SET \"Bill Rate\" = '200.00', \"Bill Amount\" = '200.00', PlugRate = '200.00', PlugCode = 'P-LINKED' WHERE PlugCode = 'P-STATIC'")
    
    # Add formatting for linking (pboq_formatting already exists from ensure_schema)
    # purple color for linked plug: #f3e5f5
    cursor.execute("INSERT INTO pboq_formatting (row_idx, col_idx, fmt_json) VALUES (?, ?, ?)",
                   (1, 3, json.dumps({"bg_color": "#f3e5f5"}))) # Bill Rate linked to Plug
    cursor.execute("INSERT INTO pboq_formatting (row_idx, col_idx, fmt_json) VALUES (?, ?, ?)",
                   (1, 4, json.dumps({"bg_color": "#f3e5f5"}))) # Bill Amount linked to Plug
    conn.commit()
    conn.close()
    
    # Update mappings in state file
    states_dir = project_dir / "PBOQ States"
    state_file = states_dir / "PBOQ_Test.db.json"
    with open(state_file, 'r') as f:
        pst = json.load(f)
    pst['mappings']['bill_rate'] = 3
    pst['mappings']['bill_amount'] = 4
    with open(state_file, 'w') as f:
        json.dump(pst, f)
        
    # Run Migration (1.0 -> 1.5, 50% increase)
    worker = MarginMigrationWorker(
        project_dir=str(project_dir),
        old_overhead=10.0,
        old_profit=5.0,
        new_overhead=10.0,
        new_profit=5.0,
        old_factor=1.0,
        new_factor=1.5
    )
    worker._migrate_pboq_gross_rates(scale_factor=1.5)
    
    # Verify results
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT \"Bill Rate\", \"Bill Amount\", PlugRate FROM pboq_items WHERE PlugCode='P-LINKED'")
    row = cursor.fetchone()
    # 200 * 1.5 = 300
    assert row[2] == '300.00' # Plug Rate updated
    assert row[0] == '300.00' # Bill Rate updated (linked)
    assert row[1] == '300.00' # Bill Amount updated (linked)
    conn.close()

def test_custom_plug_factor_preserved(test_project):
    """Verify that custom PlugFactors are scaled proportionally, not overwritten."""
    project_dir, db_path = test_project
    
    # Set up custom factor (2.0) for Item 2
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    # P-STATIC is Row 2
    cursor.execute("UPDATE pboq_items SET PlugRate = '200.00', PlugFactor = '2.00' WHERE PlugCode = 'P-STATIC'")
    conn.commit()
    conn.close()
    
    # Run Migration (1.0 -> 1.5, 50% increase)
    worker = MarginMigrationWorker(
        project_dir=str(project_dir),
        old_overhead=10.0,
        old_profit=5.0,
        new_overhead=10.0,
        new_profit=5.0,
        old_factor=1.0,
        new_factor=1.5
    )
    worker._migrate_pboq_gross_rates(scale_factor=1.5)
    
    # Verify results
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT PlugRate, PlugFactor FROM pboq_items WHERE PlugCode='P-STATIC'")
    row = cursor.fetchone()
    # Original Rate: 200. Original Factor: 2.0.
    # Scale: 1.5.
    # New Rate: 200 * 1.5 = 300.
    # New Factor: 2.0 * 1.5 = 3.0.
    assert row[0] == '300.00'
    assert float(row[1].replace(',', '')) == 3.0
    conn.close()
