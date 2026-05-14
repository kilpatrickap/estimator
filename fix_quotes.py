import sqlite3
import json
import os
import glob

proj_db = r"C:\Users\Consar-Kilpatrick\Desktop\Atlantic Catering School\Project Database"
pboq_dir = r"C:\Users\Consar-Kilpatrick\Desktop\Atlantic Catering School\Priced BOQs"

dbs = [f for f in glob.glob(os.path.join(proj_db, "*.db")) if "rates" not in f.lower()]
if dbs:
    conn = sqlite3.connect(dbs[0])
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key='currency_conversion_history'")
    row = c.fetchone()
    if row:
        history = json.loads(row[0])

        
        last_conv = history[-1]
        rate = last_conv['rate']
        operator = last_conv['operator']
        print(f"Applying rate: {rate}, operator: {operator}")
        
        pboq_dbs = glob.glob(os.path.join(pboq_dir, "*.db"))
        for pdb in pboq_dbs:
            pconn = sqlite3.connect(pdb)
            pc = pconn.cursor()
            pc.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='subcontractor_quotes'")
            if pc.fetchone():
                if operator == '*':
                    pc.execute("UPDATE subcontractor_quotes SET rate = rate * ?", (rate,))
                else:
                    pc.execute("UPDATE subcontractor_quotes SET rate = rate / ?", (rate,))
                pconn.commit()
            pconn.close()
            print(f"Updated {os.path.basename(pdb)}")
            
    conn.close()
