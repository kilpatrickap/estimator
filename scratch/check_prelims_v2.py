import sqlite3

db_path = r"C:\Users\Consar-Kilpatrick\Desktop\Atlantic Catering School\Priced BOQs\PBOQ_Atlantic BOQ_21Apr26.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get all unique sheet names
cursor.execute("SELECT DISTINCT Sheet FROM pboq_items")
print("Sheets:", cursor.fetchall())

# Get items from the prelim sheet
cursor.execute("SELECT Description, [Bill Amount], RateCode, [Rate Code] FROM pboq_items WHERE Sheet LIKE '%prelim%' AND Description IS NOT NULL")
rows = cursor.fetchall()
print("\nPrelim Items (Description exists):")
for r in rows:
    print(r)

conn.close()
