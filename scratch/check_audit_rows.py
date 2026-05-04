import sqlite3

boq_path = r"C:\Users\Consar-Kilpatrick\Desktop\Atlantic Catering School\Priced BOQs\PBOQ_Atlantic BOQ_21Apr26.db"
conn = sqlite3.connect(boq_path)
cursor = conn.cursor()

# Get column names
cursor.execute("PRAGMA table_info(pboq_items)")
cols = [r[1] for r in cursor.fetchall()]

# Find indices for Description, Bill Amount, and some potential Qty column
cursor.execute(f"SELECT * FROM pboq_items WHERE [Column 6] != '' AND [Column 6] IS NOT NULL LIMIT 20")
rows = cursor.fetchall()

print("Rows in Column 6 (Bill Amount):")
for r in rows:
    print(f"Desc: {r[2]} | Qty: {r[3]} | Unit: {r[4]} | Bill: {r[6]} | Code: {r[16]}")

conn.close()
