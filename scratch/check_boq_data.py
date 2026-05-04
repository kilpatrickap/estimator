import sqlite3

db_path = r"C:\Users\Consar-Kilpatrick\Desktop\Atlantic Catering School\Priced BOQs\PBOQ_Atlantic BOQ_21Apr26.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("PRAGMA table_info(pboq_items)")
cols = [c[1] for c in cursor.fetchall()]
print("Columns:", cols)

# Check a few rows
cursor.execute("SELECT Description, Qty, [Bill Amount], GrossRate, PlugRate, [Rate Code], PlugCode FROM pboq_items WHERE [Bill Amount] > 0 LIMIT 20")
rows = cursor.fetchall()
print("\nSample Rows:")
for r in rows:
    print(r)

conn.close()
