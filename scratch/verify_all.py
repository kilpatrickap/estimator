"""Final verification of all rates after repair."""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r'c:\Users\Consar-Kilpatrick\estimator_16Jan26\estimator')

import sqlite3
from database import DatabaseManager

DB_PATH = r'C:\Users\Consar-Kilpatrick\Desktop\Atlantic Catering School\Project Database\Atlantic Catering School.db'
db = DatabaseManager(DB_PATH)

TARGET_RATES = ['FMWK1A', 'FMWK1B', 'FMWK1C', 'ETWK1F', 'CONC1A', 'CONC1B', 'RFMT1A', 'RFMT1B', 'WALL1A']
ALL_RATES = sorted(set(r['rate_code'] for r in db.get_rates_data() if r.get('rate_code')))

print(f"{'Rate':<10} {'Grand Total':<14} {'ExRates?':<10} {'Status'}")
print("=" * 55)

for rate_code in ALL_RATES:
    rates_data = [r for r in db.get_rates_data() if r['rate_code'] == rate_code]
    if not rates_data:
        continue
    
    est = db.load_estimate_details(rates_data[0]['id'])
    if not est:
        continue
    
    totals = est.calculate_totals()
    has_ex = bool(est.exchange_rates)
    
    # Check for remaining unconverted resources
    unconverted = False
    for task in est.tasks:
        for lab in task.labor:
            if lab['rate'] > 10 and has_ex:
                unconverted = True
    
    marker = "⚠️ " if rate_code in TARGET_RATES else "  "
    if unconverted:
        status = "❌ STILL UNCONVERTED"
    elif has_ex:
        # Check if exchange rates are actually needed
        all_project = all(
            item.get('currency', est.currency) == est.currency
            for task in est.tasks for item in task.all_items
        )
        if all_project:
            status = "⚠️ Has orphan exchange rates"
        else:
            status = "✅ OK (foreign resources)"
    else:
        status = "✅ OK"
    
    print(f"{marker}{rate_code:<8} {totals['grand_total']:<14.4f} {'Yes' if has_ex else 'No':<10} {status}")

# Now test factor application
print("\n\n=== TESTING FACTOR APPLICATION ===")
print("Applying factor 1.1 to all estimates...")

# Save current state for comparison
pre_factor = {}
for rate_code in ALL_RATES:
    rates_data = [r for r in db.get_rates_data() if r['rate_code'] == rate_code]
    if rates_data:
        est = db.load_estimate_details(rates_data[0]['id'])
        if est:
            pre_factor[rate_code] = est.calculate_totals()['grand_total']

db.bulk_update_estimate_factor(1.1)

print(f"\n{'Rate':<10} {'Before (f=1.15)':<16} {'After (f=1.1)':<16} {'Ratio':<8} {'Expected':<8} {'OK?'}")
print("=" * 75)

for rate_code in ALL_RATES:
    rates_data = [r for r in db.get_rates_data() if r['rate_code'] == rate_code]
    if not rates_data:
        continue
    
    est = db.load_estimate_details(rates_data[0]['id'])
    if not est:
        continue
    
    totals = est.calculate_totals()
    before = pre_factor.get(rate_code, 0)
    after = totals['grand_total']
    
    if before > 0:
        ratio = after / before
        expected_ratio = 1.1 / 1.15  # New factor / old factor
        ok = abs(ratio - expected_ratio) < 0.01
        marker = "✅" if ok else "❌"
        print(f"{rate_code:<10} {before:<16.4f} {after:<16.4f} {ratio:<8.4f} {expected_ratio:<8.4f} {marker}")
    else:
        print(f"{rate_code:<10} {before:<16.4f} {after:<16.4f} {'N/A':<8} {'N/A':<8}")

# Restore original factor
db.bulk_update_estimate_factor(1.15)
print("\nRestored factor to 1.15")
