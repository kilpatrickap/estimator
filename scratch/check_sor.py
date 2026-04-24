"""Check SOR database for the same currency issue."""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r'c:\Users\Consar-Kilpatrick\estimator_16Jan26\estimator')

import sqlite3
from database import DatabaseManager

SOR_PATH = r'C:\Users\Consar-Kilpatrick\Desktop\Atlantic Catering School\SOR\SOR_Atlantic BOQ_21Apr26.db'
db = DatabaseManager(SOR_PATH)

rates = db.get_rates_data()
print(f"SOR has {len(rates)} rates")

# Check for exchange rates and unconverted values
conn = sqlite3.connect(SOR_PATH)
c = conn.cursor()

for r in rates:
    est = db.load_estimate_details(r['id'])
    if not est or not est.tasks:
        continue
    
    has_ex = bool(est.exchange_rates)
    totals = est.calculate_totals()
    
    # Check for high labor rates (GHS indicator)
    max_labor = max((lab['rate'] for task in est.tasks for lab in task.labor), default=0)
    
    if has_ex and max_labor > 10:
        print(f"  ❌ {r['rate_code']}: UNCONVERTED (labor={max_labor:.2f}, ex={est.exchange_rates})")
    elif has_ex:
        all_project = all(
            item.get('currency', est.currency) == est.currency
            for task in est.tasks for item in task.all_items
        )
        if all_project:
            print(f"  ⚠️ {r['rate_code']}: Orphan exchange rates, grand={totals['grand_total']:.4f}")
        else:
            print(f"  ✅ {r['rate_code']}: Has foreign resources (correct), grand={totals['grand_total']:.4f}")
    else:
        pass  # OK, no exchange rates

conn.close()
print("\nDone.")
