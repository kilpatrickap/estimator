"""Check FMWK rates specifically to see if they need conversion."""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r'c:\Users\Consar-Kilpatrick\estimator_16Jan26\estimator')

from database import DatabaseManager
DB_PATH = r'C:\Users\Consar-Kilpatrick\Desktop\Atlantic Catering School\Project Database\Atlantic Catering School.db'
db = DatabaseManager(DB_PATH)

for rate_code in ['FMWK1A', 'FMWK1B', 'FMWK1C']:
    rates_data = [r for r in db.get_rates_data() if r['rate_code'] == rate_code]
    if not rates_data:
        print(f"{rate_code}: NOT FOUND")
        continue
    
    est = db.load_estimate_details(rates_data[0]['id'])
    if not est:
        continue
    
    print(f"\n=== {rate_code} (id={est.id}) ===")
    print(f"  Currency: {est.currency}")
    print(f"  Exchange rates: {est.exchange_rates}")
    print(f"  Factor: {est.adjustment_factor}")
    totals = est.calculate_totals()
    print(f"  Grand total: {totals['grand_total']:.4f}")
    
    for task in est.tasks:
        print(f"  Task: {task.description}")
        for cat_name, items in [('materials', task.materials), ('labor', task.labor), 
                                 ('equipment', task.equipment), ('plant', task.plant)]:
            for item in items:
                name = item.get('name', item.get('trade', item.get('description', '')))
                cost = item.get('unit_cost', item.get('rate', item.get('amount', 0)))
                qty = item.get('qty', item.get('hours', 1))
                total = item.get('total', 0)
                curr = item.get('currency', 'N/A')
                print(f"    [{cat_name}] {name}: cost={cost:.4f} {curr}, qty={qty}, total={total:.4f}")
