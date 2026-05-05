import pytest
import os
import sys

# Add current directory to path so we can import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def calculate_bid(base_cost, overhead_pct, profit_pct, factor):
    """Mirroring the logic in StrategicBiddingAnalytic."""
    # Bid = Cost * (1 + O%) * (1 + P%) * Factor
    bid = base_cost * (1 + overhead_pct/100) * (1 + profit_pct/100) * factor
    return round(bid, 2)

def calculate_profit(base_cost, overhead_pct, profit_pct, factor):
    """Mirroring the logic in StrategicBiddingAnalytic."""
    bid = calculate_bid(base_cost, overhead_pct, profit_pct, factor)
    overhead_amt = base_cost * (overhead_pct/100) * factor
    profit_amt = bid - (base_cost * factor) - overhead_amt
    return round(profit_amt, 2)

def test_what_if_math_standard():
    base_cost = 1000.0
    overhead = 15.0
    profit = 10.0
    factor = 1.0
    
    # Expected Bid = 1000 * 1.15 * 1.10 * 1.0 = 1265.0
    assert calculate_bid(base_cost, overhead, profit, factor) == 1265.0
    
    # Expected Overhead = 1000 * 0.15 * 1.0 = 150.0
    # Expected Profit = 1265.0 - 1000.0 - 150.0 = 115.0
    assert calculate_profit(base_cost, overhead, profit, factor) == 115.0

def test_what_if_math_with_factor():
    base_cost = 1000.0
    overhead = 10.0
    profit = 5.0
    factor = 1.1 # 10% inflation
    
    # Expected Bid = 1000 * 1.10 * 1.05 * 1.1 = 1270.5
    assert calculate_bid(base_cost, overhead, profit, factor) == 1270.5
    
    # Expected Overhead = 1000 * 0.10 * 1.1 = 110.0
    # Expected Base = 1000 * 1.1 = 1100.0
    # Expected Profit = 1270.5 - 1100.0 - 110.0 = 60.5
    assert calculate_profit(base_cost, overhead, profit, factor) == 60.5

def test_zero_base_cost():
    assert calculate_bid(0, 15, 10, 1.0) == 0.0
    assert calculate_profit(0, 15, 10, 1.0) == 0.0

if __name__ == "__main__":
    pytest.main([__file__])
