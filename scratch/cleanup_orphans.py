"""Clean up orphan exchange rates from estimates that are already correctly in USD."""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r'c:\Users\Consar-Kilpatrick\estimator_16Jan26\estimator')

from database import DatabaseManager
DB_PATH = r'C:\Users\Consar-Kilpatrick\Desktop\Atlantic Catering School\Project Database\Atlantic Catering School.db'
db = DatabaseManager(DB_PATH)

# These estimates have resources correctly in USD but still have exchange rate records
ORPHAN_RATES = ['ETWK1A', 'ETWK1B', 'ETWK1C', 'ETWK1D', 'ETWK1E']

for rate_code in ORPHAN_RATES:
    rates_data = [r for r in db.get_rates_data() if r['rate_code'] == rate_code]
    if not rates_data:
        continue
    
    est = db.load_estimate_details(rates_data[0]['id'])
    if not est:
        continue
    
    if est.exchange_rates:
        print(f"{rate_code}: Removing orphan exchange rates {est.exchange_rates}")
        est.exchange_rates = {}
        db.save_estimate(est)
        print(f"  ✅ Cleaned")
    else:
        print(f"{rate_code}: No exchange rates (already clean)")
