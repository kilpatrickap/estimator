import sqlite3

db_path = r"C:\Users\Consar-Kilpatrick\Desktop\Atlantic Catering School\Priced BOQs\PBOQ_Atlantic BOQ_21Apr26.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("SELECT Description, [Bill Amount], RateCode, [Rate Code], PlugCode FROM pboq_items WHERE Sheet LIKE '%prelim%'")
rows = cursor.fetchall()
print("Prelim Items:")
for r in rows:
    print(r)

conn.close()
