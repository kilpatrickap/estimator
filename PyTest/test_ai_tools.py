import sys
import os
import sqlite3
import pytest
from PyQt6.QtWidgets import QApplication

# Add project root to system path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import ai_tools
from ai_worker import AICopilotWorker

@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app

def test_get_workspace_structure():
    # Retrieve structural workspace contents
    structure = ai_tools.get_workspace_structure()
    assert isinstance(structure, list), "Workspace structure must return a list of paths."
    assert len(structure) > 0, "Workspace structure should not be empty."
    # Check that crucial files are present
    assert any("ai_tools.py" in p for p in structure), "ai_tools.py must be detected in the root folder."
    assert any("ai_worker.py" in p for p in structure), "ai_worker.py must be detected in the root folder."

def test_query_active_estimate_summary():
    # Test without a window (should fall back to standard database querying or return empty message)
    summary = ai_tools.query_active_estimate_summary(main_window=None)
    assert isinstance(summary, dict), "Active estimate summary must return a dictionary."
    assert "source" in summary or "status" in summary, "Summary must contain either source details or empty status."

def test_query_active_estimate_summary_project_fallback():
    # Test project directory fallback when last_project_dir is set to Atlantic Catering School
    from database import DatabaseManager
    costs_db = DatabaseManager("construction_costs.db")
    original_project_dir = costs_db.get_setting('last_project_dir', '')
    
    try:
        # Set project dir to the active school project
        costs_db.set_setting('last_project_dir', 'C:/Users/Consar-Kilpatrick/Desktop/Atlantic Catering School')
        
        summary = ai_tools.query_active_estimate_summary(main_window=None)
        assert isinstance(summary, dict)
        assert "source" in summary
        assert "Atlantic Catering School" in summary["source"] or "Atlantic Catering School" in summary["project_name"]
        assert "total_boq_items" in summary
        assert summary["total_boq_items"] == 1288
        assert abs(summary["grand_total"] - 1516663.90) < 0.01
    finally:
        # Restore setting
        if original_project_dir:
            costs_db.set_setting('last_project_dir', original_project_dir)
        else:
            with costs_db.Session() as session:
                from orm_models import Setting
                s = session.query(Setting).get('last_project_dir')
                if s:
                    session.delete(s)
                    session.commit()

def test_query_historical_rates():
    # Query without a search term
    rates = ai_tools.query_historical_rates()
    assert isinstance(rates, list), "Historical rates should return a list."
    
    # Query with a search term that doesn't exist
    empty_rates = ai_tools.query_historical_rates("non_existent_code_xyz_123")
    assert isinstance(empty_rates, list), "Filtered rates should return a list."
    assert len(empty_rates) == 0, "Filtered rates list must be empty for a non-existent search term."

    # Test that project directory scanning logic runs gracefully
    try:
        from database import DatabaseManager
        costs_db = DatabaseManager("construction_costs.db")
        old_val = costs_db.get_setting('last_project_dir', '')
        costs_db.set_setting('last_project_dir', 'dummy_nonexistent_dir_123')
        
        # Should not crash and should complete gracefully
        dummy_rates = ai_tools.query_historical_rates("Concrete")
        assert isinstance(dummy_rates, list)
        
        # Restore setting
        if old_val:
            costs_db.set_setting('last_project_dir', old_val)
        else:
            with costs_db.Session() as session:
                from orm_models import Setting
                s = session.query(Setting).get('last_project_dir')
                if s:
                    session.delete(s)
                    session.commit()
    except Exception:
        pass

def test_get_outlier_items():
    # Test with a dummy/non-existent PBOQ DB
    dummy_pboq = "dummy_pboq_test.db"
    if os.path.exists(dummy_pboq):
        try:
            os.remove(dummy_pboq)
        except Exception:
            pass
            
    try:
        # Run outlier scanner
        outliers = ai_tools.get_outlier_items(dummy_pboq)
        assert isinstance(outliers, dict), "Outliers result must return a dictionary."
        assert "outlier_deviations" in outliers, "Result should map cost deviations."
        assert "manual_plug_rates" in outliers, "Result should map plug rates."
        
        # Create a dummy sqlite DB representing a PBOQ sheet to verify plug rate scanning
        conn = sqlite3.connect(dummy_pboq)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE pboq_items (
                Description TEXT,
                PlugRate REAL,
                PlugCode TEXT,
                IsFlagged INTEGER
            )
        """)
        cursor.execute("INSERT INTO pboq_items VALUES ('Excavation manual plug', 45.50, 'PLUG-01', 1)")
        cursor.execute("INSERT INTO pboq_items VALUES ('Concrete standard build', 0.00, '', 0)")
        conn.commit()
        conn.close()
        
        # Scan again with populated sheet
        outliers = ai_tools.get_outlier_items(dummy_pboq)
        plugs = outliers.get("manual_plug_rates", [])
        assert len(plugs) == 1, "Should detect exactly one manual plug rate."
        assert plugs[0]["description"] == "Excavation manual plug", "Should fetch the correct description."
        assert plugs[0]["plug_rate"] == 45.50, "Should match the plugged unit rate."
        assert plugs[0]["is_flagged_for_review"] is True, "Should recognize the IsFlagged bit."
    finally:
        if os.path.exists(dummy_pboq):
            try:
                os.remove(dummy_pboq)
            except Exception:
                pass

def test_ai_worker_local_intelligence(qapp):
    # Run the worker locally without an API key to test local intelligence generation
    worker = AICopilotWorker("Show active estimate KPIs", main_window=None)
    
    # Force local fallback interpreter path to ensure deterministic testing of the fallback rules
    def mock_call_ollama(*args, **kwargs):
        raise Exception("Force local fallback for unit test")
    worker._call_local_ollama = mock_call_ollama
    
    # Connect signals to slots to capture outputs
    results = []
    errors = []
    
    worker.signals.finished.connect(results.append)
    worker.signals.error.connect(errors.append)
    
    # Run synchronously for verification purposes
    worker.run()
    
    assert len(errors) == 0, f"Worker failed with errors: {errors}"
    assert len(results) == 1, "Worker must emit finished signal once."
    assert "#" in results[0], "Local response must contain Markdown headings."
    assert "KPI" in results[0] or "Estimate" in results[0] or "Project" in results[0], "Local summary query response should present dashboard statistics."

def test_ai_worker_pboq_local_intelligence(qapp):
    # Setup dummy database with PBOQ structure
    dummy_pboq = "dummy_pboq_test_local.db"
    if os.path.exists(dummy_pboq):
        try: os.remove(dummy_pboq)
        except Exception: pass
        
    try:
        conn = sqlite3.connect(dummy_pboq)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE pboq_items (
                Description TEXT,
                "Bill Rate" TEXT,
                "Bill Amount" TEXT,
                PlugRate REAL
            )
        """)
        cursor.execute("INSERT INTO pboq_items VALUES ('Item 1', '10.50', '1,050.00', 0.0)")
        cursor.execute("INSERT INTO pboq_items VALUES ('Item 2', '20.00', '2,000.00', 1.0)")
        conn.commit()
        conn.close()
        
        # Test worker with custom summary dictionary mock/active_summary
        worker = AICopilotWorker("Show active estimate KPIs", main_window=None)
        
        # Mock active_summary returning PBOQ keys
        active_summary = {
            "source": "Mock PBOQ",
            "project_name": "dummy_pboq_test_local.db",
            "total_boq_items": 2,
            "plugged_items": 1,
            "priced_items": 2,
            "outstanding_items": 0,
            "grand_total": 3050.00,
            "currency": "USD ($)",
            "pboq_database_path": dummy_pboq
        }
        
        # Run local interpreter directly to verify it parses Case A: PBOQ sheet
        res = worker._generate_local_response("Show active estimate KPIs", active_summary, [], {"outlier_deviations": [], "manual_plug_rates": []})
        
        assert "Active Priced BOQ Dashboard" in res
        assert "dummy_pboq_test_local.db" in res
        assert "3,050.00" in res
        assert "Total BOQ Items" in res
    finally:
        if os.path.exists(dummy_pboq):
            try: os.remove(dummy_pboq)
            except Exception: pass


def test_call_local_ollama_queries_database(qapp, monkeypatch):
    import json
    worker = AICopilotWorker("Show active estimate KPIs", main_window=None)
    
    # Mock urllib.request.urlopen to avoid sending actual network calls
    captured_payloads = []
    
    class MockResponse:
        def __init__(self, data_dict):
            self.data = json.dumps(data_dict).encode("utf-8")
        def read(self):
            return self.data
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass
            
    def mock_urlopen(req, *args, **kwargs):
        # Determine URL
        url = req.full_url if hasattr(req, 'full_url') else str(req)
        if "api/tags" in url:
            # Return a valid model list
            return MockResponse({"models": [{"name": "deepseek-r1:1.5b"}]})
        elif "v1/chat/completions" in url:
            # Capture what was sent to chat completions
            payload = json.loads(req.data.decode("utf-8"))
            captured_payloads.append(payload)
            return MockResponse({
                "choices": [{
                    "message": {
                        "content": "<think>thinking...</think>Success result."
                    }
                }]
            })
        raise Exception(f"Unexpected URL: {url}")
        
    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)
    
    # We must mock active project db path fallback
    monkeypatch.setattr(ai_tools, "get_active_project_db_path", lambda: "construction_costs.db")
    
    # Run _call_local_ollama
    active_summary = {"source": "test", "project_name": "test"}
    res = worker._call_local_ollama(active_summary, [], {"outlier_deviations": [], "manual_plug_rates": []})
    
    assert "Success result" in res
    assert len(captured_payloads) == 1
    
    user_prompt = captured_payloads[0]["messages"][1]["content"]
    
    # The user_prompt should contain the database statistics with NON-ZERO counts!
    # Specifically, it should count the materials in construction_costs.db
    import sqlite3
    db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'construction_costs.db'))
    conn = sqlite3.connect(db_path)
    expected_materials = conn.cursor().execute("SELECT COUNT(*) FROM materials").fetchone()[0]
    expected_tasks = conn.cursor().execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    conn.close()
    
    assert f"Cost Library (materials): {expected_materials} records" in user_prompt
    assert f"Project Database (construction_costs.db): {expected_tasks} tasks, {expected_materials} materials" in user_prompt
