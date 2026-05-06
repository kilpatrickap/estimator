import os
import sqlite3
import pytest
from PyQt6.QtWidgets import QApplication
import sys
import shutil

# Ensure the estimator directory is in the path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "estimator")))

from analytics_components import get_project_currency_info, get_project_currency_symbol
from analytics_financial_executive import FinancialExecutiveAnalytic
from analytics_historical_benchmarking import HistoricalBenchmarkingAnalytic

@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
    yield app

@pytest.fixture
def mock_project():
    base_temp = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scratch", "test_tmp"))
    if not os.path.exists(base_temp): os.makedirs(base_temp)
    
    project_dir = os.path.join(base_temp, "MockProject")
    if os.path.exists(project_dir):
        shutil.rmtree(project_dir)
    
    pj_db_dir = os.path.join(project_dir, "Project Database")
    os.makedirs(pj_db_dir)
    
    db_path = os.path.join(pj_db_dir, "mock_project.db")
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE settings (key TEXT, value TEXT)")
    cursor.execute("INSERT INTO settings VALUES ('currency', 'GHS (₵)')")
    cursor.execute("CREATE TABLE estimates (id INTEGER PRIMARY KEY, currency TEXT)")
    cursor.execute("INSERT INTO estimates (id, currency) VALUES (1, 'GHS (₵)')")
    conn.commit()
    conn.close()
    
    return str(project_dir)

def test_currency_symbol_extraction(mock_project):
    symbol = get_project_currency_symbol(mock_project)
    assert symbol == "₵"

def test_financial_executive_currency_load(qapp, mock_project):
    analytic = FinancialExecutiveAnalytic(mock_project)
    assert analytic.currency_symbol.strip() == "₵"

def test_alternate_currency_format():
    base_temp = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scratch", "test_tmp"))
    project_dir = os.path.join(base_temp, "AltProject")
    if os.path.exists(project_dir):
        shutil.rmtree(project_dir)
    
    pj_db_dir = os.path.join(project_dir, "Project Database")
    os.makedirs(pj_db_dir)
    
    db_path = os.path.join(pj_db_dir, "alt_project.db")
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE settings (key TEXT, value TEXT)")
    cursor.execute("INSERT INTO settings VALUES ('currency', 'USD ($)')")
    conn.commit()
    conn.close()
    
    symbol = get_project_currency_symbol(str(project_dir))
    assert symbol == "$"

def test_historical_benchmarking_conversion(qapp):
    base_temp = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scratch", "test_tmp"))
    if not os.path.exists(base_temp): os.makedirs(base_temp)
    
    # 1. Current Project (Base GHS)
    curr_proj = os.path.join(base_temp, "CurrProj")
    if os.path.exists(curr_proj): shutil.rmtree(curr_proj)
    os.makedirs(os.path.join(curr_proj, "Project Database"))
    
    db_path = os.path.join(curr_proj, "Project Database", "curr.db")
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("CREATE TABLE settings (key TEXT, value TEXT)")
    c.execute("INSERT INTO settings VALUES ('currency', 'GHS (₵)')")
    c.execute("CREATE TABLE estimates (id INTEGER PRIMARY KEY, currency TEXT)")
    c.execute("INSERT INTO estimates (id, currency) VALUES (1, 'GHS (₵)')")
    c.execute("CREATE TABLE estimate_exchange_rates (currency TEXT, rate FLOAT, operator TEXT, date TEXT)")
    # 1 USD = 15.5 GHS -> Base(GHS) / 15.5 = USD. Operator='/' means Base = Foreign * Rate
    c.execute("INSERT INTO estimate_exchange_rates VALUES ('USD', 15.5, '/', '2026-01-01')")
    # Add a current rate for the item to trigger the variance calculation
    # Using correct schema from boq_setup.py
    c.execute('CREATE TABLE pboq_items ("Description" TEXT, "Unit" TEXT, "Bill Rate" TEXT, "RateCode" TEXT)')
    c.execute("INSERT INTO pboq_items VALUES ('test item', 'm2', '200.0', 'C1')")
    conn.commit()
    conn.close()
    
    # 2. Historical Project (Base USD)
    hist_proj = os.path.join(base_temp, "HistProj")
    if os.path.exists(hist_proj): shutil.rmtree(hist_proj)
    os.makedirs(os.path.join(hist_proj, "Project Database"))
    
    h_db_path = os.path.join(hist_proj, "Project Database", "hist.db")
    conn = sqlite3.connect(h_db_path)
    c = conn.cursor()
    c.execute("CREATE TABLE settings (key TEXT, value TEXT)")
    c.execute("INSERT INTO settings VALUES ('currency', 'USD ($)')")
    c.execute("CREATE TABLE estimates (id INTEGER PRIMARY KEY, currency TEXT)")
    c.execute("INSERT INTO estimates (id, currency) VALUES (1, 'USD ($)')")
    # pboq_items
    c.execute('CREATE TABLE pboq_items ("Description" TEXT, "Unit" TEXT, "Bill Rate" TEXT, "RateCode" TEXT)')
    c.execute("INSERT INTO pboq_items VALUES ('test item', 'm2', '10.0', 'H1')")
    conn.commit()
    conn.close()
    
    # 3. Test Analytic
    analytic = HistoricalBenchmarkingAnalytic(curr_proj)
    # Mock portfolio selection
    analytic.selected_benchmark_files = [ h_db_path ]
    analytic.refresh_data()
    
    # Verify conversion: 10.0 USD should be 155.0 GHS
    found = False
    for desc, entries in analytic.all_benchmarks.items():
        if desc == 'test item':
            hist_entries = [e for e in entries if e['project'] != 'CURRENT']
            if hist_entries:
                found = True
                # Check for float equality with small tolerance
                assert abs(hist_entries[0]['rate'] - 155.0) < 0.001
    assert found
