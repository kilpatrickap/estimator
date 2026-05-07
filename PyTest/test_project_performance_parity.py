import sqlite3
import os
import pytest

# Paths
PROJECT_DIR = r"C:\Users\Consar-Kilpatrick\Desktop\Atlantic Catering School"
DB_PATH = os.path.join(PROJECT_DIR, "Priced BOQs", "PBOQ_Atlantic BOQ_21Apr26.db")

def test_pricing_mix_parity():
    """Verifies that the pricing mix sums correctly and ignores 0.00 placeholders."""
    if not os.path.exists(DB_PATH):
        pytest.skip(f"Database not found at {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Replicate the logic from analytics_project_performance.py
    # 1. Detect columns
    cursor.execute("PRAGMA table_info(pboq_items)")
    cols = [info[1] for info in cursor.fetchall()]
    
    # Find bill amount column (typically Column 5 or Bill Amount)
    bill_amt_col = next((c for c in cols if c in ["Bill Amount", "BillAmount", "Column 5"]), None)
    assert bill_amt_col is not None, "Bill Amount column not found"
    
    # Sanitization string (same as in code)
    sani = f"REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(IFNULL([^{bill_amt_col}], '0'), ',', ''), ' ', ''), 'GH¢', ''), 'GHC', ''), 'GHS', ''), '¢', ''), '₵', ''), '$', '')"
    # Note: SQLite uses [] or "" for escaping. In the script I'll use "" to match.
    sani = sani.replace(f"[^{bill_amt_col}]", f'"{bill_amt_col}"')

    # Item Filter (Simplified but representative of the logic)
    # The real logic uses desc_col, unit_col, qty_col.
    # In Atlantic database: Column 1 is Desc, Column 2 is Unit, Column 3 is Qty.
    item_clause = "(TRIM(\"Column 1\") != '' AND \"Column 1\" IS NOT NULL AND LOWER(\"Column 1\") NOT LIKE '%collection%' AND LOWER(\"Column 1\") NOT LIKE '%summary%')"

    # Query for individual sources
    query = f"""
        SELECT 
            SUM(CASE WHEN CAST(REPLACE(REPLACE(REPLACE(IFNULL(GrossRate, '0'), ',', ''), ' ', ''), '$', '') AS REAL) > 0 THEN CAST({sani} AS REAL) ELSE 0 END),
            SUM(CASE WHEN CAST(REPLACE(REPLACE(REPLACE(IFNULL(PlugRate, '0'), ',', ''), ' ', ''), '$', '') AS REAL) > 0 THEN CAST({sani} AS REAL) ELSE 0 END),
            SUM(CASE WHEN CAST(REPLACE(REPLACE(REPLACE(IFNULL(SubbeeRate, '0'), ',', ''), ' ', ''), '$', '') AS REAL) > 0 THEN CAST({sani} AS REAL) ELSE 0 END),
            SUM(CASE WHEN CAST(REPLACE(REPLACE(REPLACE(IFNULL(ProvSum, '0'), ',', ''), ' ', ''), '$', '') AS REAL) > 0 THEN CAST({sani} AS REAL) ELSE 0 END),
            SUM(CASE WHEN CAST(REPLACE(REPLACE(REPLACE(IFNULL(PCSum, '0'), ',', ''), ' ', ''), '$', '') AS REAL) > 0 THEN CAST({sani} AS REAL) ELSE 0 END),
            SUM(CASE WHEN CAST(REPLACE(REPLACE(REPLACE(IFNULL(Daywork, '0'), ',', ''), ' ', ''), '$', '') AS REAL) > 0 THEN CAST({sani} AS REAL) ELSE 0 END)
        FROM pboq_items
        WHERE {item_clause}
    """
    
    cursor.execute(query)
    row = cursor.fetchone()
    sources = {
        'gross': row[0] or 0.0,
        'plug': row[1] or 0.0,
        'sub': row[2] or 0.0,
        'prov': row[3] or 0.0,
        'pc': row[4] or 0.0,
        'daywork': row[5] or 0.0
    }
    
    total_sources = sum(sources.values())
    
    # Query for Total Bid (only items considered 'priced')
    # A priced item must have at least one rate > 0
    priced_check = """(
        CAST(REPLACE(REPLACE(REPLACE(IFNULL(GrossRate, '0'), ',', ''), ' ', ''), '$', '') AS REAL) > 0 OR
        CAST(REPLACE(REPLACE(REPLACE(IFNULL(PlugRate, '0'), ',', ''), ' ', ''), '$', '') AS REAL) > 0 OR
        CAST(REPLACE(REPLACE(REPLACE(IFNULL(SubbeeRate, '0'), ',', ''), ' ', ''), '$', '') AS REAL) > 0 OR
        CAST(REPLACE(REPLACE(REPLACE(IFNULL(ProvSum, '0'), ',', ''), ' ', ''), '$', '') AS REAL) > 0 OR
        CAST(REPLACE(REPLACE(REPLACE(IFNULL(PCSum, '0'), ',', ''), ' ', ''), '$', '') AS REAL) > 0 OR
        CAST(REPLACE(REPLACE(REPLACE(IFNULL(Daywork, '0'), ',', ''), ' ', ''), '$', '') AS REAL) > 0
    )"""
    
    cursor.execute(f"SELECT SUM(CAST({sani} AS REAL)) FROM pboq_items WHERE {item_clause} AND {priced_check}")
    total_bid = cursor.fetchone()[0] or 0.0
    
    print(f"\nTotal Bid: {total_bid:,.2f}")
    print(f"Total Sources Sum: {total_sources:,.2f}")
    for k, v in sources.items():
        print(f" - {k}: {v:,.2f}")
        
    # Validation 1: Total sources should be close to total bid.
    # It might exceed slightly if an item is tagged with multiple rates (rare but possible).
    # But it definitely shouldn't be 5x the total bid as it was before.
    assert total_sources <= total_bid * 1.05, f"Sources sum ({total_sources}) significantly exceeds Total Bid ({total_bid})"
    assert total_sources >= total_bid * 0.95, f"Sources sum ({total_sources}) is significantly less than Total Bid ({total_bid})"

    # Validation 2: Ensure PlugRate=0.00 didn't cause inflation.
    # In the bug, PlugRate was ~750k. Now it should be much less or match the actual items.
    # From my inspection, PlugRate was '0.00' for most items.
    assert sources['plug'] < total_bid, "Plug Rates still seem inflated"
    
    conn.close()

if __name__ == "__main__":
    test_pricing_mix_parity()
