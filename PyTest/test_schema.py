import sqlite3
import pytest
import sys
import os

# Add parent directory to path so it can find pboq_logic
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from pboq_logic import PBOQLogic

def test_ensure_schema_new_db():
    # Setup an in-memory DB
    conn = sqlite3.connect(":memory:")
    
    # Call the refactored method
    success, db_cols = PBOQLogic.ensure_schema(conn)
    
    assert success is True
    
    # Assert RateCode exists, but "Rate Code" does NOT
    assert "RateCode" in db_cols
    assert "Rate Code" not in db_cols
    
    # Assert Column 0 to Column 3 exist
    for i in range(4):
        assert f"Column {i}" in db_cols
        
    # Assert Column 4 and above do NOT exist
    assert "Column 4" not in db_cols
    assert "Column 19" not in db_cols
    
    conn.close()

def test_pboq_items_table_structure():
    conn = sqlite3.connect(":memory:")
    PBOQLogic.ensure_schema(conn)
    
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(pboq_items)")
    cols = [info[1] for info in cursor.fetchall()]
    
    assert "RateCode" in cols
    assert "Rate Code" not in cols
    
    conn.close()
