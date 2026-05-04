import sqlite3

db_path = r"C:\Users\Consar-Kilpatrick\Desktop\Atlantic Catering School\Project Database\Atlantic Catering School.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("Settings:")
cursor.execute("SELECT * FROM settings")
for r in cursor.fetchall():
    print(r)

# Check if there's a markups table
try:
    print("\nMarkups:")
    cursor.execute("SELECT * FROM markups")
    for r in cursor.fetchall():
        print(r)
except:
    print("\nNo markups table found.")

conn.close()
