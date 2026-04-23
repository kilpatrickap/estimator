import sys
import time
import os
from PyQt6.QtWidgets import QApplication

# Adjust the path to import application modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pboq_viewer import PBOQDialog

def test_load():
    app = QApplication(sys.argv)
    
    # Use the project directory
    project_dir = r"C:\Users\Consar-Kilpatrick\Desktop\Atlantic Catering School"
    
    print("Initializing PBOQDialog...")
    dialog = PBOQDialog(project_dir=project_dir)
    
    # Find the index of the specific DB
    db_name = "Atlantic Catering School.db"
    index_to_load = -1
    for i in range(dialog.pboq_file_selector.count()):
        if dialog.pboq_file_selector.itemText(i) == db_name:
            index_to_load = i
            break
            
    if index_to_load == -1:
        print(f"Could not find {db_name} in the file selector. Loading index 0 instead.")
        index_to_load = 0
        if dialog.pboq_file_selector.count() == 0:
            print("No PBOQ databases found!")
            return
            
    db_file = dialog.pboq_file_selector.itemText(index_to_load)
    print(f"Testing load time for: {db_file}")
    
    start_time = time.time()
    
    # Call the load method
    dialog._load_pboq_db(index_to_load)
    
    end_time = time.time()
    
    load_time = end_time - start_time
    print(f"Load completed in: {load_time:.4f} seconds")
    
    # We don't need to exec the app, just exit
    app.quit()

if __name__ == "__main__":
    test_load()
