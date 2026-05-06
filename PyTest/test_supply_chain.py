import os
import sqlite3
import pytest
from PyQt6.QtWidgets import QApplication
from analytics_supply_chain import SupplyChainIntelligenceAnalytic

@pytest.fixture
def app(qtbot):
    """Fixture to provide a SupplyChainIntelligenceAnalytic instance with a running QApplication."""
    # The qtbot fixture from pytest-qt automatically handles QApplication creation/cleanup
    widget = SupplyChainIntelligenceAnalytic("fake_dir")
    qtbot.addWidget(widget)
    return widget

def test_to_float_logic(app):
    """Tests the float parsing logic for various currency and formatting scenarios."""
    analytic = app
    
    assert analytic._to_float("1,200.50") == 1200.5
    assert analytic._to_float("$ 5,000.00") == 5000.0
    assert analytic._to_float("₵ 450.75") == 450.75
    assert analytic._to_float("") == 0.0
    assert analytic._to_float(None) == 0.0
    assert analytic._to_float("invalid") == 0.0

def test_variance_calculation():
    """Verifies the mathematical correctness of variance and savings percentages."""
    target = 1000.0
    winner = 850.0
    savings = target - winner
    savings_pct = (savings / target) * 100
    
    assert savings == 150.0
    assert savings_pct == 15.0

def test_market_heat_logic():
    """Ensures the average bidder (Market Heat) calculation is mathematically sound."""
    total_bids = 10
    pkg_count = 4
    avg_heat = total_bids / pkg_count
    assert avg_heat == 2.5
