import sqlite3

boq_path = r"C:\Users\Consar-Kilpatrick\Desktop\Atlantic Catering School\Priced BOQs\PBOQ_Atlantic BOQ_21Apr26.db"
conn = sqlite3.connect(boq_path)
cursor = conn.cursor()

# Get column names
cursor.execute("PRAGMA table_info(pboq_items)")
cols = [r[1] for r in cursor.fetchall()]

# Find indices for Description, Bill Amount, and some potential Qty column
d_idx = cols.index('Description')
b_idx = cols.index('Bill Amount')
r_idx = cols.index('RateCode')

# Let's see a few rows
cursor.execute(f"SELECT * FROM pboq_items WHERE [Bill Amount] != '' LIMIT 5")
rows = cursor.fetchall()

print("Column mapping investigation:")
for i, col in enumerate(cols):
    val = rows[0][i] if rows else "N/A"
    print(f"Index {i}: {col} -> {val}")

conn.close()
