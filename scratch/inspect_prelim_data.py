import sqlite3

db_path = r"C:\Users\Consar-Kilpatrick\Desktop\Atlantic Catering School\Priced BOQs\PBOQ_Atlantic BOQ_21Apr26.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("SELECT * FROM pboq_items WHERE Sheet='bill nr 1 prelims-THREE' AND [Bill Amount] != '' LIMIT 20")
rows = cursor.fetchall()
print("Prelim Rows with Bill Amount:")
for r in rows:
    print(r)

conn.close()
