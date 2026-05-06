import os
import sqlite3
import pytest
from PyQt6.QtWidgets import QApplication
import sys

# Ensure the estimator directory is in the path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "estimator")))

from analytics_components import get_project_currency_symbol
from analytics_financial_executive import FinancialExecutiveAnalytic

@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
    yield app

@pytest.fixture
def mock_project(tmp_path_factory):
    # Use a local directory to avoid permission issues in C:\Users\...\AppData\Local\Temp
    base_temp = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scratch", "test_tmp"))
    if not os.path.exists(base_temp): os.makedirs(base_temp)
    
    project_dir = os.path.join(base_temp, "MockProject")
    if os.path.exists(project_dir):
        import shutil
        shutil.rmtree(project_dir)
    
    pj_db_dir = os.path.join(project_dir, "Project Database")
    os.makedirs(pj_db_dir)
    
    db_path = os.path.join(pj_db_dir, "mock_project.db")
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE settings (key TEXT, value TEXT)")
    cursor.execute("INSERT INTO settings VALUES ('currency', 'GHS (₵)')")
    conn.commit()
    conn.close()
    
    return str(project_dir)

def test_currency_symbol_extraction(mock_project):
    symbol = get_project_currency_symbol(mock_project)
    assert symbol == "₵"

def test_financial_executive_currency_load(qapp, mock_project):
    analytic = FinancialExecutiveAnalytic(mock_project)
    # The module adds a trailing space for display padding
    assert analytic.currency_symbol.strip() == "₵"

def test_alternate_currency_format():
    base_temp = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scratch", "test_tmp"))
    project_dir = os.path.join(base_temp, "AltProject")
    if os.path.exists(project_dir):
        import shutil
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
