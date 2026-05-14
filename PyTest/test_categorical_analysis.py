import sys
import os
import pytest

project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_dir)

from analytics_financial_executive import FinancialExecutiveAnalytic
from PyQt6.QtWidgets import QApplication, QLabel

def test_categorical_analysis_subcontract_bid():
    """
    Tests that Sub-Contract packages in the Categorical Analysis table
    retain their BOQ Target bid amount instead of applying a uniform global markup.
    """
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
        
    db_path = r"C:\Users\Consar-Kilpatrick\Desktop\Atlantic Catering School"
    analytic = FinancialExecutiveAnalytic(db_path)
    
    layout = analytic.cat_table_list
    
    found_subcontract = False
    for i in range(layout.count()):
        item = layout.itemAt(i)
        if item and item.widget():
            widget = item.widget()
            if hasattr(widget, 'findChildren'):
                labels = widget.findChildren(QLabel)
                texts = [lbl.text() for lbl in labels]
                
                # Check if it's the Waterproofing sub-contract category
                if any("Sub-Contract" in t and "Waterproofing" in t for t in texts):
                    found_subcontract = True
                    
                    # Based on BOQ, Target Bid = 7,606.50
                    has_correct_bid = any("7,606.50" in t for t in texts)
                    
                    assert has_correct_bid, f"Expected BOQ Target Bid of 7,606.50 not found. Instead got: {texts}"

    assert found_subcontract, "Sub-Contract Waterproofing row was not found in Categorical Analysis table."
