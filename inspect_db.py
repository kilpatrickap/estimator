import sqlite3
import os

db_path = "construction_rates.db"
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(estimates)")
    cols = cursor.fetchall()
    for col in cols:
        print(f"Column: {col[1]} ({col[2]})")
    conn.close()
else:
    print("Database not found")
