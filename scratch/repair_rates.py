"""
DATA REPAIR: Convert resource values from GHS to USD for estimates
that had their currency labels swapped but values never converted.

These estimates have:
- exchange_rates defined (GHS -> USD conversion)
- all resources labeled as USD ($)  
- but resource VALUES are still in GHS

The fix: multiply/divide each resource value by the stored exchange rate,
then remove the exchange rate record (since conversion is now embedded in values).
"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r'c:\Users\Consar-Kilpatrick\estimator_16Jan26\estimator')

import sqlite3
from database import DatabaseManager

DB_PATH = r'C:\Users\Consar-Kilpatrick\Desktop\Atlantic Catering School\Project Database\Atlantic Catering School.db'
db = DatabaseManager(DB_PATH)

# Estimates confirmed to need conversion (GHS values labeled as USD)
# Based on diagnosis: labor rates > 10 with exchange rates present
NEEDS_CONVERSION = []

# Auto-detect: find estimates where exchange rates exist, all resources say project currency,
# and labor rates indicate GHS values
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

c.execute("""
SELECT DISTINCT e.id, e.rate_code, er.currency, er.rate, er.operator
FROM estimates e
JOIN estimate_exchange_rates er ON er.estimate_id = e.id
ORDER BY e.rate_code
""")
candidates = c.fetchall()
conn.close()

project_currency = db.get_setting('currency', 'USD ($)')

for est_id, rate_code, ex_curr, ex_rate, ex_op in candidates:
    est = db.load_estimate_details(est_id)
    if not est or not est.tasks:
        continue
    
    # Check if all resources are labeled as project currency
    all_project = all(
        item.get('currency', est.currency) == project_currency
        for task in est.tasks for item in task.all_items
    )
    
    if not all_project:
        continue  # Has foreign-currency resources, will be handled by convert_to_base_currency
    
    # Check if values are unconverted (GHS magnitude)
    # Use labor rates as reference: GHS Labourer ≈ 20.25, USD Labourer ≈ 1.86
    labor_rates = [lab['rate'] for task in est.tasks for lab in task.labor]
    
    if labor_rates:
        max_labor = max(labor_rates)
        # If max labor rate > 10, values are still in GHS
        if max_labor > 10:
            NEEDS_CONVERSION.append((est_id, rate_code, ex_curr, ex_rate, ex_op))
            continue
        else:
            # Already converted
            continue
    
    # No labor - check materials for high values
    mat_prices = [mat['unit_cost'] for task in est.tasks for mat in task.materials]
    if mat_prices:
        max_mat = max(mat_prices)
        # GHS material prices are typically 10x+ higher than USD
        if max_mat > 100 and ex_op == '/' and ex_rate > 5:
            NEEDS_CONVERSION.append((est_id, rate_code, ex_curr, ex_rate, ex_op))
        elif max_mat > 50 and ex_op == '*' and ex_rate < 0.2:
            NEEDS_CONVERSION.append((est_id, rate_code, ex_curr, ex_rate, ex_op))

print(f"Project currency: {project_currency}")
print(f"\nEstimates that NEED resource value conversion:")
print(f"{'ID':<5} {'Rate':<10} {'Ex.Curr':<12} {'Ex.Rate':<10} {'Op'}")
print("-" * 50)
for est_id, rate_code, ex_curr, ex_rate, ex_op in NEEDS_CONVERSION:
    print(f"{est_id:<5} {rate_code:<10} {ex_curr:<12} {ex_rate:<10} {ex_op}")

print(f"\nTotal: {len(NEEDS_CONVERSION)} estimates need fixing")
print("\n--- PERFORMING CONVERSION ---\n")

for est_id, rate_code, ex_curr, ex_rate, ex_op in NEEDS_CONVERSION:
    est = db.load_estimate_details(est_id)
    if not est:
        continue
    
    print(f"Converting {rate_code} (id={est_id}):")
    
    # Get pre-conversion totals
    old_totals = est.calculate_totals()
    print(f"  BEFORE: subtotal={old_totals['subtotal']:.4f}, grand={old_totals['grand_total']:.4f}")
    
    # Convert each resource value using the exchange rate
    for task in est.tasks:
        for item in task.all_items:
            old_total = item['total']
            
            if 'unit_cost' in item:
                old_price = item['unit_cost']
                if ex_op == '/':
                    new_price = old_price / ex_rate
                else:
                    new_price = old_price * ex_rate
                item['unit_cost'] = new_price
                item['total'] = item['qty'] * new_price
            elif 'rate' in item:
                old_rate = item['rate']
                if ex_op == '/':
                    new_rate = old_rate / ex_rate
                else:
                    new_rate = old_rate * ex_rate
                item['rate'] = new_rate
                item['total'] = item.get('hours', 1.0) * new_rate
            elif 'amount' in item:
                old_amt = item['amount']
                if ex_op == '/':
                    new_amt = old_amt / ex_rate
                else:
                    new_amt = old_amt * ex_rate
                item['amount'] = new_amt
                item['total'] = new_amt
    
    # Remove the exchange rate since values are now properly in project currency
    est.exchange_rates = {}
    
    # Recalculate and save
    new_totals = est.calculate_totals()
    print(f"  AFTER:  subtotal={new_totals['subtotal']:.4f}, grand={new_totals['grand_total']:.4f}")
    
    # Verify the conversion makes sense
    if old_totals['grand_total'] > 0:
        ratio = new_totals['grand_total'] / old_totals['grand_total']
        if ex_op == '/':
            expected_ratio = 1.0 / ex_rate
        else:
            expected_ratio = ex_rate
        print(f"  Ratio: {ratio:.4f} (expected ≈{expected_ratio:.4f})")
    
    db.save_estimate(est)
    print(f"  ✅ Saved\n")

# Verify final state
print("\n=== VERIFICATION ===")
for est_id, rate_code, _, _, _ in NEEDS_CONVERSION:
    est = db.load_estimate_details(est_id)
    totals = est.calculate_totals()
    
    # Check DB values match
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT net_total, grand_total FROM estimates WHERE id=?', (est_id,))
    db_row = c.fetchone()
    c.execute('SELECT COUNT(*) FROM estimate_exchange_rates WHERE estimate_id=?', (est_id,))
    ex_count = c.fetchone()[0]
    conn.close()
    
    match = abs(db_row[1] - totals['grand_total']) < 0.01
    
    print(f"  {rate_code}: grand={totals['grand_total']:.4f} (DB={db_row[1]:.4f}) {'✅' if match else '❌'}, ex_rates_remaining={ex_count}")
