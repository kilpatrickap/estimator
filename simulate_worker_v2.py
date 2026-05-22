import sys
sys.stdout.reconfigure(encoding='utf-8')
import ai_worker
import ai_tools

class DummyMainWindow:
    def _get_active_estimate_window(self):
        return None

# Create worker
worker = ai_worker.AICopilotWorker("Show active estimate KPIs", main_window=DummyMainWindow())

# Connect signals to print
worker.signals.finished.connect(lambda txt: print(f"\n--- SUCCESS RESPONSE ---\n{txt}\n--------------------\n"))
worker.signals.error.connect(lambda err: print(f"\n--- ERROR RESPONSE ---\n{err}\n--------------------\n"))

# Mock _call_local_ollama to raise exception to test local fallback
original_call_ollama = worker._call_local_ollama
def mock_call_ollama(*args, **kwargs):
    raise Exception("Ollama is not running locally.")
worker._call_local_ollama = mock_call_ollama

# Run worker
print("Running worker with local fallback...")
worker.run()

# Run with actual Ollama if possible
worker_ollama = ai_worker.AICopilotWorker("Show active estimate KPIs", main_window=DummyMainWindow())
worker_ollama.signals.finished.connect(lambda txt: print(f"\n--- SUCCESS OLLAMA RESPONSE ---\n{txt}\n--------------------\n"))
worker_ollama.signals.error.connect(lambda err: print(f"\n--- ERROR OLLAMA RESPONSE ---\n{err}\n--------------------\n"))

print("\nRunning worker with Ollama (if running)...")
try:
    worker_ollama.run()
except Exception as e:
    print("Ollama run failed:", e)
