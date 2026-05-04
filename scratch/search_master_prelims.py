import sqlite3

db_path = r"C:\Users\Consar-Kilpatrick\Desktop\Atlantic Catering School\Project Database\Atlantic Catering School.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("Estimates with 'prelim' in Rate Code or Sheet?")
cursor.execute("SELECT id, rate_code, net_total FROM estimates")
rows = cursor.fetchall()
for r in rows:
    if r[1] and "prelim" in r[1].lower():
        print(f"Found by Rate Code: {r}")

# Check tasks for prelim-like descriptions
cursor.execute("SELECT e.id, e.rate_code, t.name FROM estimates e JOIN tasks t ON e.id = t.estimate_id")
rows = cursor.fetchall()
for r in rows:
    if r[2] and "prelim" in r[2].lower():
        print(f"Found by Task Name: {r}")

conn.close()
