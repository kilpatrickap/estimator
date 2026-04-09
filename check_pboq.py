import sqlite3
import os

db_path = "construction_rates.db"
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pboq_items'")
    if cursor.fetchone():
        print("pboq_items table exists")
    else:
        print("pboq_items table does NOT exist")
    conn.close()
