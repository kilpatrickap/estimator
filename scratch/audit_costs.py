import sqlite3

# BOQ Database
boq_path = r"C:\Users\Consar-Kilpatrick\Desktop\Atlantic Catering School\Priced BOQs\PBOQ_Atlantic BOQ_21Apr26.db"
master_path = r"C:\Users\Consar-Kilpatrick\Desktop\Atlantic Catering School\Project Database\Atlantic Catering School.db"

conn_boq = sqlite3.connect(boq_path)
conn_master = sqlite3.connect(master_path)

# Find top items in BOQ
query = "SELECT Description, Qty, [Bill Amount], RateCode, [Rate Code] FROM pboq_items WHERE [Bill Amount] != '' AND [Bill Amount] IS NOT NULL ORDER BY CAST(REPLACE(REPLACE([Bill Amount], ',', ''), '$', '') AS FLOAT) DESC LIMIT 5"
cursor_boq = conn_boq.cursor()
cursor_boq.execute(query)
top_items = cursor_boq.fetchall()

print(f"{'Description':<40} | {'Qty':<10} | {'Bill Amt':<12} | {'RateCode':<10} | {'NetCost(DB)':<12} | {'TotalNet':<12}")
print("-" * 110)

total_net_sum = 0
for desc, qty, bill_amt, rc1, rc2 in top_items:
    code = rc1 or rc2
    net_cost = 0.0
    if code:
        cursor_master = conn_master.cursor()
        cursor_master.execute("SELECT net_total FROM estimates WHERE rate_code = ?", (code,))
        row = cursor_master.fetchone()
        if row:
            net_cost = row[0]
    
    qty_f = float(qty.replace(',', '')) if qty else 0.0
    total_net = net_cost * qty_f
    total_net_sum += total_net
    print(f"{desc[:38]:<40} | {qty:<10} | {bill_amt:<12} | {code:<10} | {net_cost:<12.2f} | {total_net:<12.2f}")

conn_boq.close()
conn_master.close()
