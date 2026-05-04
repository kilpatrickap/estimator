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

def debug_all_items(self):
    self._load_project_settings()
    
    print(f"{'Description':<50} | {'Category':<20} | {'Bid':<12}")
    print("-" * 90)
    
    for f in os.listdir(self.pboq_folder):
        if not f.lower().endswith('.db'): continue
        db_path = os.path.join(self.pboq_folder, f)
        mapping = self._get_pboq_mapping(f)
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(pboq_items)")
        cols = [info[1] for info in cursor.fetchall()]
        
        # COLUMN DETECTION
        b_idx = mapping.get('bill_amount')
        q_idx = mapping.get('qty')
        d_idx = mapping.get('desc')
        p_code_idx = mapping.get('plug_code')
        p_cat_idx = mapping.get('plug_cat')
        r_code_idx = next((i for i, c in enumerate(cols) if "ratecode" in c.lower() or "rate code" in c.lower()), None)
        
        b_col = cols[b_idx + 1] if b_idx is not None else None
        d_col = cols[d_idx + 1] if d_idx is not None else None
        pc_col = cols[p_cat_idx + 1] if p_cat_idx is not None else None
        p_code_col = cols[p_code_idx + 1] if p_code_idx is not None else None
        
        if not b_col or not d_col: continue
        
        cursor.execute(f"SELECT \"{d_col}\", \"{b_col}\", \"{pc_col if pc_col else 'Sheet'}\", \"{p_code_col if p_code_col else 'Sheet'}\", \"{cols[r_code_idx] if r_code_idx is not None else 'Sheet'}\" FROM pboq_items")
        
        for row in cursor.fetchall():
            desc, b, p_cat, p_code, r_code = row
            if not desc or "summary" in desc.lower() or "collection" in desc.lower(): continue
            
            bill_f = self._to_float(b)
            if bill_f == 0: continue
            
            is_prelim = (str(p_cat).lower() == "preliminaries") if p_cat and p_cat != 'Sheet' else False
            active_code = p_code if p_code and p_code != 'Sheet' and str(p_code).strip() else (r_code if r_code != 'Sheet' else None)
            ratios, master_net_cost, master_cat = self._get_rate_composition(active_code) if active_code else (None, 0.0, None)
            
            category = "Uncategorized"
            if is_prelim: category = "Preliminaries"
            elif p_cat and p_cat != 'Sheet' and str(p_cat).strip(): category = str(p_cat).strip()
            elif master_cat and str(master_cat).strip(): category = str(master_cat).strip()
            
            if category == "Uncategorized":
                print(f"{desc[:50]:<50} | {category:<20} | {bill_f:>12,.2f}")

debug_all_items(analytic)
app.quit()
