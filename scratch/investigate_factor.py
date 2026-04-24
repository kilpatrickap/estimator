"""
Compare Labourer rate across estimates to distinguish truly-converted vs unconverted.
"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r'c:\Users\Consar-Kilpatrick\estimator_16Jan26\estimator')
import sqlite3
from database import DatabaseManager

DB_PATH = r'C:\Users\Consar-Kilpatrick\Desktop\Atlantic Catering School\Project Database\Atlantic Catering School.db'
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# Find all Labourer rates
c.execute("""
SELECT e.rate_code, el.rate, el.currency, er.rate as ex_rate, er.operator as ex_op
FROM estimate_labor el
JOIN tasks t ON el.task_id = t.id
JOIN estimates e ON t.estimate_id = e.id
LEFT JOIN estimate_exchange_rates er ON er.estimate_id = e.id
WHERE el.name_trade = 'Labourer'
ORDER BY e.rate_code
""")
rows = c.fetchall()

print("Labourer rates across estimates:")
print(f"{'Rate':<10} {'Price':<15} {'ExRate':<10} {'Op':<4} {'Interpretation'}")
print("-" * 70)

for r in rows:
    rate_code = r[0] or "(none)"
    price = r[1]
    ex_rate = r[3]
    ex_op = r[4]
    
    # If price is ~20 and there's an exchange rate, it's still GHS
    # If price is ~1.86, it's already USD
    if price > 10:
        interp = f"GHS VALUE! ({price:.2f} / 10.9 = {price/10.9:.2f} USD)"
    else:
        interp = f"USD value (correct)"
    
    print(f"{rate_code:<10} {price:<15.4f} {str(ex_rate or ''):<10} {str(ex_op or ''):<4} {interp}")

# Now determine which estimates need their resources converted
print("\n\n=== FULL DIAGNOSIS ===")
c.execute("""
SELECT e.id, e.rate_code, e.currency, er.rate, er.operator 
FROM estimates e 
LEFT JOIN estimate_exchange_rates er ON er.estimate_id = e.id 
ORDER BY e.rate_code
""")
all_ests = c.fetchall()

db = DatabaseManager(DB_PATH)

for est_id, rate_code, est_curr, ex_rate, ex_op in all_ests:
    est = db.load_estimate_details(est_id)
    if not est or not est.tasks:
        continue
    
    has_exchange = bool(est.exchange_rates)
    if not has_exchange:
        print(f"  {rate_code or f'(id={est_id})':<10} No exchange rates - OK")
        continue
    
    # Check: are ALL resources in project currency?
    all_project_curr = True
    any_foreign = False
    for task in est.tasks:
        for item in task.all_items:
            item_curr = item.get('currency', est.currency)
            if item_curr != est.currency:
                all_project_curr = False
                any_foreign = True
    
    if any_foreign:
        print(f"  {rate_code:<10} Has foreign-currency resources (will be auto-converted) - OK")
        continue
    
    # All resources say project currency but exchange rates exist
    # This is the problematic case - are the values ACTUALLY converted?
    # Check if resources were auto-converted during rate build-up (small USD values)
    # or just relabeled by bulk_update_estimate_currency (large GHS values)
    
    # Use the exchange rate to test: if we "convert" the total, does it become reasonable?
    raw_total = sum(item['total'] for task in est.tasks for item in task.all_items)
    
    ex_data = list(est.exchange_rates.values())[0]
    if ex_data['operator'] == '/':
        converted_total = raw_total / ex_data['rate']
    else:
        converted_total = raw_total * ex_data['rate']
    
    # The ratio tells us: if ratio > 1, converting makes the number smaller = values are in GHS
    # If ratio < 1, converting makes it bigger = values are already in a smaller unit (USD via multiply)
    ratio = raw_total / converted_total if converted_total else 1
    
    # For multiply operators (rate=0.0917): GHS * 0.0917 = USD, so ratio = 1/0.0917 ≈ 10.9
    # For divide operators (rate=10.9): GHS / 10.9 = USD, so ratio = 10.9
    # In both cases, if values are still in GHS, ratio >> 1
    # If values are already in USD:
    #   - multiply by 0.0917: would make them even smaller (wrong direction) - ratio = 1/0.0917
    #   - divide by 10.9: would make them even smaller - ratio = 10.9
    # Hmm, this doesn't help distinguish.
    
    # Better approach: The original GHS Labourer rate was ~20.25 GHS/hr
    # The converted USD rate should be ~1.86 USD/hr
    # So check the actual resource values
    
    # If any resource price > 10 and ex_rate exists, values are likely still in GHS
    max_labor_rate = max((lab['rate'] for task in est.tasks for lab in task.labor), default=0)
    
    if max_labor_rate > 10:
        needs_fix = "NEEDS CONVERSION (GHS values labeled as USD)"
        symbol = "❌"
    elif max_labor_rate > 0:
        needs_fix = "Already converted to USD"
        symbol = "✅"
    else:
        # No labor - check materials
        max_mat = max((mat['unit_cost'] for task in est.tasks for mat in task.materials), default=0)
        if max_mat > 100:
            needs_fix = "LIKELY NEEDS CONVERSION (high material prices)"
            symbol = "❌"
        else:
            needs_fix = "Cannot determine (no labor reference)"
            symbol = "⚠️"
    
    print(f"  {symbol} {rate_code:<10} max_labor_rate={max_labor_rate:.2f}, raw_total={raw_total:.2f} → {needs_fix}")

conn.close()
