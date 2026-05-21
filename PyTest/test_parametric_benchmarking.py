# PyTest/test_parametric_benchmarking.py

import sys
import os
import pytest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from analytics_cost_modelling import ParametricBenchmarkingAnalytic

@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app

def test_parametric_widget_initialization(qapp):
    project_dir = r"C:\Users\Consar-Kilpatrick\Desktop\Atlantic Catering School"
    analytic = ParametricBenchmarkingAnalytic(project_dir)
    
    assert analytic is not None
    assert analytic.currency_symbol in ["$", "₵", "GH¢", "€", "£"]
    
def test_parametric_calculations(qapp):
    project_dir = r"C:\Users\Consar-Kilpatrick\Desktop\Atlantic Catering School"
    analytic = ParametricBenchmarkingAnalytic(project_dir)
    
    # Set standard options
    analytic.gfa_slider.setValue(200)
    analytic.type_combo.setCurrentText("Residential House")
    analytic.region_combo.setCurrentIndex(0) # Accra (1.0x)
    analytic.spec_combo.setCurrentIndex(0)   # Standard (1.0x)
    analytic.comp_combo.setCurrentIndex(0)   # Simple (1.0x)
    analytic.site_combo.setCurrentIndex(0)   # Flat (1.0x)
    analytic.wet_spin.setValue(0)            # 0 wet areas
    
    # Trigger refresh
    analytic.refresh_calculations()
    
    # 200 m2 of Residential (750 baseline) under standard = 750 / m2
    # Simulated Rate should be exactly 750.0
    sim_rate_str = analytic.card_sim_rate.value_label.text()
    assert "750" in sim_rate_str.replace(",", "")
    
    sim_total_str = analytic.card_sim_total.value_label.text()
    assert "150000" in sim_total_str.replace(",", "")

def test_slider_updates_labels(qapp):
    project_dir = r"C:\Users\Consar-Kilpatrick\Desktop\Atlantic Catering School"
    analytic = ParametricBenchmarkingAnalytic(project_dir)
    
    analytic.gfa_slider.setValue(500)
    assert analytic.gfa_val_lbl.text() == "500 m²"
    
def test_breakdown_drivers_match_total(qapp):
    project_dir = r"C:\Users\Consar-Kilpatrick\Desktop\Atlantic Catering School"
    analytic = ParametricBenchmarkingAnalytic(project_dir)
    
    # Let's check if sum of breakdown chart equals total simulated rate
    analytic.gfa_slider.setValue(100)
    analytic.wet_spin.setValue(2)
    analytic.refresh_calculations()
    
    driver_sum = sum(d[1] for d in analytic.breakdown_chart.cost_drivers)
    # The value shown in card_sim_rate is simulated_rate
    # Let's extract simulated_rate directly from the calculation output
    # or assert driver_sum is non-zero
    assert driver_sum > 0
    # Retrieve simulated rate
    card_rate = float(analytic.card_sim_rate.value_label.text().replace(analytic.currency_symbol, "").replace(",", "").strip())
    assert abs(driver_sum - card_rate) < 0.01

def test_parametric_currency_conversion(qapp):
    project_dir = r"C:\Users\Consar-Kilpatrick\Desktop\Atlantic Catering School"
    analytic = ParametricBenchmarkingAnalytic(project_dir)
    
    # 1. Base case: USD
    analytic.currency_code = "USD"
    analytic.currency_symbol = "$"
    analytic.gfa_slider.setValue(200)
    analytic.type_combo.setCurrentText("Residential House")
    analytic.region_combo.setCurrentIndex(0) # Accra (1.0x)
    analytic.spec_combo.setCurrentIndex(0)   # Standard (1.0x)
    analytic.comp_combo.setCurrentIndex(0)   # Simple (1.0x)
    analytic.site_combo.setCurrentIndex(0)   # Flat (1.0x)
    analytic.wet_spin.setValue(0)
    analytic.refresh_calculations()
    
    usd_rate = float(analytic.card_sim_rate.value_label.text().replace("$", "").replace(",", "").strip())
    assert abs(usd_rate - 750.0) < 0.01
    
    # 2. Switch to GHS (₵) with a fallback exchange rate of 15.0
    analytic.currency_code = "GHS"
    analytic.currency_symbol = "₵"
    analytic.refresh_calculations()
    
    ghs_rate = float(analytic.card_sim_rate.value_label.text().replace("₵", "").replace(",", "").strip())
    # Should be scaled by 15.0: 750.0 * 15.0 = 11250.0
    assert abs(ghs_rate - 11250.0) < 0.01

