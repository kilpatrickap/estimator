import sqlite3
import os

db_path = r"C:\Users\Consar-Kilpatrick\Desktop\Two\Two\Priced BOQs\PBOQ_Two.db"
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT SubbeeCategory FROM pboq_items;")
    rows = cursor.fetchall()
    print("SubbeeCategory values:")
    for row in rows:
        print(f"'{row[0]}'")
    conn.close()
else:
    print(f"File not found: {db_path}")
