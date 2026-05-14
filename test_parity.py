import os
import sys

# Add current dir to path
sys.path.insert(0, os.path.abspath('.'))

from analytics_strategic_bidding import StrategicBiddingAnalytic
from analytics_financial_executive import FinancialExecutiveAnalytic
from analytics_project_performance import ProjectPerformanceAnalytic
from PyQt6.QtWidgets import QApplication

def test_project():
    app = QApplication(sys.argv)
    project_dir = r"C:\Users\Consar-Kilpatrick\Desktop\Atlantic Catering School"
    
    print("=== Testing Strategic Bidding ===")
    sb = StrategicBiddingAnalytic(project_dir)
    print(f"Base Cost (Constant): {sb.base_cost:.2f}")
    
    # Simulate current state
    curr_bid = sb.base_cost + (sb.base_cost * (sb.current_overhead / 100)) + (sb.base_cost * (sb.current_profit / 100))
    print(f"Current Calculated Final Bid: {curr_bid:.2f}")
    
    print("\n=== Testing Financial Executive ===")
    fe = FinancialExecutiveAnalytic(project_dir)
    print(f"FE Base Cost text: {fe.card_total_cost.value_label.text()}")
    print(f"FE Final Bid text: {fe.card_total_bid.value_label.text()}")

    print("\n=== Testing Project Performance ===")
    pp = ProjectPerformanceAnalytic(project_dir)
    print(f"PP Final Bid text: {pp.card_total_bid.value_label.text()}")

if __name__ == '__main__':
    test_project()
