import sqlite3

# BOQ Database
boq_path = r"C:\Users\Consar-Kilpatrick\Desktop\Atlantic Catering School\Priced BOQs\PBOQ_Atlantic BOQ_21Apr26.db"
master_path = r"C:\Users\Consar-Kilpatrick\Desktop\Atlantic Catering School\Project Database\Atlantic Catering School.db"

conn_boq = sqlite3.connect(boq_path)
conn_master = sqlite3.connect(master_path)

# Query using identified columns
# Column 2 = Desc, Column 3 = Unit, Column 4 = Qty, [Bill Amount] = Bill, RateCode = Code
query = "SELECT [Column 2], [Column 3], [Column 4], [Bill Amount], RateCode FROM pboq_items WHERE [Bill Amount] != '' AND [Bill Amount] != '0.00' ORDER BY CAST(REPLACE(REPLACE([Bill Amount], ',', ''), '$', '') AS FLOAT) DESC LIMIT 10"
cursor_boq = conn_boq.cursor()
cursor_boq.execute(query)
top_items = cursor_boq.fetchall()

print(f"{'Description':<35} | {'Unit':<5} | {'Qty':<8} | {'Code':<8} | {'Net(DB)':<10} | {'TotalNet':<12}")
print("-" * 100)

for desc, unit, qty, bill_amt, code in top_items:
    if not desc or "summary" in desc.lower() or "collection" in desc.lower(): continue
    
    net_cost = 0.0
    if code:
        cursor_master = conn_master.cursor()
        cursor_master.execute("SELECT net_total FROM estimates WHERE rate_code = ?", (code,))
        row = cursor_master.fetchone()
        if row: net_cost = row[0]
    
    try:
        qty_f = float(str(qty).replace(',', '')) if qty else 0.0
    except:
        qty_f = 0.0
        
    total_net = net_cost * qty_f
    
    print(f"{str(desc)[:33]:<35} | {str(unit):<5} | {str(qty):<8} | {str(code):<8} | {net_cost:<10.2f} | {total_net:<12.2f}")

conn_boq.close()
conn_master.close()
