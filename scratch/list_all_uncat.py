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

def audit_all_uncat(self):
    self._load_project_settings()
    master_path = os.path.join(self.project_dir, "Project Database", os.path.basename(self.project_dir) + ".db")
    
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
        
        # Mapping helpers
        b_col = cols[mapping.get('bill_amount') + 1] if 'bill_amount' in mapping else None
        q_col = cols[mapping.get('qty') + 1] if 'qty' in mapping else None
        d_col = cols[mapping.get('desc') + 1] if 'desc' in mapping else None
        p_code_col = cols[mapping.get('plug_code') + 1] if 'plug_code' in mapping else None
        p_cat_col = cols[mapping.get('plug_cat') + 1] if 'plug_cat' in mapping else None
        r_code_col = next((c for c in cols if "ratecode" in c.lower() or "rate code" in c.lower()), None)
        
        if not b_col or not d_col: continue
        
        query = f"SELECT \"{d_col}\", \"{b_col}\", \"{q_col if q_col else 'Sheet'}\", \"{p_code_col if p_code_col else 'Sheet'}\", \"{p_cat_col if p_cat_col else 'Sheet'}\", \"{r_code_col if r_code_col else 'Sheet'}\" FROM pboq_items"
        cursor.execute(query)
        
        for row in cursor.fetchall():
            desc, b, q, p_code, p_cat, r_code = row[:6]
            if not desc or "summary" in desc.lower() or "collection" in desc.lower(): continue
            
            bill_f = self._to_float(b)
            if bill_f == 0: continue
            
            # Logic from refresh_data
            is_prelim = (str(p_cat).lower() == "preliminaries") if p_cat and p_cat != 'Sheet' else False
            
            active_code = p_code if p_code and p_code != 'Sheet' and str(p_code).strip() else (r_code if r_code != 'Sheet' else None)
            ratios, master_net_cost, master_cat = self._get_rate_composition(active_code) if active_code else (None, 0.0, None)
            
            category = "Uncategorized"
            if is_prelim: category = "Preliminaries"
            elif p_cat and p_cat != 'Sheet' and str(p_cat).strip(): category = str(p_cat).strip()
            elif master_cat and str(master_cat).strip(): category = str(master_cat).strip()
            
            if category == "Uncategorized":
                # We need to estimate cost for the printout
                # Since we don't have the full buildup here, we'll just show the bid
                print(f"{desc[:60]:<60} | {bill_f:>12,.2f}")

audit_all_uncat(analytic)
app.quit()
