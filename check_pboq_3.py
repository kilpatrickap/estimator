import sqlite3
import os

db_path = r"C:\Users\Consar-Kilpatrick\Desktop\Two\Two\Priced BOQs\PBOQ_Three.db"
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    print("Tables:", cursor.fetchall())
    
    # Check pboq_items schema
    cursor.execute("PRAGMA table_info(pboq_items);")
    cols = cursor.fetchall()
    print("\npboq_items columns:")
    for c in cols:
        print(c)
        
    # Check data for PR-ETWK1A
    print("\nData for PR-ETWK1A:")
    cursor.execute("SELECT RateCode, PlugCode, PlugRate FROM pboq_items WHERE PlugCode = 'PR-ETWK1A';")
    print(cursor.fetchall())
    
    conn.close()
else:
    print("DB not found at", db_path)
