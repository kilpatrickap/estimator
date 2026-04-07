import sqlite3
import os

db_path = r"C:\Users\Consar-Kilpatrick\Desktop\Two\Two\Priced BOQs\PBOQ_Two.db"
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Identify items with currency-like strings in SubbeeCategory
    # Using 'GHS%' as a pattern based on our findings
    cursor.execute("SELECT rowid, SubbeeCategory FROM pboq_items WHERE SubbeeCategory LIKE 'GHS%'")
    rows = cursor.fetchall()
    
    if not rows:
        print("No contaminated items found.")
        conn.close()
        exit()
        
    print(f"Repairing {len(rows)} items...")
    
    # Update them to 'Miscellaneous'
    cursor.execute("UPDATE pboq_items SET SubbeeCategory = 'Miscellaneous' WHERE SubbeeCategory LIKE 'GHS%'")
    
    conn.commit()
    print("Repair complete.")
    conn.close()
else:
    print(f"File not found: {db_path}")
