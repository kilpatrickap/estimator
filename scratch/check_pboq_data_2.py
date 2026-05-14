import sqlite3
import os

db_path = r'C:\Users\Consar-Kilpatrick\Desktop\test\test\Priced BOQs\PBOQ_APINTO BOQ BLANK BOQ.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Check values in "Bill Rate" column
cursor.execute('SELECT "Column 2", "Bill Rate" FROM pboq_items WHERE Sheet="MAIN BUILDING"')
rows = cursor.fetchall()
conn.close()

priceable = [r for r in rows if r[0] and str(r[0]).strip()]
priced = []
for r in priceable:
    try:
        val = float(str(r[1]).replace(',',''))
        if val > 0:
            priced.append(r)
    except: pass

dummy = [r for r in priced if float(str(r[1]).replace(',','')) == 0.1]

print(f"Total rows in Sheet: {len(rows)}")
print(f"Priceable items (has qty): {len(priceable)}")
print(f"Priced items (Bill Rate > 0): {len(priced)}")
print(f"Dummy items (Bill Rate == 0.1): {len(dummy)}")
if priced:
    print(f"Sample of priced: {priced[:5]}")
