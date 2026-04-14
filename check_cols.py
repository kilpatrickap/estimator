import sqlite3
import os

db_dir = 'C:/Users/Consar-Kilpatrick/Desktop/Two/Two/Project Database'
if os.path.exists(db_dir):
    for f in os.listdir(db_dir):
        if f.endswith('.db'):
            db_path = os.path.join(db_dir, f)
            print(f"--- DB: {f} ---")
            try:
                conn = sqlite3.connect(db_path)
                c = conn.cursor()
                c.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = c.fetchall()
                print("Tables:", [t[0] for t in tables])
                if ('pboq_items',) in tables:
                    c.execute("PRAGMA table_info(pboq_items)")
                    cols = [col[1] for col in c.fetchall()]
                    print("pboq_items cols:", cols)
                conn.close()
            except Exception as e:
                print("Err:", e)
