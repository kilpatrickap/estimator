import sqlite3

db_path = r"C:\Users\Consar-Kilpatrick\Desktop\Atlantic Catering School\Priced BOQs\PBOQ_Atlantic BOQ_21Apr26.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("SELECT Description, RateCode, [Rate Code] FROM pboq_items WHERE [Bill Amount] > 0 LIMIT 20")
rows = cursor.fetchall()
print("Rate Code comparison:")
for r in rows:
    print(r)

conn.close()
