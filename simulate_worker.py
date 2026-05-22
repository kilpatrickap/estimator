import sys
sys.stdout.reconfigure(encoding='utf-8')
import ai_worker
import ai_tools

class DummyMainWindow:
    def _get_active_estimate_window(self):
        return None

# Create worker
worker = ai_worker.AICopilotWorker("Show active estimate KPIs", main_window=DummyMainWindow())

# Mock _call_local_ollama to raise exception to test local fallback
original_call_ollama = worker._call_local_ollama
def mock_call_ollama(*args, **kwargs):
    raise Exception("Ollama is not running locally.")
worker._call_local_ollama = mock_call_ollama

# Run worker
print("Running worker with local fallback...")
worker.run()

# Restore Ollama and run if possible
worker_ollama = ai_worker.AICopilotWorker("Show active estimate KPIs", main_window=DummyMainWindow())
print("\nRunning worker with Ollama (if running)...")
try:
    worker_ollama.run()
except Exception as e:
    print("Ollama failed:", e)
