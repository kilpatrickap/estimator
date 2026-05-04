import sqlite3
import os

project_dir = r"C:\Users\Consar-Kilpatrick\Desktop\Atlantic Catering School"
pboq_folder = os.path.join(project_dir, "Priced BOQs")
master_path = r"C:\Users\Consar-Kilpatrick\Desktop\Atlantic Catering School\Project Database\Atlantic Catering School.db"

uncat_items = []

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
        
        if category == "Uncategorized":
            uncat_items.append({
                'desc': desc,
                'bid': bill_f,
                'code': code,
                'file': f
            })

    conn_m.close()
    conn.close()

print(f"{'Description':<60} | {'Bid Value':<15} | {'Rate Code':<15}")
print("-" * 95)
total = 0
for item in sorted(uncat_items, key=lambda x: x['bid'], reverse=True):
    print(f"{item['desc'][:60]:<60} | {item['bid']:>15,.2f} | {str(item['code']):<15}")
    total += item['bid']
print("-" * 95)
print(f"{'TOTAL UNCATEGORIZED':<60} | {total:>15,.2f}")
