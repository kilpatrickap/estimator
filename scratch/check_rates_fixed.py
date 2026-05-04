import sqlite3

db_path = r"C:\Users\Consar-Kilpatrick\Desktop\Atlantic Catering School\Priced BOQs\PBOQ_Atlantic BOQ_21Apr26.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get some rows that have something in Bill Amount
cursor.execute("SELECT Description, [Bill Amount], GrossRate, RateCode, PlugRate, PlugCode, [Rate Code] FROM pboq_items WHERE [Bill Amount] IS NOT NULL AND [Bill Amount] != '' LIMIT 50")
rows = cursor.fetchall()
print("Extended comparison (fixed query):")
for r in rows:
    print(r)

conn.close()
