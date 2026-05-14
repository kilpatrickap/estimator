import sys
import os
import pytest

# Add the project directory to sys.path so we can import the modules
project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_dir)

from analytics_financial_executive import FinancialExecutiveAnalytic
from PyQt6.QtWidgets import QApplication

def test_subcontractor_analysis_bid_amount():
    """
    Tests that the Sub-Contractor Analysis correctly uses the BOQ target/bill amount
    instead of the uniformly marked-up cost.
    """
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
        
    db_path = r"C:\Users\Consar-Kilpatrick\Desktop\Atlantic Catering School"
    analytic = FinancialExecutiveAnalytic(db_path)
    
    # We inspect the sub_table_list layout items
    layout = analytic.sub_table_list
    
    # Check if the row for Waterproofing exists and has correct amounts
    found_waterproofing = False
    for i in range(layout.count()):
        item = layout.itemAt(i)
        if item and item.widget():
            widget = item.widget()
            # If it's a MetricRow and has the correct elements
            if hasattr(widget, 'findChildren'):
                labels = widget.findChildren(type(analytic.card_total_bid).mro()[1]) # Not a direct way to find QLabel, let's use exact class matching
                
                from PyQt6.QtWidgets import QLabel
                labels = widget.findChildren(QLabel)
                
                # We need to extract the raw strings
                texts = [lbl.text() for lbl in labels]
                
                if any("Waterproofing" in t for t in texts):
                    found_waterproofing = True
                    
                    # Based on the BOQ data, the target (Bid Amount) should be 7606.50
                    # and Net Cost should be 6915.00
                    has_correct_bid = any("7,606.50" in t for t in texts)
                    has_correct_cost = any("6,915.00" in t for t in texts)
                    
                    assert has_correct_bid, f"Expected Target Bid of 7,606.50 not found in Waterproofing row. Texts: {texts}"
                    assert has_correct_cost, f"Expected Net Cost of 6,915.00 not found in Waterproofing row. Texts: {texts}"

    assert found_waterproofing, "Waterproofing sub-contractor row was not found in the Sub-Contractor Analysis table."

