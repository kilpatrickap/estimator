import sqlite3
import os

db_path = r"C:\Users\Consar-Kilpatrick\Desktop\Two\Two\Priced BOQs\PBOQ_Three.db"
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(pboq_items);")
    cols = [c[1] for c in cursor.fetchall()]
    
    cursor.execute("SELECT * FROM pboq_items WHERE PlugCode = 'PR-ETWK1A' LIMIT 1;")
    r = cursor.fetchone()
    if r:
        d = dict(zip(cols, r))
        for k, v in d.items():
            if v and str(v).strip():
                print(f"{k}: {v}")
    conn.close()
