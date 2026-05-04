import sqlite3
import os

project_dir = r"C:\Users\Consar-Kilpatrick\Desktop\Atlantic Catering School"
pboq_folder = os.path.join(project_dir, "Priced BOQs")

for f in os.listdir(pboq_folder):
    if not f.lower().endswith('.db'): continue
    db_path = os.path.join(pboq_folder, f)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Search for anything with "water" in description
    cursor.execute("SELECT * FROM pboq_items WHERE [Column 2] LIKE '%water%' OR [Description] LIKE '%water%'")
    rows = cursor.fetchall()
    if rows:
        print(f"File: {f}")
        for r in rows:
            print(r)
    conn.close()
