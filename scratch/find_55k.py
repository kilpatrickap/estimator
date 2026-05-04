import sqlite3

db_path = r"C:\Users\Consar-Kilpatrick\Desktop\Atlantic Catering School\Priced BOQs\PBOQ_Atlantic BOQ_21Apr26.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("SELECT Sheet, Description, [Bill Amount] FROM pboq_items WHERE [Bill Amount] != '' AND [Bill Amount] IS NOT NULL")
rows = cursor.fetchall()
for r in rows:
    if "55,000" in str(r[2]):
        print(r)

conn.close()
