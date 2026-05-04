import sqlite3

db_path = r"C:\Users\Consar-Kilpatrick\Desktop\Atlantic Catering School\Project Database\Atlantic Catering School.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("SELECT rate_code, net_total FROM estimates WHERE rate_code IN ('CONC1A', 'CONC1B', 'ETWK1A')")
for r in cursor.fetchall():
    print(r)

conn.close()
