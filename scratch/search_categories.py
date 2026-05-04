import sqlite3

db_path = r"C:\Users\Consar-Kilpatrick\Desktop\Atlantic Catering School\Project Database\Atlantic Catering School.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("All unique categories in estimates:")
cursor.execute("SELECT DISTINCT category FROM estimates")
print(cursor.fetchall())

print("\nAll unique categories in tasks:")
try:
    cursor.execute("SELECT DISTINCT category FROM tasks")
    print(cursor.fetchall())
except:
    print("No category column in tasks.")

print("\nSearching for 'prelim' in any category column...")
cursor.execute("SELECT rate_code, category FROM estimates WHERE category IS NOT NULL")
for r in cursor.fetchall():
    if "prelim" in r[1].lower():
        print(f"Estimate Category: {r}")

conn.close()
