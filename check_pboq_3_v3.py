import sqlite3
import os

db_path = r"C:\Users\Consar-Kilpatrick\Desktop\Two\Two\Priced BOQs\PBOQ_Three.db"
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(pboq_items);")
    cols = [c[1] for c in cursor.fetchall()]
    
    cursor.execute("SELECT * FROM pboq_items WHERE PlugCode = 'PR-ETWK1A' OR PlugCode = 'PR-PRLM1A';")
    rows = cursor.fetchall()
    
    for r in rows:
        d = dict(zip(cols, r))
        print(f"PlugCode: {d.get('PlugCode')} | Desc: {d.get('Description')} | Col2: {d.get('Column 2')} | Col3: {d.get('Column 3')}")
        
    conn.close()
