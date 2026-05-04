import sqlite3
import os

project_dir = r"C:\Users\Consar-Kilpatrick\Desktop\Atlantic Catering School"
pboq_folder = os.path.join(project_dir, "Priced BOQs")

for f in os.listdir(pboq_folder):
    if not f.lower().endswith('.db'): continue
    db_path = os.path.join(pboq_folder, f)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Skip the header rows
    cursor.execute("SELECT * FROM pboq_items WHERE [Column 6] != '' AND [Column 6] IS NOT NULL LIMIT 20")
    rows = cursor.fetchall()
    print(f"File: {f}")
    for r in rows:
        print(f"Desc (idx 2): {r[2]} | Qty (idx 3): {r[3]} | Unit (idx 4): {r[4]} | Bill (idx 6): {r[6]} | Code (idx 16): {r[16]}")
    conn.close()
