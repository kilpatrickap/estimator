import sys
import os
import sqlite3
from PyQt6.QtWidgets import QApplication

# Add project root to path
sys.path.append(os.getcwd())

from analytics_financial_executive import FinancialExecutiveAnalytic

app = QApplication(sys.argv)
project_dir = r"C:\Users\Consar-Kilpatrick\Desktop\Atlantic Catering School"
analytic = FinancialExecutiveAnalytic(project_dir)

def final_audit(self):
    self._load_project_settings()
    
    print(f"{'Description':<60} | {'Bid':<12} | {'Cost':<12}")
    print("-" * 90)
    
    for f in os.listdir(self.pboq_folder):
        if not f.lower().endswith('.db'): continue
        db_path = os.path.join(self.pboq_folder, f)
        mapping = self._get_pboq_mapping(f)
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(pboq_items)")
        cols = [info[1] for info in cursor.fetchall()]
        
        b_idx = mapping.get('bill_amount')
        q_idx = mapping.get('qty')
        d_idx = mapping.get('desc')
        
        b_col = cols[b_idx + 1] if b_idx is not None and (b_idx + 1) < len(cols) else next((c for c in cols if c.lower() in ["bill amount", "billamount"]), None)
        q_col = cols[q_idx + 1] if q_idx is not None and (q_idx + 1) < len(cols) else next((c for c in cols if c.lower() in ["quantity", "qty"]), None)
        d_col = cols[d_idx + 1] if d_idx is not None and (d_idx + 1) < len(cols) else next((c for c in cols if c.lower() in ["description", "desc"]), None)
        
        if not b_col or not q_col: continue

        src_cols = {
            'plug': next((c for c in cols if c.lower() in ["plugrate", "plug_rate"]), None),
            'plug_code': next((c for c in cols if c.lower() in ["plugcode", "plug_code"]), None),
            'plug_cat': next((c for c in cols if c.lower() in ["plugcategory", "plug_category"]), None),
            'sub': next((c for c in cols if c.lower() in ["subbeerate", "sub_rate"]), None),
            'gross': next((c for c in cols if c.lower() in ["grossrate", "gross_rate"]), None),
            'rate_code': next((c for c in cols if c.lower() in ["rate code", "ratecode"]), None),
            'prov': next((c for c in cols if c.lower() in ["provsum", "prov_sum"]), None),
            'pc': next((c for c in cols if c.lower() in ["pcsum", "pc_sum"]), None),
            'dw': next((c for c in cols if c.lower() in ["daywork"]), None)
        }
        
        query_parts = ["Sheet", f"\"{d_col}\"", f"\"{q_col}\"", f"\"{b_col}\""]
        for k in ['plug', 'plug_code', 'plug_cat', 'sub', 'gross', 'rate_code', 'prov', 'pc', 'dw']:
            v = src_cols.get(k)
            query_parts.append(f"\"{v}\"" if v else "0")
        
        query = f"SELECT {', '.join(query_parts)} FROM pboq_items"
        cursor.execute(query)
        rows = cursor.fetchall()
        
        for r in rows:
            sheet, desc, q, b, plug, p_code, p_cat, sub, gross, r_code, prov, pc, dw = r
            desc_low = (desc or "").lower()
            if "collection" in desc_low or "summary" in desc_low: continue
            
            qty_f, bill_f = self._to_float(q), self._to_float(b)
            if bill_f == 0 and qty_f == 0: continue
            
            p_val, s_val, g_val, pr_val, pc_val, d_val = [self._to_float(x) for x in [plug, sub, gross, prov, pc, dw]]
            is_prelim = (str(p_cat).lower() == "preliminaries") if p_cat else False
            
            active_code = p_code if p_code and str(p_code).strip() else r_code
            ratios, master_net_cost, master_cat = self._get_rate_composition(active_code) if active_code else (None, 0.0, None)
            
            category = "Uncategorized"
            if is_prelim: category = "Preliminaries"
            elif p_cat and str(p_cat).strip(): category = str(p_cat).strip()
            elif master_cat and str(master_cat).strip(): category = str(master_cat).strip()
            
            if category == "Uncategorized":
                # Calculate cost fallback
                if master_net_cost > 0: unit_cost = master_net_cost
                else:
                    if p_val > 0: unit_cost = p_val
                    elif s_val > 0: unit_cost = s_val
                    elif g_val > 0: unit_cost = g_val
                    elif d_val > 0: unit_cost = d_val
                    else: unit_cost = bill_f if is_prelim and bill_f > 0 and qty_f <= 1 else 0.0
                
                calc_qty = qty_f if qty_f > 0 else (1.0 if is_prelim and bill_f > 0 else 0.0)
                item_cost = unit_cost * calc_qty
                
                print(f"{desc[:60]:<60} | {bill_f:>12,.2f} | {item_cost:>12,.2f}")

final_audit(analytic)
app.quit()
