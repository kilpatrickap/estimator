import sys
import os
from PyQt6.QtWidgets import QApplication, QLabel

sys.path.append(os.getcwd())
from analytics_financial_executive import FinancialExecutiveAnalytic

app = QApplication(sys.argv)
project_dir = r"C:\Users\Consar-Kilpatrick\Desktop\Atlantic Catering School"
analytic = FinancialExecutiveAnalytic(project_dir)

print("--- CATEGORICAL AUDIT ---")
count = analytic.cat_table_list.count()
for i in range(count):
    item = analytic.cat_table_list.itemAt(i)
    if item and item.widget():
        labels = item.widget().findChildren(QLabel)
        if len(labels) >= 2:
            print(f"Category: {labels[0].text()} | Bid: {labels[1].text()}")

app.quit()
