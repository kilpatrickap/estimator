import sys
import os
from PyQt6.QtWidgets import QApplication

# Add project root to path
sys.path.append(os.getcwd())

from analytics_financial_executive import FinancialExecutiveAnalytic

app = QApplication(sys.argv)
project_dir = r"C:\Users\Consar-Kilpatrick\Desktop\Atlantic Catering School"
analytic = FinancialExecutiveAnalytic(project_dir)

# We can't easily reach inside refresh_data's local variables, 
# so I'll create a special diagnostic method in a subclass or just re-run the logic here
# but using the class's own methods for mapping.

def audit_uncategorized(self):
    self._load_project_settings()
    uncat_list = []
    
    for f in os.listdir(self.pboq_folder):
        if not f.lower().endswith('.db'): continue
        db_path = os.path.join(self.pboq_folder, f)
        mapping = self._get_pboq_mapping(f)
        
        import sqlite3
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(pboq_items)")
        cols = [info[1] for info in cursor.fetchall()]
        
        b_idx = mapping.get('bill_amount')
        d_idx = mapping.get('desc')
        p_code_idx = mapping.get('plug_code')
        p_cat_idx = mapping.get('plug_cat')
        
        # Determine actual column names
        b_col = cols[b_idx + 1] if b_idx is not None else None
        d_col = cols[d_idx + 1] if d_idx is not None else None
        pc_col = cols[p_cat_idx + 1] if p_cat_idx is not None else None
        
        if not b_col or not d_col: continue
        
        query = f"SELECT \"{d_col}\", \"{b_col}\", \"Sheet\" FROM pboq_items"
        # We also need rate code etc. 
        # But let's just use the logic from the class itself by checking what falls into Uncategorized.
        
        # Actually, let's just print the results of the already calculated aggregation 
        # if we could... but we can't.
        
        # Let's just do a targeted query for the values the user mentioned.
        cursor.execute(query)
        for d, b, s in cursor.fetchall():
            b_f = self._to_float(b)
            if b_f == 17606.50:
                print(f"FOUND $17,606.50: {d} (Sheet: {s})")
            if b_f == 6915.00:
                print(f"FOUND $6,915.00: {d} (Sheet: {s})")
        conn.close()

audit_uncategorized(analytic)
app.quit()
