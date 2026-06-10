import sys
import os
import urllib.request
import json
import re

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, 'c:/Users/Consar-Kilpatrick/Estimator_Pro_20May26/estimator')

import ai_tools

costs_db = ai_tools.DatabaseManager("construction_costs.db")
project_dir = costs_db.get_setting('last_project_dir', '')
if project_dir:
    project_dir = project_dir.replace('\\', '/')
    if os.path.basename(project_dir) == "Project Database":
        project_dir = os.path.dirname(project_dir)

print("Project Directory:", project_dir)

# Run the what-if tool directly
try:
    res = ai_tools.run_what_if_scenario(project_dir, 'material', 'concrete', '+10%')
    print("--- WHAT IF TOOL RESULT ---")
    print(json.dumps(res, indent=2))
    print("----------------------------")
except Exception as e:
    print("Error running tool:", e)
