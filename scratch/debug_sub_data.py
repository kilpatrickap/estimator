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

def debug_sub_ratios(self):
    self._load_project_settings()
    
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
        p_code_idx = mapping.get('plug_code')
        p_cat_idx = mapping.get('plug_cat')
        s_pkg_idx = mapping.get('sub_package')
        s_n_idx = mapping.get('sub_name')
        
        # Determine actual column names
        b_col = cols[b_idx + 1] if b_idx is not None else None
        d_col = cols[d_idx + 1] if d_idx is not None else None
        sp_col = cols[s_pkg_idx + 1] if s_pkg_idx is not None else None
        sn_col = cols[s_n_idx + 1] if s_n_idx is not None else None
        
        if not b_col or not d_col: continue
        
        query = f"SELECT \"{d_col}\", \"{b_col}\", \"{sp_col if sp_col else 'Sheet'}\", \"{sn_col if sn_col else 'Sheet'}\" FROM pboq_items"
        cursor.execute(query)
        
        for row in cursor.fetchall():
            desc, b, sp, sn = row
            if "polythene" in str(desc).lower():
                print(f"DEBUG Polythene: Bid={b} | Pkg={sp} | Name={sn}")
        conn.close()

debug_sub_ratios(analytic)
app.quit()
