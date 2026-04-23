import sys
import cProfile
import pstats
import os
from PyQt6.QtWidgets import QApplication

# Adjust the path to import application modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from boq_setup import BOQSetupWindow

def run_profile():
    app = QApplication(sys.argv)
    
    project_dir = r"C:\Users\Consar-Kilpatrick\Desktop\Atlantic Catering School"
    boq_dir = os.path.join(project_dir, "Imported BOQs")
    
    if not os.path.exists(boq_dir):
        print(f"Directory not found: {boq_dir}")
        return
        
    boq_files = [f for f in os.listdir(boq_dir) if f.endswith('.xlsx') or f.endswith('.xls')]
    if not boq_files:
        print("No Excel files found in Imported BOQs")
        return
        
    boq_file_path = os.path.join(boq_dir, boq_files[0])
    print(f"Testing load time for: {boq_file_path}")
    
    profiler = cProfile.Profile()
    profiler.enable()
    
    # Load the Imported BOQ (constructor calls _load_excel)
    dialog = BOQSetupWindow(boq_file_path=boq_file_path, project_dir=project_dir)
    
    profiler.disable()
    
    print("--- PROFILING RESULTS ---")
    stats = pstats.Stats(profiler).sort_stats('tottime')
    stats.print_stats(20)  # Print top 20 functions by total time
    
    app.quit()

if __name__ == "__main__":
    run_profile()
