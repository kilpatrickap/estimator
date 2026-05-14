import sys
import os
import pytest
from PyQt6.QtWidgets import QApplication

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from analytics_supply_chain import SupplyChainIntelligenceAnalytic

@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app

def test_bid_spread_chart_currency(qapp):
    # Using the project directory
    project_dir = r"C:\Users\Consar-Kilpatrick\Desktop\Atlantic Catering School"
    
    analytic = SupplyChainIntelligenceAnalytic(project_dir)
    
    # Check if the currency_symbol in the chart matches the one in analytic
    assert analytic.spread_chart.currency_symbol == analytic.currency_symbol.strip(), \
        "BidSpreadChart did not receive the correct project currency symbol."
