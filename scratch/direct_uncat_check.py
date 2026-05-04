import sys
import os
import sqlite3

db_path = r"C:\Users\Consar-Kilpatrick\Desktop\Atlantic Catering School\Priced BOQs\PBOQ_Atlantic BOQ_21Apr26.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Column 35 (Index 35 is actually the 36th column)
# PRAGMA table_info to be sure
cursor.execute("PRAGMA table_info(pboq_items)")
cols = [info[1] for info in cursor.fetchall()]

# Index 35 is 36th column
b_col = cols[36] # 0-indexed info[0] is 35
d_col = cols[2]  # Index 1 is 2nd column
pc_col = cols[21] # Index 20? 

query = f"SELECT \"{d_col}\", \"{b_col}\", \"{cols[16]}\", \"{cols[18]}\", \"{cols[21]}\" FROM pboq_items"
cursor.execute(query)

uncat_sum = 0
print(f"{'Description':<60} | {'Bid':<12}")
print("-" * 75)

for row in cursor.fetchall():
    desc, b, r_code, p_code, p_cat = row
    if not desc or "summary" in desc.lower() or "collection" in desc.lower(): continue
    
    try:
        val = float(str(b).replace(',', '').strip())
    except:
        val = 0
    
    if val == 0: continue
    
    # Simple check for uncategorized
    if not p_cat and not r_code and not p_code:
         print(f"{desc[:60]:<60} | {val:>12,.2f}")
         uncat_sum += val

print(f"UNCATEGORIZED SUM: {uncat_sum:,.2f}")
conn.close()
