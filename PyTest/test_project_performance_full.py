import sqlite3
import os
import pytest

# Paths
PROJECT_DIR = r"C:\Users\Consar-Kilpatrick\Desktop\Atlantic Catering School"
PBOQ_FOLDER = os.path.join(PROJECT_DIR, "Priced BOQs")

def test_full_project_analytics_parity():
    """Verifies analytics parity across all project databases."""
    if not os.path.exists(PBOQ_FOLDER):
        pytest.skip(f"PBOQ folder not found at {PBOQ_FOLDER}")

    total_bid_all = 0.0
    sources_all = {
        'gross': 0.0, 'plug': 0.0, 'sub': 0.0, 'prov': 0.0, 'pc': 0.0, 'daywork': 0.0
    }

    db_files = [f for f in os.listdir(PBOQ_FOLDER) if f.lower().endswith('.db')]
    
    for f in db_files:
        db_path = os.path.join(PBOQ_FOLDER, f)
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("PRAGMA table_info(pboq_items)")
        cols = [info[1] for info in cursor.fetchall()]
        bill_amt_col = next((c for c in cols if c in ["Bill Amount", "BillAmount", "Column 5"]), None)
        if not bill_amt_col:
            conn.close()
            continue
            
        sani = f"REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(IFNULL(\"{bill_amt_col}\", '0'), ',', ''), ' ', ''), 'GH¢', ''), 'GHC', ''), 'GHS', ''), '¢', ''), '₵', ''), '$', '')"

        # Broad item filter
        item_clause = "(TRIM(\"Column 1\") != '' AND \"Column 1\" IS NOT NULL AND LOWER(\"Column 1\") NOT LIKE '%collection%' AND LOWER(\"Column 1\") NOT LIKE '%summary%')"
        
        query_sources = f"""
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
        cursor.execute(query_sources)
        row = cursor.fetchone()
        sources_all['gross'] += row[0] or 0.0
        sources_all['plug'] += row[1] or 0.0
        sources_all['sub'] += row[2] or 0.0
        sources_all['prov'] += row[3] or 0.0
        sources_all['pc'] += row[4] or 0.0
        sources_all['daywork'] += row[5] or 0.0
        
        priced_check = """(
            CAST(REPLACE(REPLACE(REPLACE(IFNULL(GrossRate, '0'), ',', ''), ' ', ''), '$', '') AS REAL) > 0 OR
            CAST(REPLACE(REPLACE(REPLACE(IFNULL(PlugRate, '0'), ',', ''), ' ', ''), '$', '') AS REAL) > 0 OR
            CAST(REPLACE(REPLACE(REPLACE(IFNULL(SubbeeRate, '0'), ',', ''), ' ', ''), '$', '') AS REAL) > 0 OR
            CAST(REPLACE(REPLACE(REPLACE(IFNULL(ProvSum, '0'), ',', ''), ' ', ''), '$', '') AS REAL) > 0 OR
            CAST(REPLACE(REPLACE(REPLACE(IFNULL(PCSum, '0'), ',', ''), ' ', ''), '$', '') AS REAL) > 0 OR
            CAST(REPLACE(REPLACE(REPLACE(IFNULL(Daywork, '0'), ',', ''), ' ', ''), '$', '') AS REAL) > 0
        )"""
        
        cursor.execute(f"SELECT SUM(CAST({sani} AS REAL)) FROM pboq_items WHERE {item_clause} AND {priced_check}")
        total_bid_all += cursor.fetchone()[0] or 0.0
        conn.close()

    total_sources = sum(sources_all.values())
    
    print(f"\nProject Total Bid: {total_bid_all:,.2f}")
    print(f"Project Sources Sum: {total_sources:,.2f}")
    for k, v in sources_all.items():
        print(f" - {k}: {v:,.2f}")

    # The sum of sources should exactly equal the total bid if each item has exactly one source.
    # If some items have zero sources (unpriced), they aren't in either.
    # If some have multiple, sources sum will be higher.
    assert total_sources >= total_bid_all * 0.99, "Sources sum is significantly less than total bid"
    assert total_sources <= total_bid_all * 1.01, "Sources sum significantly exceeds total bid (double counting likely)"

if __name__ == "__main__":
    test_full_project_analytics_parity()
