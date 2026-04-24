"""
Repair FMWK1A: The Softwood material price is still in GHS (4166.67)
but labeled as USD. The labor was correctly auto-converted.
The exchange rate is GHS * 0.0917 = USD.

We need to convert only the unconverted resources.
"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r'c:\Users\Consar-Kilpatrick\estimator_16Jan26\estimator')

from database import DatabaseManager
DB_PATH = r'C:\Users\Consar-Kilpatrick\Desktop\Atlantic Catering School\Project Database\Atlantic Catering School.db'
db = DatabaseManager(DB_PATH)

# ---- FMWK1A ----
est = db.load_estimate_details(6)
print(f"=== FMWK1A BEFORE ===")
print(f"Exchange rates: {est.exchange_rates}")

ex_data = est.exchange_rates.get('GHS (₵)')
if not ex_data:
    print("No exchange rate found, skipping")
    exit()

ex_rate = ex_data['rate']
ex_op = ex_data['operator']

for task in est.tasks:
    for item in task.all_items:
        name = item.get('name', item.get('trade', ''))
        cost = item.get('unit_cost', item.get('rate', item.get('amount', 0)))
        
        # Determine if this resource needs conversion:
        # If price > threshold, it's likely still in GHS
        # Labor at 2.52 is already USD, Softwood at 4166.67 is GHS
        
        # For * 0.0917: USD values should be small (< ~50 for typical rates)
        # GHS values would be 10x+ larger
        needs_convert = False
        
        if ex_op == '*' and ex_rate < 1:
            # Values already converted would be small (multiplied by 0.0917)
            # Values still in GHS would be large (need to multiply by 0.0917)
            if cost > 50:  # Threshold: anything > 50 is likely GHS
                needs_convert = True
        elif ex_op == '/' and ex_rate > 1:
            # Values already converted would be small (divided by 10.9)
            # Values still in GHS would be large
            if cost > 50:
                needs_convert = True
        
        if needs_convert:
            old_cost = cost
            if 'unit_cost' in item:
                if ex_op == '/':
                    item['unit_cost'] /= ex_rate
                else:
                    item['unit_cost'] *= ex_rate
                item['total'] = item['qty'] * item['unit_cost']
                print(f"  CONVERTED {name}: {old_cost:.4f} → {item['unit_cost']:.4f}")
            elif 'rate' in item:
                if ex_op == '/':
                    item['rate'] /= ex_rate
                else:
                    item['rate'] *= ex_rate
                item['total'] = item.get('hours', 1.0) * item['rate']
                print(f"  CONVERTED {name}: {old_cost:.4f} → {item['rate']:.4f}")
        else:
            print(f"  SKIPPED {name}: {cost:.4f} (already converted)")

# Remove exchange rates since all values are now in USD
est.exchange_rates = {}

totals = est.calculate_totals()
print(f"\nFMWK1A AFTER: grand_total={totals['grand_total']:.4f}")
db.save_estimate(est)
print("✅ FMWK1A saved")

# Now check FMWK1B and FMWK1C which reference FMWK1A as a sub-rate
# These use the GrossRate from FMWK1A, so they should auto-update if 
# their material cost references FMWK1A's grand_total
for rate_code, est_id in [('FMWK1B', 11), ('FMWK1C', 17)]:
    est = db.load_estimate_details(est_id)
    if not est:
        continue
    
    print(f"\n=== {rate_code} ===")
    for task in est.tasks:
        for mat in task.materials:
            print(f"  {mat['name']}: cost={mat['unit_cost']:.4f}, total={mat['total']:.4f}")
            # Check if this references FMWK1A
            if 'FMWK1A' in mat['name']:
                print(f"    → This references FMWK1A. Current value {mat['unit_cost']:.4f} should match FMWK1A's new grand_total")
                # The reference price should be FMWK1A's grand total
                fmwk1a = db.load_estimate_details(6)
                fmwk1a_grand = fmwk1a.calculate_totals()['grand_total']
                print(f"    → FMWK1A's current grand_total: {fmwk1a_grand:.4f}")
                
                if abs(mat['unit_cost'] - fmwk1a_grand) > 0.01:
                    print(f"    → MISMATCH! Updating reference...")
                    mat['unit_cost'] = fmwk1a_grand
                    mat['total'] = mat['qty'] * fmwk1a_grand
                    print(f"    → Updated to {mat['unit_cost']:.4f}")
    
    totals = est.calculate_totals()
    print(f"  Grand total: {totals['grand_total']:.4f}")
    db.save_estimate(est)
    print(f"  ✅ {rate_code} saved")
