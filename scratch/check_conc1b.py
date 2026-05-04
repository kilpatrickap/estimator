import sqlite3

db_path = r"C:\Users\Consar-Kilpatrick\Desktop\Atlantic Catering School\Project Database\Atlantic Catering School.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

est_id = 9 # CONC1B
print(f"Checking Resources for Estimate ID {est_id} (CONC1B):")

# Materials
cursor.execute("SELECT name, price, quantity FROM estimate_materials WHERE task_id IN (SELECT id FROM tasks WHERE estimate_id=?)", (est_id,))
print("\nMaterials:")
for r in cursor.fetchall():
    print(r)

# Labor
cursor.execute("SELECT name_trade, rate, hours FROM estimate_labor WHERE task_id IN (SELECT id FROM tasks WHERE estimate_id=?)", (est_id,))
print("\nLabor:")
for r in cursor.fetchall():
    print(r)

# Plant
cursor.execute("SELECT name_trade, rate, hours FROM estimate_plant WHERE task_id IN (SELECT id FROM tasks WHERE estimate_id=?)", (est_id,))
print("\nPlant:")
for r in cursor.fetchall():
    print(r)

conn.close()
