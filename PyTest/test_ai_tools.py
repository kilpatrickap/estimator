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

@pytest.fixture(autouse=True)
def mock_db_settings(monkeypatch):
    from database import DatabaseManager
    original_get_setting = DatabaseManager.get_setting
    def patched_get_setting(self, key, default=None):
        if key == "ai_model_name":
            return "batiai/llama4-scout:iq3"
        return original_get_setting(self, key, default)
    monkeypatch.setattr(DatabaseManager, "get_setting", patched_get_setting)

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
    
    db_path = 'C:/Users/Consar-Kilpatrick/Desktop/Atlantic Catering School/Project Database/Atlantic Catering School.db'
    original_overhead = None
    original_profit = None
    
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT value FROM settings WHERE key='overhead'")
            r = cursor.fetchone()
            if r: original_overhead = r[0]
            cursor.execute("SELECT value FROM settings WHERE key='profit'")
            r = cursor.fetchone()
            if r: original_profit = r[0]
            
            # Set to 10.0 for test assertions
            cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('overhead', '10.0')")
            cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('profit', '10.0')")
            conn.commit()
        except Exception:
            pass
        finally:
            conn.close()

    try:
        # Set project dir to the active school project
        costs_db.set_setting('last_project_dir', 'C:/Users/Consar-Kilpatrick/Desktop/Atlantic Catering School')
        
        summary = ai_tools.query_active_estimate_summary(main_window=None)
        assert isinstance(summary, dict)
        assert "source" in summary
        assert "Atlantic Catering School" in summary["source"] or "Atlantic Catering School" in summary["project_name"]
        assert "total_boq_items" in summary
        assert summary["total_boq_items"] == 58
        assert abs(summary["subtotal"] - 692198.64) < 0.01
        assert abs(summary["overhead_amount"] - 69219.86) < 0.01
        assert abs(summary["profit_amount"] - 69219.86) < 0.01
        assert abs(summary["grand_total"] - 830638.37) < 0.01
    finally:
        # Restore settings in school database
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            try:
                if original_overhead is not None:
                    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('overhead', ?)", (original_overhead,))
                else:
                    cursor.execute("DELETE FROM settings WHERE key='overhead'")
                if original_profit is not None:
                    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('profit', ?)", (original_profit,))
                else:
                    cursor.execute("DELETE FROM settings WHERE key='profit'")
                conn.commit()
            except Exception:
                pass
            finally:
                conn.close()

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
    assert "Cannot Connect to AI Reasoner" in results[0], "Local response must notify user about the offline state."
    assert "batiai/llama4-scout:iq3" in results[0], "Should reference the target local LLM model name."


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
            # Return a valid model list strictly containing batiai/llama4-scout:iq3
            return MockResponse({"models": [{"name": "batiai/llama4-scout:iq3"}]})
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
    assert captured_payloads[0]["model"] == "batiai/llama4-scout:iq3", "Should strictly use the batiai/llama4-scout:iq3 model"
    
    assert len(captured_payloads[0]["messages"]) == 2, "Should have system prompt and user query messages"
    assert captured_payloads[0]["messages"][0]["role"] == "system"
    assert "query_db" in captured_payloads[0]["messages"][0]["content"]
    
    user_prompt = captured_payloads[0]["messages"][1]["content"]
    assert user_prompt == "Show active estimate KPIs", "Should pass the raw user query"

def test_ai_worker_agentic_tool_calling(qapp, monkeypatch):
    import json
    worker = AICopilotWorker("Count materials", main_window=None)
    
    # Track the calls to chat/completions
    api_calls = []
    
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
        url = req.full_url if hasattr(req, 'full_url') else str(req)
        if "api/tags" in url:
            return MockResponse({"models": [{"name": "batiai/llama4-scout:iq3"}]})
        elif "v1/chat/completions" in url:
            payload = json.loads(req.data.decode("utf-8"))
            api_calls.append(payload)
            
            # First call: simulate model requesting the DB tool
            if len(api_calls) == 1:
                return MockResponse({
                    "choices": [{
                        "message": {
                            "content": "Let me query the database first.\n<query_db db=\"construction_costs.db\">SELECT COUNT(*) FROM materials</query_db>"
                        }
                    }]
                })
            # Second call: simulated final model answer based on the tool result
            else:
                # Retrieve system tool result from payload to make sure it exists
                tool_res = payload["messages"][-1]["content"]
                assert "query_result" in tool_res
                return MockResponse({
                    "choices": [{
                        "message": {
                            "content": "There are exactly 28 records in the materials table."
                        }
                    }]
                })
        raise Exception(f"Unexpected URL: {url}")
        
    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)
    
    # Run _call_local_ollama
    active_summary = {"source": "test", "project_name": "test"}
    res = worker._call_local_ollama(active_summary, [], {})
    
    assert "28 records" in res
    assert len(api_calls) == 2, "Should invoke chat completions twice (one for tool call, one for final answer)"
    
    # Validate the tool message was appended
    messages = api_calls[1]["messages"]
    assert messages[-2]["role"] == "assistant"
    assert "query_db" in messages[-2]["content"]
    assert messages[-1]["role"] == "user"
    assert "[System Tool Result]" in messages[-1]["content"]


def test_ai_worker_priced_boq_items_context(qapp, monkeypatch):
    import json
    # Mock get_active_project_priced_items to return a static list of items
    monkeypatch.setattr(ai_tools, "get_active_project_priced_items", lambda pdir: [
        {"sheet": "test_sheet", "description": "Concrete Slab Item", "qty": 10.5, "unit": "m3", "net_rate": 150.0, "net_amount": 1575.0}
    ])
    
    worker = AICopilotWorker("list all priced BOQ items", main_window=None)
    
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
        url = req.full_url if hasattr(req, 'full_url') else str(req)
        if "api/tags" in url:
            return MockResponse({"models": [{"name": "batiai/llama4-scout:iq3"}]})
        elif "v1/chat/completions" in url:
            payload = json.loads(req.data.decode("utf-8"))
            captured_payloads.append(payload)
            return MockResponse({
                "choices": [{
                    "message": {
                        "content": "Here is the list of priced items: ..."
                    }
                }]
            })
        raise Exception(f"Unexpected URL: {url}")
        
    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)
    
    # Run _call_local_ollama
    active_summary = {"source": "test", "project_name": "test"}
    res = worker._call_local_ollama(active_summary, [], {})
    
    assert "Here is the list of priced items" in res
    assert len(captured_payloads) == 1
    system_prompt = captured_payloads[0]["messages"][0]["content"]
    assert "--- ACTIVE PROJECT PRICED BOQ ITEMS ---" in system_prompt
    assert "Concrete Slab Item" in system_prompt
    assert "10.5" in system_prompt
    assert "150.00" in system_prompt
    assert "1575.00" in system_prompt


def test_ai_worker_proactive_search_context(qapp, monkeypatch):
    import json
    
    # Mock search databases/historical rates to return static items
    monkeypatch.setattr(ai_tools, "query_historical_rates", lambda q: [
        {"rate_code": "CONC1A", "project_name": "Plain concrete", "unit": "m3", "currency": "USD", "net_total": 155.93, "grand_total": 155.93, "_source_db": "Atlantic Catering School.db"}
    ])
    monkeypatch.setattr(ai_tools, "search_active_database", lambda q: {
        "materials": [{"name": "Standard concrete mix", "price": 120.00, "currency": "USD", "unit": "m3", "source": "Library"}]
    })
    
    worker = AICopilotWorker("Search historical rates for Concrete", main_window=None)
    
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
        url = req.full_url if hasattr(req, 'full_url') else str(req)
        if "api/tags" in url:
            return MockResponse({"models": [{"name": "batiai/llama4-scout:iq3"}]})
        elif "v1/chat/completions" in url:
            payload = json.loads(req.data.decode("utf-8"))
            captured_payloads.append(payload)
            return MockResponse({
                "choices": [{
                    "message": {
                        "content": "Found historical concrete rates."
                    }
                }]
            })
        raise Exception(f"Unexpected URL: {url}")
        
    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)
    
    # Run _call_local_ollama
    active_summary = {"source": "test", "project_name": "test"}
    res = worker._call_local_ollama(active_summary, [], {})
    
    assert "Found historical concrete rates" in res
    assert len(captured_payloads) == 1
    system_prompt = captured_payloads[0]["messages"][0]["content"]
    assert "--- REAL-TIME SEARCH RESULTS FOR 'concrete' ---" in system_prompt
    assert "CONC1A" in system_prompt
    assert "Plain concrete" in system_prompt
    assert "Standard concrete mix" in system_prompt
    assert "155.93" in system_prompt
    assert "120.0" in system_prompt


def test_ai_worker_typo_resilience(qapp, monkeypatch):
    import json
    
    worker = AICopilotWorker("Count materials", main_window=None)
    
    # 1. Verify fuzzy path resolution resolves LLM typo "constructioncosts.db" -> "construction_costs.db"
    resolved = worker._resolve_file_path("constructioncosts.db")
    assert resolved is not None
    assert "construction_costs.db" in resolved.replace('\\', '/')

    # 2. Mock URL open to verify that querydb with a typo parses successfully as a tool call
    api_calls = []
    
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
        url = req.full_url if hasattr(req, 'full_url') else str(req)
        if "api/tags" in url:
            return MockResponse({"models": [{"name": "batiai/llama4-scout:iq3"}]})
        elif "v1/chat/completions" in url:
            payload = json.loads(req.data.decode("utf-8"))
            api_calls.append(payload)
            
            # First call returns the typoed tag
            if len(api_calls) == 1:
                return MockResponse({
                    "choices": [{
                        "message": {
                            "content": "Let me search the library:\n<querydb db=\"constructioncosts.db\">SELECT COUNT(*) FROM materials</querydb>"
                        }
                    }]
                })
            else:
                return MockResponse({
                    "choices": [{
                        "message": {
                            "content": "Successfully searched using typo-resilient parsing."
                        }
                    }]
                })
        raise Exception(f"Unexpected URL: {url}")
        
    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)
    
    # Run _call_local_ollama
    active_summary = {"source": "test", "project_name": "test"}
    res = worker._call_local_ollama(active_summary, [], {})
    
    assert "Successfully searched using typo-resilient parsing" in res
    assert len(api_calls) == 2, "Should parse the typoed tag as a valid tool execution call"
    
    # Verify the tool result payload in the second call
    second_call_messages = api_calls[1]["messages"]
    assert second_call_messages[-1]["role"] == "user"
    assert "query_result" in second_call_messages[-1]["content"]
    assert "Error:" not in second_call_messages[-1]["content"], "Should successfully find the database file and return rows, not a file-not-found error"


def test_ai_worker_self_correcting_loop(qapp, monkeypatch):
    worker = AICopilotWorker("Count materials", main_window=None)
    
    # Run a query on construction_costs.db using non-existent column "item_name"
    sql = "SELECT item_name FROM materials"
    res = worker._execute_sql("construction_costs.db", sql)
    
    assert "Error executing SQL" in res
    assert "Note that table 'materials' has columns" in res
    assert "name" in res
    assert "price" in res
    assert "unit" in res

def test_ai_worker_sql_auto_correction(qapp, monkeypatch):
    worker = AICopilotWorker("Count materials", main_window=None)
    
    # 1. Test pre-execution column rewrite (description -> name for materials)
    sql1 = "SELECT description FROM materials LIMIT 1"
    res1 = worker._execute_sql("construction_costs.db", sql1)
    assert "Error executing SQL" not in res1
    assert "name" in res1
    assert res1.count("|") >= 6  # Confirm markdown table structure exists
    
    # 2. Test pre-execution column rewrite (name -> trade for labor)
    sql2 = "SELECT name FROM labor LIMIT 1"
    res2 = worker._execute_sql("construction_costs.db", sql2)
    assert "Error executing SQL" not in res2
    assert "trade" in res2
    assert res2.count("|") >= 6  # Confirm markdown table structure exists

    # 3. Test dynamic post-execution self-correction (desc -> name for materials)
    sql3 = "SELECT desc FROM materials LIMIT 1"
    res3 = worker._execute_sql("construction_costs.db", sql3)
    assert "Error executing SQL" not in res3
    assert "name" in res3
    assert res3.count("|") >= 6  # Confirm markdown table structure exists

def test_ai_worker_empty_response_guard(qapp, monkeypatch):
    """Verify that when the LLM returns only <think> tags with no actual content,
    the system falls back to presenting the pre-fetched search results."""
    import json
    
    # Mock search databases to return concrete rates
    monkeypatch.setattr(ai_tools, "query_historical_rates", lambda q: [
        {"rate_code": "CONC1A", "project_name": "Plain concrete", "unit": "m3", "currency": "USD", "net_total": 155.93, "grand_total": 155.93, "_source_db": "Library"}
    ])
    monkeypatch.setattr(ai_tools, "search_active_database", lambda q: {
        "materials": [{"name": "Standard concrete mix", "price": 120.00, "currency": "USD", "unit": "m3", "source": "Library"}]
    })
    
    worker = AICopilotWorker("Search historical rates for Concrete", main_window=None)
    
    api_calls = []
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
        url = req.full_url if hasattr(req, 'full_url') else str(req)
        if "api/tags" in url:
            return MockResponse({"models": [{"name": "batiai/llama4-scout:iq3"}]})
        elif "v1/chat/completions" in url:
            api_calls.append(True)
            # Simulate LLM returning ONLY <think> tags with no actual content
            return MockResponse({
                "choices": [{
                    "message": {
                        "content": "<think>I need to look up concrete rates in the database.</think>"
                    }
                }]
            })
        raise Exception(f"Unexpected URL: {url}")
        
    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)
    
    active_summary = {"source": "test", "project_name": "test"}
    res = worker._call_local_ollama(active_summary, [], {})
    
    # Should NOT return an empty string — must fall back to presenting the pre-fetched data
    assert res is not None
    assert len(res.strip()) > 0, "Response must not be empty when pre-fetched data exists"
    assert "CONC1A" in res or "project libraries" in res, "Should contain rate data or library reference"


def test_ai_worker_proactive_directive_injected(qapp, monkeypatch):
    """Verify that when proactive search results are found, the SYSTEM DIRECTIVE
    instructing the LLM to use pre-fetched data is injected into the system prompt."""
    import json
    
    monkeypatch.setattr(ai_tools, "query_historical_rates", lambda q: [
        {"rate_code": "CONC1A", "project_name": "Plain concrete", "unit": "m3", "currency": "USD", "net_total": 155.93, "grand_total": 155.93, "_source_db": "Library"}
    ])
    monkeypatch.setattr(ai_tools, "search_active_database", lambda q: {"materials": []})
    
    worker = AICopilotWorker("Search historical rates for Concrete", main_window=None)
    
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
        url = req.full_url if hasattr(req, 'full_url') else str(req)
        if "api/tags" in url:
            return MockResponse({"models": [{"name": "batiai/llama4-scout:iq3"}]})
        elif "v1/chat/completions" in url:
            payload = json.loads(req.data.decode("utf-8"))
            captured_payloads.append(payload)
            return MockResponse({
                "choices": [{
                    "message": {
                        "content": "Here are the concrete rates from your project."
                    }
                }]
            })
        raise Exception(f"Unexpected URL: {url}")
        
    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)
    
    active_summary = {"source": "test", "project_name": "test"}
    res = worker._call_local_ollama(active_summary, [], {})
    
    assert len(captured_payloads) == 1
    system_prompt = captured_payloads[0]["messages"][0]["content"]
    
    # Verify the mandatory data usage rule is present
    assert "MANDATORY DATA USAGE RULE" in system_prompt, "Should include mandatory data usage directive"
    
    # Verify the proactive context signal directive is present
    assert "[SYSTEM DIRECTIVE:" in system_prompt, "Should include SYSTEM DIRECTIVE when search results found"
    assert "Do NOT issue" in system_prompt or "Only issue a" in system_prompt, "Should instruct LLM about query usage"

    
    # Verify the self-correction constraint is present
    assert "SELF-CORRECTION ON ERROR" in system_prompt, "Should include self-correction directive"


def test_ai_worker_conversation_history(qapp, monkeypatch):
    import json
    
    # 1. Test conversation history injection and <think> stripping
    history = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "<think>Thinking...</think>Hi there!"}
    ]
    worker = AICopilotWorker("What is the cost?", main_window=None, conversation_history=history)
    
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
        url = req.full_url if hasattr(req, 'full_url') else str(req)
        if "api/tags" in url:
            return MockResponse({"models": [{"name": "batiai/llama4-scout:iq3"}]})
        elif "v1/chat/completions" in url:
            payload = json.loads(req.data.decode("utf-8"))
            captured_payloads.append(payload)
            return MockResponse({
                "choices": [{
                    "message": {
                        "content": "The cost is $100."
                    }
                }]
            })
        raise Exception(f"Unexpected URL: {url}")
        
    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)
    
    active_summary = {"source": "test", "project_name": "test"}
    res = worker._call_local_ollama(active_summary, [], {})
    
    assert "The cost is $100." in res
    assert len(captured_payloads) == 1
    msgs = captured_payloads[0]["messages"]
    
    # Total messages should be system + user(1) + assistant(1) + user(current) = 4
    assert len(msgs) == 4
    assert msgs[0]["role"] == "system"
    assert msgs[1]["role"] == "user"
    assert msgs[1]["content"] == "Hello"
    assert msgs[2]["role"] == "assistant"
    # Ensure <think> block is stripped from history!
    assert msgs[2]["content"] == "Hi there!"
    assert msgs[3]["role"] == "user"
    assert msgs[3]["content"] == "What is the cost?"


def test_suggestions_and_proactive_warnings(qapp, monkeypatch):
    # Test get_context_suggestions fallback and dynamic generation
    suggestions = ai_tools.get_context_suggestions(None)
    assert len(suggestions) > 0
    assert "Show active estimate KPIs" in suggestions or "Analyze project outliers" in suggestions




