import sqlite3
import os

project_dir = r"C:\Users\Consar-Kilpatrick\Desktop\Atlantic Catering School"
pboq_folder = os.path.join(project_dir, "Priced BOQs")

for f in os.listdir(pboq_folder):
    if not f.lower().endswith('.db'): continue
    db_path = os.path.join(pboq_folder, f)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM pboq_items LIMIT 5")
    rows = cursor.fetchall()
    print(f"File: {f}")
    for r in rows:
        # Print first 25 columns to see where the data is
        print(r[:25])
    conn.close()
