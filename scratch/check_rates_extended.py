import sqlite3

db_path = r"C:\Users\Consar-Kilpatrick\Desktop\Atlantic Catering School\Priced BOQs\PBOQ_Atlantic BOQ_21Apr26.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("SELECT Description, [Bill Amount], GrossRate, RateCode, PlugRate, PlugCode, [Rate Code] FROM pboq_items WHERE [Bill Amount] > 0 AND Description NOT LIKE '%Collection%' AND Description NOT LIKE '%Summary%' LIMIT 50")
rows = cursor.fetchall()
print("Extended comparison:")
for r in rows:
    print(r)

conn.close()
