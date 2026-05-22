import os
import sqlite3
from sqlalchemy import create_engine
from database import DatabaseManager
from orm_models import Material, Labor, Equipment, Plant, IndirectCost, DBEstimate, DBTask

def get_workspace_structure(workspace_root=None):
    """
    Recursively lists all files and folders in the workspace, excluding hidden or system directories,
    providing full structural context to the AI Agent.
    """
    if not workspace_root:
        workspace_root = os.getcwd()
    
    structure = []
    exclude_dirs = {'.git', '.idea', '__pycache__', '.pytest_cache', '.vscode', 'venv', '.venv'}
    
    for root, dirs, files in os.walk(workspace_root):
        # Exclude hidden/ignored directories in-place to avoid traversing them
        dirs[:] = [d for d in dirs if d not in exclude_dirs and not d.startswith('.')]
        
        # Capture directory structure
        for d in dirs:
            rel_path = os.path.relpath(os.path.join(root, d), workspace_root)
            structure.append(f"{rel_path}/")
            
        # Capture files
        for f in files:
            rel_path = os.path.relpath(os.path.join(root, f), workspace_root)
            structure.append(rel_path)
            
    return sorted(structure)

def query_active_estimate_summary(main_window=None):
    """
    Retrieves the KPIs and summary of the active project/estimate.
    Checks the active subwindow first, and falls back to scanning
    the recent records in construction_costs.db.
    """
    # 1. Try to get details from the active PyQt6 MDI subwindow
    if main_window:
        try:
            active_win = main_window._get_active_estimate_window()
            if active_win and hasattr(active_win, 'estimate'):
                est = active_win.estimate
                totals = est.calculate_totals()
                return {
                    "source": "Active PyQt6 Window (Rate Build-up Editor)",
                    "project_name": getattr(est, 'project_name', 'Unnamed Project'),
                    "client_name": getattr(est, 'client_name', 'N/A'),
                    "rate_code": getattr(est, 'rate_code', 'N/A'),
                    "category": getattr(est, 'category', 'N/A'),
                    "rate_type": getattr(est, 'rate_type', 'Simple'),
                    "overhead_percent": getattr(est, 'overhead_percent', 0.0),
                    "profit_margin_percent": getattr(est, 'profit_margin_percent', 0.0),
                    "currency": getattr(est, 'currency', 'GHS (₵)'),
                    "unit": getattr(est, 'unit', 'each'),
                    "notes": getattr(est, 'notes', ''),
                    "subtotal": totals.get("subtotal", 0.0),
                    "overhead_amount": totals.get("overhead", 0.0),
                    "profit_amount": totals.get("profit", 0.0),
                    "grand_total": totals.get("grand_total", 0.0)
                }
            
            # Check for PBOQ Viewer active window
            active_class = getattr(active_win, '__class__', None).__name__ if active_win else None
            if active_class == 'PBOQDialog':
                pboq_path = active_win.pboq_file_selector.currentData()
                if pboq_path and os.path.exists(pboq_path):
                    conn = sqlite3.connect(pboq_path)
                    cursor = conn.cursor()
                    
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pboq_items'")
                    table_exists = cursor.fetchone()
                    
                    total_items = 0
                    plugged_items = 0
                    priced_items = 0
                    grand_total = 0.0
                    
                    if table_exists:
                        cursor.execute("SELECT COUNT(*) FROM pboq_items")
                        total_items = cursor.fetchone()[0]
                        
                        cursor.execute("PRAGMA table_info(pboq_items)")
                        actual_cols = [c[1] for c in cursor.fetchall()]
                        
                        plug_col = next((c for c in ["PlugRate", "Plug Rate", "PlugRate "] if c in actual_cols), None)
                        if plug_col:
                            cursor.execute(f"SELECT COUNT(*) FROM pboq_items WHERE \"{plug_col}\" > 0")
                            plugged_items = cursor.fetchone()[0]
                        
                        bill_rate_col = next((c for c in ["Bill Rate", "BillRate", "Bill Rate "] if c in actual_cols), None)
                        if bill_rate_col:
                            cursor.execute(f"SELECT \"{bill_rate_col}\" FROM pboq_items")
                            for (val_str,) in cursor.fetchall():
                                if val_str:
                                    try:
                                        val_f = float(str(val_str).replace(',', '').strip())
                                        if val_f > 0:
                                            priced_items += 1
                                    except ValueError:
                                        pass
                        
                        bill_amt_col = next((c for c in ["Bill Amount", "BillAmount", "Bill Amount "] if c in actual_cols), None)
                        if bill_amt_col:
                            cursor.execute(f"SELECT \"{bill_amt_col}\" FROM pboq_items")
                            for (val_str,) in cursor.fetchall():
                                if val_str:
                                    try:
                                        grand_total += float(str(val_str).replace(',', '').strip())
                                    except ValueError:
                                        pass
                    
                    conn.close()
                    
                    currency = 'GHS (₵)'
                    try:
                        db = DatabaseManager("construction_costs.db")
                        currency = db.get_setting('currency', 'GHS (₵)')
                    except Exception:
                        pass
                    
                    return {
                        "source": f"Active PyQt6 Window (PBOQ Dialog: {os.path.basename(pboq_path)})",
                        "project_name": os.path.basename(pboq_path),
                        "total_boq_items": total_items,
                        "plugged_items": plugged_items,
                        "priced_items": priced_items,
                        "outstanding_items": max(0, total_items - priced_items),
                        "grand_total": grand_total,
                        "currency": currency,
                        "pboq_database_path": pboq_path
                    }
        except Exception as e:
            pass

    # 2. Fallback: Query the construction_costs.db for recent estimate information
    try:
        db = DatabaseManager("construction_costs.db")
        recents = db.get_recent_estimates(limit=1)
        if recents:
            recent_id = recents[0]['id']
            est_obj = db.load_estimate_details(recent_id)
            if est_obj:
                totals = est_obj.calculate_totals()
                return {
                    "source": "Database Fallback (construction_costs.db)",
                    "project_name": est_obj.project_name,
                    "client_name": est_obj.client_name,
                    "rate_code": est_obj.rate_code,
                    "overhead_percent": est_obj.overhead_percent,
                    "profit_margin_percent": est_obj.profit_margin_percent,
                    "currency": est_obj.currency,
                    "subtotal": totals.get("subtotal", 0.0),
                    "overhead_amount": totals.get("overhead", 0.0),
                    "profit_amount": totals.get("profit", 0.0),
                    "grand_total": totals.get("grand_total", 0.0)
                }
    except Exception:
        pass

    return {"status": "No active estimate found or database is currently empty."}

def query_historical_rates(query_str=None, db_file="construction_rates.db"):
    """
    Queries historical rates inside the specified rates database file,
    providing matching entries, codes, categories, units, and grand totals.
    Also dynamically searches loaded project databases if available.
    """
    db_paths = []
    
    # 1. Fallback / global database
    if os.path.exists(db_file):
        db_paths.append(("Historical Library", db_file))
        
    # 2. Check if a project directory is active in construction_costs.db settings
    try:
        costs_db = DatabaseManager("construction_costs.db")
        project_dir = costs_db.get_setting('last_project_dir', '')
        if project_dir and os.path.exists(project_dir):
            if os.path.basename(project_dir) == "Project Database":
                project_dir = os.path.dirname(project_dir)
            for sub_folder in ["Imported Library", "Project Database", "Priced BOQs", "SOR"]:
                folder_path = os.path.join(project_dir, sub_folder)
                if os.path.exists(folder_path):
                    for f in os.listdir(folder_path):
                        if f.endswith('.db'):
                            db_paths.append((f, os.path.join(folder_path, f)))
    except Exception:
        pass

    results = []
    seen_keys = set() # To avoid duplicate rate codes
    query_lower = query_str.lower() if query_str else None
    
    for db_name, path in db_paths:
        try:
            db = DatabaseManager(path)
            rates = db.get_rates_data()
            for r in rates:
                name = str(r.get('project_name', '')).lower()
                code = str(r.get('rate_code', '')).lower()
                notes = str(r.get('notes', '')).lower()
                
                if not query_lower or (query_lower in name or query_lower in code or query_lower in notes):
                    # Dedup by code and grand total
                    key = (r.get('rate_code'), r.get('grand_total'))
                    if key not in seen_keys:
                        seen_keys.add(key)
                        results.append(r)
        except Exception:
            pass
            
    return results


def get_outlier_items(pboq_db_path=None, threshold=0.15):
    """
    Scans estimate items (or active PBOQ database) and compares their unit rates
    against the baseline libraries to detect pricing anomalies (±15% deviations)
    and manual plug rates.
    """
    outliers = []
    plug_rates = []
    
    # 1. Build rapid-lookup baseline directory of cost library elements
    library_baseline = {
        'materials': {},
        'labor': {},
        'equipment': {},
        'plant': {}
    }
    
    try:
        cost_db = DatabaseManager("construction_costs.db")
        for m in cost_db.get_items('materials'):
            library_baseline['materials'][m['name'].lower()] = m['price']
        for l in cost_db.get_items('labor'):
            library_baseline['labor'][l['trade'].lower()] = l['rate']
        for eq in cost_db.get_items('equipment'):
            library_baseline['equipment'][eq['name'].lower()] = eq['rate']
        for pl in cost_db.get_items('plant'):
            library_baseline['plant'][pl['name'].lower()] = pl['rate']
    except Exception as e:
        pass

    # 2. Query estimates in construction_costs.db for task breakdown item anomalies
    try:
        cost_db = DatabaseManager("construction_costs.db")
        with cost_db.Session() as session:
            ests = session.query(DBEstimate).all()
            for db_est in ests:
                loaded = cost_db.load_estimate_details(db_est.id)
                if not loaded:
                    continue
                for task in loaded.tasks:
                    # Materials anomalies
                    for mat in task.materials:
                        name = mat.get('name', '')
                        price = mat.get('unit_cost', 0.0)
                        base_price = library_baseline['materials'].get(name.lower())
                        if base_price and base_price > 0:
                            dev = (price - base_price) / base_price
                            if abs(dev) >= threshold:
                                outliers.append({
                                    "project": loaded.project_name,
                                    "task": task.description,
                                    "type": "Material",
                                    "item": name,
                                    "current_rate": price,
                                    "library_rate": base_price,
                                    "deviation": f"{dev * 100:+.1f}%"
                                })

                    # Labor anomalies
                    for lab in task.labor:
                        trade = lab.get('trade', '')
                        rate = lab.get('rate', 0.0)
                        base_rate = library_baseline['labor'].get(trade.lower())
                        if base_rate and base_rate > 0:
                            dev = (rate - base_rate) / base_rate
                            if abs(dev) >= threshold:
                                outliers.append({
                                    "project": loaded.project_name,
                                    "task": task.description,
                                    "type": "Labor",
                                    "item": trade,
                                    "current_rate": rate,
                                    "library_rate": base_rate,
                                    "deviation": f"{dev * 100:+.1f}%"
                                })

                    # Equipment anomalies
                    for eq in task.equipment:
                        name = eq.get('name', '')
                        rate = eq.get('rate', 0.0)
                        base_rate = library_baseline['equipment'].get(name.lower())
                        if base_rate and base_rate > 0:
                            dev = (rate - base_rate) / base_rate
                            if abs(dev) >= threshold:
                                outliers.append({
                                    "project": loaded.project_name,
                                    "task": task.description,
                                    "type": "Equipment",
                                    "item": name,
                                    "current_rate": rate,
                                    "library_rate": base_rate,
                                    "deviation": f"{dev * 100:+.1f}%"
                                })

                    # Plant anomalies
                    for pl in task.plant:
                        name = pl.get('name', '')
                        rate = pl.get('rate', 0.0)
                        base_rate = library_baseline['plant'].get(name.lower())
                        if base_rate and base_rate > 0:
                            dev = (rate - base_rate) / base_rate
                            if abs(dev) >= threshold:
                                outliers.append({
                                    "project": loaded.project_name,
                                    "task": task.description,
                                    "type": "Plant",
                                    "item": name,
                                    "current_rate": rate,
                                    "library_rate": base_rate,
                                    "deviation": f"{dev * 100:+.1f}%"
                                })
    except Exception as e:
        pass

    # 3. Scan specified PBOQ database for direct plug rates and flagged anomalies
    if pboq_db_path and os.path.exists(pboq_db_path):
        try:
            conn = sqlite3.connect(pboq_db_path)
            cursor = conn.cursor()
            # Read schema to get available columns dynamically
            cursor.execute("PRAGMA table_info(pboq_items)")
            columns = [c[1] for c in cursor.fetchall()]
            
            # Fetch all items that have a plug rate or are flagged
            if "PlugRate" in columns:
                cursor.execute("SELECT rowid, * FROM pboq_items WHERE PlugRate > 0 OR IsFlagged = 1")
                rows = cursor.fetchall()
                for r in rows:
                    row_id = r[0]
                    # We map columns by index to gather information safely
                    item_data = dict(zip(columns, r[1:]))
                    
                    desc = item_data.get('Description') or item_data.get('Column 1') or item_data.get('Column 2') or f"Row {row_id}"
                    plug_val = item_data.get('PlugRate', 0)
                    plug_code = item_data.get('PlugCode', '')
                    is_flagged = item_data.get('IsFlagged', 0)
                    
                    if plug_val and float(plug_val) > 0:
                        plug_rates.append({
                            "row_id": row_id,
                            "description": desc,
                            "plug_rate": float(plug_val),
                            "plug_code": plug_code,
                            "is_flagged_for_review": bool(is_flagged)
                        })
            conn.close()
        except Exception:
            pass

    return {
        "outlier_deviations": outliers,
        "manual_plug_rates": plug_rates
    }
