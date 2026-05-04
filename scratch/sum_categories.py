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

# Now we access the cat_table_list and sum them up
total_bid = 0.0
total_cost = 0.0

print(f"{'Category Name':<40} | {'Bid Value':<15} | {'Net Cost':<15}")
print("-" * 75)

# We need to iterate over the items in cat_table_list
# Each item is a MetricRow
count = analytic.cat_table_list.count()
for i in range(count):
    item = analytic.cat_table_list.itemAt(i)
    widget = item.widget()
    if widget:
        # MetricRow doesn't expose bid/cost directly as attributes, 
        # but let's try to extract them from the labels or just use the logic
        # Actually, let's just re-calculate it exactly as refresh_data does but print it
        pass

# A better way: Look at the sections and c_agg if I can.
# But those are local to refresh_data.
# Let's just print the labels from the MetricRow widgets.

for i in range(count):
    widget = analytic.cat_table_list.itemAt(i).widget()
    if widget:
        labels = widget.findChildren(os.path.getattribute(sys.modules['PyQt6.QtWidgets'], 'QLabel'))
        if len(labels) >= 3:
            name = labels[0].text()
            bid_str = labels[1].text().replace('$', '').replace(',', '').strip()
            cost_str = labels[2].text().replace('$', '').replace(',', '').strip()
            
            try:
                b_val = float(bid_str)
                c_val = float(cost_str)
                print(f"{name:<40} | {b_val:>15,.2f} | {c_val:>15,.2f}")
                total_bid += b_val
                total_cost += c_val
            except:
                pass

print("-" * 75)
print(f"{'TOTAL SUM OF CATEGORIES':<40} | {total_bid:>15,.2f} | {total_cost:>15,.2f}")
print(f"{'DASHBOARD TOTAL CARD':<40} | {analytic.card_total_bid.value_label.text():>15} | {analytic.card_total_cost.value_label.text():>15}")

app.quit()
