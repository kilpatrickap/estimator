import sqlite3
import os

db_path = r"C:\Users\Consar-Kilpatrick\Desktop\Two\Two\Priced BOQs\PBOQ_Two.db"
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM pboq_items WHERE SubbeeCategory LIKE 'GHS%'")
    count = cursor.fetchone()[0]
    print(f"Contaminated items count: {count}")
    
    # Optional: Preview first 5 items to fix
    cursor.execute("SELECT SubbeeCategory FROM pboq_items WHERE SubbeeCategory LIKE 'GHS%' LIMIT 5")
    rows = cursor.fetchall()
    for row in rows:
        print(f"'{row[0]}'")
    
    conn.close()
else:
    print(f"File not found: {db_path}")
