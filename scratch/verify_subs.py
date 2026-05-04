import sys
import os
from PyQt6.QtWidgets import QApplication, QLabel

sys.path.append(os.getcwd())
from analytics_financial_executive import FinancialExecutiveAnalytic

app = QApplication(sys.argv)
project_dir = r"C:\Users\Consar-Kilpatrick\Desktop\Atlantic Catering School"
analytic = FinancialExecutiveAnalytic(project_dir)

print("--- SUB-CONTRACTOR AUDIT ---")
count = analytic.sub_table_list.count()
print(f"Sub-Contractor Table Rows: {count-1}") # -1 for stretch

for i in range(count):
    item = analytic.sub_table_list.itemAt(i)
    if item and item.widget():
        labels = item.widget().findChildren(QLabel)
        if len(labels) >= 2:
            print(f"Row: {labels[0].text()} | Bid: {labels[1].text()}")

print("\n--- CATEGORICAL OVERRIDE CHECK ---")
count_cat = analytic.cat_table_list.count()
for i in range(count_cat):
    item = analytic.cat_table_list.itemAt(i)
    if item and item.widget():
        name = item.widget().findChildren(QLabel)[0].text()
        if "Sub:" in name:
            print(f"Overridden Category Found: {name}")

app.quit()
