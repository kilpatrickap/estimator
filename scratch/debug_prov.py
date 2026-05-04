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

def debug_prov_sum(self):
    self._load_project_settings()
    
    for f in os.listdir(self.pboq_folder):
        if not f.lower().endswith('.db'): continue
        db_path = os.path.join(self.pboq_folder, f)
        mapping = self._get_pboq_mapping(f)
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(pboq_items)")
        cols = [info[1] for info in cursor.fetchall()]
        
        b_col = cols[mapping.get('bill_amount') + 1]
        d_col = cols[mapping.get('desc') + 1]
        prov_col = cols[mapping.get('prov_sum') + 1] if 'prov_sum' in mapping else None
        
        if not b_col or not d_col: continue
        
        query = f"SELECT \"{d_col}\", \"{b_col}\", \"{prov_col if prov_col else 'Sheet'}\" FROM pboq_items"
        cursor.execute(query)
        
        for row in cursor.fetchall():
            desc, b, prov = row
            if "structural audit" in str(desc).lower():
                print(f"DEBUG: Desc={desc} | Bid={b} | Prov={prov}")
        conn.close()

debug_prov_sum(analytic)
app.quit()
