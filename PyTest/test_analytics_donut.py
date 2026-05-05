import pytest
import os
import sqlite3
import json
from PyQt6.QtWidgets import QApplication
from analytics_project_performance import ProjectPerformanceAnalytic

# Mocking PBOQLogic to avoid dependencies during test
from pboq_logic import PBOQLogic

@pytest.fixture
def temp_project(tmp_path):
    # Create project structure
    project_dir = tmp_path / "test_project"
    project_dir.mkdir()
    
    pboq_dir = project_dir / "Priced BOQs"
    pboq_dir.mkdir()
    
    # Create PBOQ States directory to avoid mapping errors
    states_dir = project_dir / "PBOQ States"
    states_dir.mkdir()
    
    # Create a dummy PBOQ database
    db_path = pboq_dir / "test_boq.db"
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # Create table with expected columns
    cursor.execute("""
        CREATE TABLE pboq_items (
            Sheet TEXT,
            Description TEXT,
            Unit TEXT,
            Quantity TEXT,
            "Bill Amount" TEXT,
            GrossRate TEXT,
            PlugRate TEXT,
            SubbeeRate TEXT,
            ProvSum TEXT,
            PCSum TEXT,
            Daywork TEXT,
            IsFlagged INTEGER DEFAULT 0
        )
    """)
    
    # Insert test data with various price types and formats
    items = [
        # Sheet, Desc, Unit, Qty, Bill Amt, Gross, Plug, Sub, Prov, PC, Daywork
        ("Sheet1", "Gross Item", "m2", "10", "1,000.00", "R01", "", "", "", "", ""), 
        ("Sheet1", "Plug Item", "nr", "5", "500.00", "", "P01", "", "", "", ""),
        ("Sheet2", "Sub Item", "item", "1", "2,000.00", "", "", "S01", "", "", ""),
        ("Sheet2", "Prov Item", "sum", "1", "GHS 300.00", "", "", "", "PR01", "", ""),
        ("Sheet3", "PC Item", "sum", "1", "₵ 150.00", "", "", "", "", "PC01", ""),
        ("Sheet3", "Daywork Item", "hr", "4", "100.00", "", "", "", "", "", "DW01"),
    ]
    
    for item in items:
        cursor.execute("""
            INSERT INTO pboq_items (Sheet, Description, Unit, Quantity, "Bill Amount", GrossRate, PlugRate, SubbeeRate, ProvSum, PCSum, Daywork)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, item)
    
    conn.commit()
    conn.close()
    
    # Create a dummy state file to ensure mappings are picked up
    state_file = states_dir / "test_boq.db.json"
    state_data = {
        "mappings": {
            "desc": 0,
            "unit": 1,
            "qty": 2,
            "bill_amount": 3
        }
    }
    with open(state_file, 'w') as f:
        json.dump(state_data, f)
    
    return project_dir

def test_analytics_donut_data_aggregation(qtbot, temp_project):
    # Initialize analytic with the temporary project directory
    analytic = ProjectPerformanceAnalytic(str(temp_project))
    qtbot.addWidget(analytic)
    
    # Manually trigger data refresh
    analytic.refresh_data()
    
    # Verify the cards are updated (Bonus check)
    assert "4,050.00" in analytic.card_total_bid.value_label.text()
    
    # Access the chart data
    chart_data = analytic.mix_chart.data
    
    # Convert list of tuples to dict for easier checking: {label: value}
    results = {label: value for label, value, color in chart_data}
    
    # Check each category's summed value
    assert results["Gross Rates"] == 1000.0
    assert results["Plug Rates"] == 500.0
    assert results["Subcontractor"] == 2000.0
    assert results["Prov. Sums"] == 300.0
    assert results["PC Sums"] == 150.0
    assert results["Dayworks"] == 100.0
    
    # Verify the Pareto Bar Chart data
    bar_data = analytic.mix_bar_chart.data
    assert len(bar_data) == 6
    
    # Check sorting (Pareto effect: highest value first)
    values = [d[1] for d in bar_data]
    assert values == sorted(values, reverse=True)
    
    # Verify specific bar values
    bar_results = {label: value for label, value, color in bar_data}
    assert bar_results["Subcontractor"] == 2000.0
    assert bar_results["Gross Rates"] == 1000.0
    
    # Verify Confidence Card logic (Gross Rates are 1000 out of 4050 total priced)
    # lib_pct = 1000 / 4050 * 100 = ~24.69% -> LOW confidence
    assert "LOW" in analytic.card_confidence.value_label.text()
    assert "24%" in analytic.card_confidence.subtext_label.text()
