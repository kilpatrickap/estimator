import sqlite3
import os

db_path = 'C:/Users/Consar-Kilpatrick/Desktop/Two/Two/Project Database/Two.db'
if os.path.exists(db_path):
    db=sqlite3.connect(db_path)
    res = db.execute('SELECT sql FROM sqlite_master WHERE type="table" AND name="pboq_items"').fetchone()
    if res:
        print(res[0])
    else:
        print("Table pboq_items not found.")
else:
    print("DB missing.")
