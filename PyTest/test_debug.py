import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import sqlite3
import json

def test_refresh_data_with_settings():
    project_dir = "C:/Users/Consar-Kilpatrick/Desktop/Atlantic Catering School"
    pboq_folder = os.path.join(project_dir, "Priced BOQs")
    
    # 1. Load project settings exactly like the dashboard does
    overhead_rate = 0.0
    profit_rate = 0.0
    try:
        db_dir = os.path.join(project_dir, "Project Database")
        if os.path.exists(db_dir):
            dbs = [f for f in os.listdir(db_dir) if f.lower().endswith('.db') and "rates" not in f.lower()]
            if dbs:
                db_path = os.path.join(db_dir, dbs[0])
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                try:
                    cursor.execute("SELECT value FROM settings WHERE key='overhead'")
                    row = cursor.fetchone()
                    if row: overhead_rate = float(row[0])
                    
                    cursor.execute("SELECT value FROM settings WHERE key='profit'")
                    row = cursor.fetchone()
                    if row: profit_rate = float(row[0])
                except: pass
                conn.close()
    except Exception as e:
        print(f"Error loading settings: {e}")
        
    print(f"\nSettings loaded:")
    print(f"  overhead_rate: {overhead_rate}")
    print(f"  profit_rate: {profit_rate}")
    
    # 2. Sum net costs
    total_net_cost = 0.0
    for f in os.listdir(pboq_folder):
        if f.lower().endswith('.db'):
            db_path = os.path.join(pboq_folder, f)
            
            qty_col_idx = -1
            desc_col_idx = -1
            bill_rate_col_idx = -1
            bill_amt_col_idx = -1
            
            state_file = os.path.join(project_dir, "PBOQ States", f + ".json")
            state_data = {}
            if os.path.exists(state_file):
                try:
                    with open(state_file, 'r') as sf:
                        state_data = json.load(sf)
                        m = state_data.get('mappings', {})
                        qty_col_idx = m.get('qty', -1)
                        desc_col_idx = m.get('desc', -1)
                        bill_rate_col_idx = m.get('bill_rate', -1)
                        bill_amt_col_idx = m.get('bill_amount', -1)
                except: pass
            
            dummy_val = state_data.get('dummy_rate', 0.1)
            
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info(pboq_items)")
                cols = [info[1] for info in cursor.fetchall()]
                
                qty_name = cols[qty_col_idx + 1] if qty_col_idx >= 0 and (qty_col_idx + 1) < len(cols) else next((c for c in cols if c.lower() in ["quantity", "qty"]), None)
                desc_name = cols[desc_col_idx + 1] if desc_col_idx >= 0 and (desc_col_idx + 1) < len(cols) else next((c for c in cols if c.lower() in ["description", "desc"]), None)
                bill_rate_name = cols[bill_rate_col_idx + 1] if bill_rate_col_idx >= 0 and (bill_rate_col_idx + 1) < len(cols) else next((c for c in cols if c.lower() in ["bill rate", "billrate", "column 4"]), None)
                bill_amt_name = cols[bill_amt_col_idx + 1] if bill_amt_col_idx >= 0 and (bill_amt_col_idx + 1) < len(cols) else next((c for c in cols if c.lower() in ["bill amount", "billamount", "column 5"]), None)
                
                col_map = {
                    'sheet': next((c for c in cols if c.lower() == 'sheet'), None),
                    'desc': desc_name,
                    'qty': qty_name,
                    'bill_rate': bill_rate_name,
                    'bill_amt': bill_amt_name,
                    'gross': next((c for c in cols if c.lower() in ["grossrate", "gross_rate"]), None),
                    'plug': next((c for c in cols if c.lower() in ["plugrate", "plug_rate"]), None),
                    'sub': next((c for c in cols if c.lower() in ["subbeerate", "sub_rate"]), None),
                    'prov': next((c for c in cols if c.lower() in ["provsum", "prov_sum"]), None),
                    'pc': next((c for c in cols if c.lower() in ["pcsum", "pc_sum"]), None),
                    'dw': next((c for c in cols if c.lower() in ["daywork"]), None),
                    'flag': next((c for c in cols if c.lower() == "isflagged"), None),
                    'rcode': next((c for c in cols if c.lower() in ["ratecode", "rate_code"]), None),
                    'pcode': next((c for c in cols if c.lower() in ["plugcode", "plug_code"]), None)
                }
                
                if not (col_map['desc'] and col_map['qty']):
                    continue
                    
                query_cols = []
                for k in ['sheet', 'desc', 'qty', 'bill_rate', 'bill_amt', 'gross', 'plug', 'sub', 'prov', 'pc', 'dw', 'flag', 'rcode', 'pcode']:
                    if col_map[k]: query_cols.append(f"\"{col_map[k]}\"")
                    else: query_cols.append("''")
                    
                cursor.execute(f"SELECT {', '.join(query_cols)} FROM pboq_items")
                rows = cursor.fetchall()
                
                def _to_float(val):
                    if not val: return 0.0
                    try: return float(str(val).replace(',', '').replace(' ', '').replace('₵','').replace('$','').strip())
                    except: return 0.0
                    
                # Cache estimates table rates for speed
                rate_cache = {}
                try:
                    cursor.execute("SELECT net_total FROM estimates WHERE rate_code = ?") # Wait, this is on a different database, but let's check
                except:
                    # Let's get rates from project.db
                    proj_conn = sqlite3.connect(os.path.join(project_dir, "Project Database", "Atlantic Catering School.db"))
                    proj_cursor = proj_conn.cursor()
                    proj_cursor.execute("SELECT rate_code, net_total FROM estimates")
                    for rc, nt in proj_cursor.fetchall():
                        if rc: rate_cache[rc.strip().upper()] = float(nt or 0.0)
                    proj_conn.close()
                
                for r in rows:
                    sheet, desc, q, br, ba, gross, plug, sub, prov, pc, dw, flag, rcode, pcode = r
                    desc_low = (desc or "").lower()
                    if not str(desc).strip() or "collection" in desc_low or "summary" in desc_low:
                        continue
                        
                    qty_f = _to_float(q)
                    bill_rate_f = _to_float(br)
                    bill_amt_f = _to_float(ba)
                    
                    if qty_f == 0 and bill_amt_f == 0:
                        continue
                        
                    g_val = _to_float(gross)
                    p_val = _to_float(plug)
                    s_val = _to_float(sub)
                    pr_val = _to_float(prov)
                    pc_val = _to_float(pc)
                    d_val = _to_float(dw)
                    
                    is_row_priced = (g_val > 0 or p_val > 0 or s_val > 0 or pr_val > 0 or pc_val > 0 or d_val > 0)
                    if not is_row_priced:
                        if bill_rate_f > 0 and abs(bill_rate_f - dummy_val) > 0.0001:
                            is_row_priced = True
                            
                    is_priced = is_row_priced
                    
                    active_code = pcode if pcode and str(pcode).strip() else rcode
                    master_net_cost = rate_cache.get(str(active_code).strip().upper(), 0.0) if active_code else 0.0
                    
                    unit_cost = 0.0
                    if pr_val > 0: unit_cost = pr_val
                    elif pc_val > 0: unit_cost = pc_val
                    elif d_val > 0: unit_cost = d_val
                    elif master_net_cost > 0: unit_cost = master_net_cost
                    else:
                        if p_val > 0: unit_cost = p_val
                        elif s_val > 0: unit_cost = s_val
                        elif g_val > 0: unit_cost = g_val
                        else:
                            if bill_amt_f > 0:
                                unit_cost = bill_amt_f if qty_f <= 1 else 0.0
                                
                    calc_qty = qty_f if qty_f > 0 else (1.0 if bill_amt_f > 0 else 0.0)
                    item_net_cost = round(unit_cost * calc_qty, 2) if is_priced else 0.0
                    
                    total_net_cost += item_net_cost
                conn.close()
            except Exception as e:
                print(f"Error: {e}")
                
    combined_markup_pct = (overhead_rate + profit_rate) / 100.0
    total_bid = total_net_cost * (1.0 + combined_markup_pct)
    print(f"\nCalculated Total Bid Value: {total_bid:,.2f}")
