import sqlite3

db_path = r"C:\Users\Consar-Kilpatrick\Desktop\Atlantic Catering School\Project Database\Atlantic Catering School.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
print("Tables:", [r[0] for r in cursor.fetchall()])

# Check pboq_items table info too (just in case)
# Wait, pboq_items is in the priced BOQ db.
conn.close()

pboq_path = r"C:\Users\Consar-Kilpatrick\Desktop\Atlantic Catering School\Priced BOQs\PBOQ_Atlantic BOQ_21Apr26.db"
conn_p = sqlite3.connect(pboq_path)
cursor_p = conn_p.cursor()
cursor_p.execute("PRAGMA table_info(pboq_items)")
print("\nPBOQ Columns:")
for r in cursor_p.fetchall():
    print(r)
conn_p.close()
