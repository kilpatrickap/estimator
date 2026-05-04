import sqlite3
import os

project_dir = r"C:\Users\Consar-Kilpatrick\Desktop\Atlantic Catering School"
pboq_folder = os.path.join(project_dir, "Priced BOQs")
master_path = r"C:\Users\Consar-Kilpatrick\Desktop\Atlantic Catering School\Project Database\Atlantic Catering School.db"

c_agg_bid = {}
c_agg_cost = {}

for f in os.listdir(pboq_folder):
    if not f.lower().endswith('.db'): continue
    db_path = os.path.join(pboq_folder, f)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Using the columns discovered: Desc=2, Qty=3, Bill=6, Code=16, PlugCat=20
    query = "SELECT [Column 2], [Column 6], RateCode, PlugCategory FROM pboq_items WHERE [Column 6] != '' AND [Column 6] != '0.00'"
    cursor.execute(query)
    rows = cursor.fetchall()
    
    conn_m = sqlite3.connect(master_path)
    cursor_m = conn_m.cursor()
    
    for desc, bill, code, p_cat in rows:
        if not desc or "summary" in desc.lower() or "collection" in desc.lower(): continue
        
        bill_f = float(str(bill).replace(',', ''))
        is_prelim = (str(p_cat).lower() == "preliminaries") if p_cat else False
        
        m_cat = None
        if code:
            cursor_m.execute("SELECT category FROM estimates WHERE rate_code = ?", (code,))
            res = cursor_m.fetchone()
            if res: m_cat = res[0]
            
        category = "Uncategorized"
        if is_prelim: category = "Preliminaries"
        elif p_cat and str(p_cat).strip(): category = str(p_cat).strip()
        elif m_cat and str(m_cat).strip(): category = str(m_cat).strip()
        
        c_agg_bid[category] = c_agg_bid.get(category, 0.0) + bill_f

    conn_m.close()
    conn.close()

print(f"{'Category':<30} | {'Bid Value':<15}")
print("-" * 50)
total = 0
for cat, val in sorted(c_agg_bid.items(), key=lambda x: x[1], reverse=True):
    print(f"{str(cat):<30} | {val:>15,.2f}")
    total += val
print("-" * 50)
print(f"{'TOTAL':<30} | {total:>15,.2f}")
