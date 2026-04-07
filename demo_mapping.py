import sqlite3
import os

db_path = r"C:\Users\Consar-Kilpatrick\Desktop\Two\Two\Priced BOQs\PBOQ_Two.db"

def simulate_mapping():
    if not os.path.exists(db_path):
        print(f"File not found: {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(pboq_items)")
    db_columns = [info[1] for info in cursor.fetchall()]
    conn.close()

    # The viewer uses db_columns[1:] as the display columns
    display_col_names = db_columns[1:]
    
    # This is the "Smart Detection" logic I added to pboq_tools.py
    smart_map_targets = {
        'rate': "GrossRate",
        'rate_code': "RateCode",
        'plug_rate': "PlugRate",
        'plug_code': "PlugCode",
        'prov_sum': "ProvSum",
        'prov_sum_code': "ProvSumCode",
        'pc_sum': "PCSum",
        'pc_sum_code': "PCSumCode",
        'daywork': "Daywork",
        'daywork_code': "DayworkCode",
        'sub_package': "SubbeePackage",
        'sub_name': "SubbeeName",
        'sub_rate': "SubbeeRate",
        'sub_markup': "SubbeeMarkup",
        'sub_category': "SubbeeCategory",
        'sub_code': "SubbeeCode"
    }

    mappings = {}
    
    # Simulate findText logic
    for role, db_name in smart_map_targets.items():
        if db_name in display_col_names:
            idx = display_col_names.index(db_name)
            mappings[role] = idx
        else:
            mappings[role] = -1

    # Print Results
    print(f"Total Columns in DB: {len(db_columns)}")
    print(f"Total Displayed Columns: {len(display_col_names)}")
    print("-" * 40)
    print(f"{'Pricing Role':<20} | {'Found at Index':<15} | {'DB Column Name'}")
    print("-" * 40)
    
    for role, idx in mappings.items():
        col_name = display_col_names[idx] if idx >= 0 else "NOT FOUND"
        print(f"{role:<20} | {idx:<15} | {col_name}")

simulate_mapping()
