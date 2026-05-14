import sqlite3
import os

db_path = r'C:\Users\Consar-Kilpatrick\Desktop\test\test\Priced BOQs\PBOQ_APINTO BOQ BLANK BOQ.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Check column names first to be sure
cursor.execute("PRAGMA table_info(pboq_items)")
cols = [info[1] for info in cursor.fetchall()]
print(f"Columns: {cols}")

# Based on previous output, qty is Column 2, bill_rate is Column 4
cursor.execute('SELECT "Column 2", "Column 4" FROM pboq_items WHERE Sheet="MAIN BUILDING"')
rows = cursor.fetchall()
conn.close()

# Filter out non-priceable items (empty qty)
priceable = [r for r in rows if r[0] and str(r[0]).strip()]
priced = [r for r in priceable if r[1] and str(r[1]).strip() and float(str(r[1]).replace(',','')) > 0]
dummy = [r for r in priced if float(str(r[1]).replace(',','')) == 0.1]

print(f"Total rows in Sheet: {len(rows)}")
print(f"Priceable items (has qty): {len(priceable)}")
print(f"Priced items (rate > 0): {len(priced)}")
print(f"Dummy items (rate == 0.1): {len(dummy)}")

# Sample of priced items that are NOT dummy
not_dummy = [r for r in priced if float(str(r[1]).replace(',','')) != 0.1]
print(f"Sample of non-dummy priced: {not_dummy[:5]}")
