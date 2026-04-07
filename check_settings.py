import sqlite3
import json

db_path = "construction_costs.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT value FROM settings WHERE key='category_prefixes'")
row = cursor.fetchone()
if row:
    print(f"category_prefixes: {row[0]}")
else:
    print("category_prefixes NOT FOUND")
conn.close()
