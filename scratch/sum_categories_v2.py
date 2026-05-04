import sys
import os
import sqlite3
from PyQt6.QtWidgets import QApplication, QLabel

# Add project root to path
sys.path.append(os.getcwd())

from analytics_financial_executive import FinancialExecutiveAnalytic

app = QApplication(sys.argv)
project_dir = r"C:\Users\Consar-Kilpatrick\Desktop\Atlantic Catering School"
analytic = FinancialExecutiveAnalytic(project_dir)

total_bid = 0.0
total_cost = 0.0

print(f"{'Category Name':<40} | {'Bid Value':<15} | {'Net Cost':<15}")
print("-" * 75)

count = analytic.cat_table_list.count()
for i in range(count):
    item = analytic.cat_table_list.itemAt(i)
    if not item: continue
    widget = item.widget()
    if widget:
        labels = widget.findChildren(QLabel)
        if len(labels) >= 3:
            name = labels[0].text().replace('Category: ', '')
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
