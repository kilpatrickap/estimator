import sys; sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r'c:\Users\Consar-Kilpatrick\estimator_16Jan26\estimator')
from database import DatabaseManager
db = DatabaseManager(r'C:\Users\Consar-Kilpatrick\Desktop\Atlantic Catering School\Project Database\Atlantic Catering School.db')
for r in db.get_rates_data():
    if r['rate_code'] in ['ETWK1A', 'ETWK1D', 'ETWK1E']:
        est = db.load_estimate_details(r['id'])
        print(f"{r['rate_code']}: exrates={est.exchange_rates}")
        for task in est.tasks:
            for item in task.all_items:
                name = item.get('name', item.get('trade', ''))
                cost = item.get('unit_cost', item.get('rate', 0))
                curr = item.get('currency', '')
                print(f"  {name}: {cost:.4f} {curr}")
