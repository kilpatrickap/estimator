import sys
import cProfile
import pstats
import os
from PyQt6.QtWidgets import QApplication

# Adjust the path to import application modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pboq_viewer import PBOQDialog

def run_profile():
    app = QApplication(sys.argv)
    
    project_dir = r"C:\Users\Consar-Kilpatrick\Desktop\Atlantic Catering School"
    dialog = PBOQDialog(project_dir=project_dir)
    
    # Select the first DB to test
    if dialog.pboq_file_selector.count() == 0:
        print("No PBOQ databases found!")
        return
        
    db_file = dialog.pboq_file_selector.itemText(0)
    print(f"Testing load time for: {db_file}")
    
    profiler = cProfile.Profile()
    profiler.enable()
    
    # Load the PBOQ database
    dialog._load_pboq_db(0)
    
    profiler.disable()
    
    print("--- PROFILING RESULTS ---")
    stats = pstats.Stats(profiler).sort_stats('tottime')
    stats.print_stats(20)  # Print top 20 functions by total time
    
    app.quit()

if __name__ == "__main__":
    run_profile()
