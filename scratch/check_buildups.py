import sqlite3

db_path = r"C:\Users\Consar-Kilpatrick\Desktop\Atlantic Catering School\Project Database\Atlantic Catering School.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get estimates that have tasks
cursor.execute("""
    SELECT e.rate_code, e.id, COUNT(t.id) 
    FROM estimates e
    JOIN tasks t ON e.id = t.estimate_id
    GROUP BY e.id
    LIMIT 10
""")
rows = cursor.fetchall()
print("Estimates with tasks:")
for r in rows:
    print(r)
    est_id = r[1]
    # Check resources for this estimate
    cursor.execute("SELECT COUNT(*) FROM estimate_materials WHERE task_id IN (SELECT id FROM tasks WHERE estimate_id=?)", (est_id,))
    m = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM estimate_labor WHERE task_id IN (SELECT id FROM tasks WHERE estimate_id=?)", (est_id,))
    l = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM estimate_plant WHERE task_id IN (SELECT id FROM tasks WHERE estimate_id=?)", (est_id,))
    p = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM estimate_equipment WHERE task_id IN (SELECT id FROM tasks WHERE estimate_id=?)", (est_id,))
    q = cursor.fetchone()[0]
    print(f"  Materials: {m}, Labor: {l}, Plant: {p}, Equip: {q}")

conn.close()
