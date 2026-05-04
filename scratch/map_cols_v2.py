import sqlite3

boq_path = r"C:\Users\Consar-Kilpatrick\Desktop\Atlantic Catering School\Priced BOQs\PBOQ_Atlantic BOQ_21Apr26.db"
conn = sqlite3.connect(boq_path)
cursor = conn.cursor()

cursor.execute("PRAGMA table_info(pboq_items)")
cols = [r[1] for r in cursor.fetchall()]

# Find indices for Description, Bill Amount, and some potential Qty column
cursor.execute(f"SELECT * FROM pboq_items WHERE [Bill Amount] != '' AND [Bill Amount] != '0.00' LIMIT 5")
rows = cursor.fetchall()

if rows:
    row = rows[0]
    print("Example Row Data:")
    for i, col in enumerate(cols):
        print(f"Index {i}: {col} -> {row[i]}")
else:
    print("No rows with bill amount found.")

conn.close()
