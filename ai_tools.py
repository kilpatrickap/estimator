import os
import sqlite3
import json
from sqlalchemy import create_engine
from database import DatabaseManager
from orm_models import Material, Labor, Equipment, Plant, IndirectCost, DBEstimate, DBTask

APP_DIR = os.path.dirname(os.path.abspath(__file__))

def get_workspace_structure(workspace_root=None):
    """
    Recursively lists all files and folders in the workspace, excluding hidden or system directories,
    providing full structural context to the AI Agent.
    """
    if not workspace_root:
        workspace_root = APP_DIR
    
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
    import json
    # 1. Try to get details from the active PyQt6 MDI subwindow
    project_dir = None
    pboq_path = None
    active_class = None
    
    if main_window:
        try:
            active_win = main_window._get_active_estimate_window()
            if active_win:
                active_class = getattr(active_win, '__class__', None).__name__
                if hasattr(active_win, 'estimate'):
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
                elif active_class == 'PBOQDialog' and hasattr(active_win, 'pboq_file_selector'):
                    pboq_path = active_win.pboq_file_selector.currentData()
                    if pboq_path:
                        project_dir = os.path.dirname(os.path.dirname(pboq_path))
                elif active_class == 'AnalyticsDashboard' and hasattr(active_win, 'project_dir'):
                    project_dir = active_win.project_dir
        except:
            pass

    # Fallback to database setting for recent project directory if not found via active window
    if not project_dir:
        try:
            costs_db = DatabaseManager("construction_costs.db")
            project_dir = costs_db.get_setting('last_project_dir', '')
        except:
            pass

    if project_dir and os.path.exists(project_dir):
        try:
            project_dir = project_dir.replace('\\', '/')
            if os.path.basename(project_dir) == "Project Database":
                project_dir = os.path.dirname(project_dir)
                
            project_name = os.path.basename(project_dir)
            pboq_dir = os.path.join(project_dir, "Priced BOQs")
            
            if os.path.exists(pboq_dir):
                # 1. Load project settings (currency, overhead, profit) from the master project database
                overhead_percent = 0.0
                profit_margin_percent = 0.0
                currency = "GHS (₵)"
                factor = 1.0
                try:
                    db_dir = os.path.join(project_dir, "Project Database")
                    if os.path.exists(db_dir):
                        dbs = [f for f in os.listdir(db_dir) if f.lower().endswith('.db') and "rates" not in f.lower()]
                        if dbs:
                            db_path = os.path.join(db_dir, dbs[0])
                            conn = sqlite3.connect(db_path)
                            cursor = conn.cursor()
                            try:
                                cursor.execute("SELECT value FROM settings WHERE key='overhead'")
                                row = cursor.fetchone()
                                if row: overhead_percent = float(row[0])
                                
                                cursor.execute("SELECT value FROM settings WHERE key='profit'")
                                row = cursor.fetchone()
                                if row: profit_margin_percent = float(row[0])
                                
                                cursor.execute("SELECT value FROM settings WHERE key='currency'")
                                row = cursor.fetchone()
                                if row: currency = row[0]
                                
                                cursor.execute("SELECT value FROM settings WHERE key='factor'")
                                row = cursor.fetchone()
                                if row: factor = float(row[0])
                            except: pass
                            conn.close()
                except: pass
                
                # 2. Iterate and aggregate across all PBOQ databases
                dbs = [os.path.join(pboq_dir, f) for f in os.listdir(pboq_dir) if f.endswith('.db')]
                total_net_cost = 0.0
                total_items = 0
                priced_items = 0
                plugged_items = 0
                best_pboq = None
                
                # If there was a viewer_state.json, load it to get best_pboq fallback
                state_file_viewer = os.path.join(project_dir, "PBOQ States", "viewer_state.json")
                if os.path.exists(state_file_viewer):
                    try:
                        with open(state_file_viewer, 'r') as sf:
                            state_data = json.load(sf)
                            last_bill = state_data.get('last_bill')
                            if last_bill:
                                cand_path = os.path.join(pboq_dir, last_bill)
                                if os.path.exists(cand_path):
                                    best_pboq = cand_path
                    except: pass
                
                if not best_pboq and dbs:
                    best_pboq = dbs[0]
                
                for path in dbs:
                    f = os.path.basename(path)
                    
                    qty_col_idx = -1
                    desc_col_idx = -1
                    bill_rate_col_idx = -1
                    bill_amt_col_idx = -1
                    dummy_val = 0.1
                    
                    state_file = os.path.join(project_dir, "PBOQ States", f + ".json")
                    state_data = {}
                    if os.path.exists(state_file):
                        try:
                            with open(state_file, 'r') as sf:
                                state_data = json.load(sf)
                                m = state_data.get('mappings', {})
                                qty_col_idx = m.get('qty', -1)
                                desc_col_idx = m.get('desc', -1)
                                bill_rate_col_idx = m.get('bill_rate', -1)
                                bill_amt_col_idx = m.get('bill_amount', -1)
                                dummy_val = state_data.get('dummy_rate', 0.1)
                        except: pass
                        
                    try:
                        conn = sqlite3.connect(path)
                        cursor = conn.cursor()
                        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pboq_items'")
                        if not cursor.fetchone():
                            conn.close()
                            continue
                            
                        cursor.execute("PRAGMA table_info(pboq_items)")
                        cols = [info[1] for info in cursor.fetchall()]
                        
                        qty_name = cols[qty_col_idx + 1] if qty_col_idx >= 0 and (qty_col_idx + 1) < len(cols) else next((c for c in cols if c.lower() in ["quantity", "qty"]), None)
                        desc_name = cols[desc_col_idx + 1] if desc_col_idx >= 0 and (desc_col_idx + 1) < len(cols) else next((c for c in cols if c.lower() in ["description", "desc"]), None)
                        bill_rate_name = cols[bill_rate_col_idx + 1] if bill_rate_col_idx >= 0 and (bill_rate_col_idx + 1) < len(cols) else next((c for c in cols if c.lower() in ["bill rate", "billrate", "column 4"]), None)
                        bill_amt_name = cols[bill_amt_col_idx + 1] if bill_amt_col_idx >= 0 and (bill_amt_col_idx + 1) < len(cols) else next((c for c in cols if c.lower() in ["bill amount", "billamount", "column 5"]), None)
                        
                        col_map = {
                            'desc': desc_name,
                            'qty': qty_name,
                            'bill_rate': bill_rate_name,
                            'bill_amt': bill_amt_name,
                            'gross': next((c for c in cols if c.lower() in ["grossrate", "gross_rate"]), None),
                            'plug': next((c for c in cols if c.lower() in ["plugrate", "plug_rate"]), None),
                            'sub': next((c for c in cols if c.lower() in ["subbeerate", "sub_rate"]), None),
                            'prov': next((c for c in cols if c.lower() in ["provsum", "prov_sum"]), None),
                            'pc': next((c for c in cols if c.lower() in ["pcsum", "pc_sum"]), None),
                            'dw': next((c for c in cols if c.lower() in ["daywork"]), None),
                            'rcode': next((c for c in cols if c.lower() in ["ratecode", "rate_code"]), None),
                            'pcode': next((c for c in cols if c.lower() in ["plugcode", "plug_code"]), None)
                        }
                        
                        if not (col_map['desc'] and col_map['qty']):
                            conn.close()
                            continue
                            
                        query_cols = []
                        for k in ['desc', 'qty', 'bill_rate', 'bill_amt', 'gross', 'plug', 'sub', 'prov', 'pc', 'dw', 'rcode', 'pcode']:
                            if col_map[k]: query_cols.append(f"\"{col_map[k]}\"")
                            else: query_cols.append("''")
                            
                        cursor.execute(f"SELECT {', '.join(query_cols)} FROM pboq_items")
                        rows = cursor.fetchall()
                        
                        rate_cache = {}
                        def get_net_rate(rate_code):
                            if not rate_code: return 0.0
                            if rate_code in rate_cache: return rate_cache[rate_code]
                            try:
                                db_dir2 = os.path.join(project_dir, "Project Database")
                                dbs2 = [f2 for f2 in os.listdir(db_dir2) if f2.lower().endswith('.db') and "rates" not in f2.lower()]
                                if dbs2:
                                    db_path2 = os.path.join(db_dir2, dbs2[0])
                                    conn2 = sqlite3.connect(db_path2)
                                    cursor2 = conn2.cursor()
                                    cursor2.execute("SELECT net_total FROM estimates WHERE rate_code = ?", (rate_code,))
                                    res = cursor2.fetchone()
                                    conn2.close()
                                    if res:
                                        rate_cache[rate_code] = float(res[0] or 0.0)
                                        return rate_cache[rate_code]
                            except: pass
                            rate_cache[rate_code] = 0.0
                            return 0.0
                            
                        def to_float(val):
                            if not val: return 0.0
                            if isinstance(val, (int, float)): return float(val)
                            try: return float(str(val).replace(',', '').replace(' ', '').replace('₵','').replace('$','').strip())
                            except: return 0.0
                            
                        for r in rows:
                            desc, q, br, ba, gross, plug, sub, prov, pc, dw, rcode, pcode = r
                            desc_low = (desc or "").lower()
                            if not str(desc).strip() or "collection" in desc_low or "summary" in desc_low:
                                continue
                                
                            qty_f = to_float(q)
                            bill_rate_f = to_float(br)
                            bill_amt_f = to_float(ba)
                            
                            if qty_f == 0 and bill_amt_f == 0:
                                continue
                                
                            g_val = to_float(gross)
                            p_val = to_float(plug)
                            s_val = to_float(sub)
                            pr_val = to_float(prov)
                            pc_val = to_float(pc)
                            d_val = to_float(dw)
                            
                            is_row_priced = (g_val > 0 or p_val > 0 or s_val > 0 or pr_val > 0 or pc_val > 0 or d_val > 0)
                            if not is_row_priced:
                                if bill_rate_f > 0 and abs(bill_rate_f - dummy_val) > 0.0001:
                                    is_row_priced = True
                                    
                            is_priced = is_row_priced
                            
                            active_code = pcode if pcode and str(pcode).strip() else rcode
                            master_net_cost = get_net_rate(active_code) if active_code else 0.0
                            
                            unit_cost = 0.0
                            if pr_val > 0: unit_cost = pr_val
                            elif pc_val > 0: unit_cost = pc_val
                            elif d_val > 0: unit_cost = d_val
                            elif master_net_cost > 0: unit_cost = master_net_cost
                            else:
                                if p_val > 0: unit_cost = p_val
                                elif s_val > 0: unit_cost = s_val
                                elif g_val > 0: unit_cost = g_val
                                else:
                                    if bill_amt_f > 0:
                                        unit_cost = bill_amt_f if qty_f <= 1 else 0.0
                                        
                            calc_qty = qty_f if qty_f > 0 else (1.0 if bill_amt_f > 0 else 0.0)
                            item_net_cost = round(unit_cost * calc_qty, 2) if is_priced else 0.0
                            
                            total_items += 1
                            if is_priced: priced_items += 1
                            total_net_cost += item_net_cost
                            
                            if plug and to_float(plug) > 0:
                                plugged_items += 1
                                
                        conn.close()
                    except Exception:
                        pass
                
                combined_markup = (overhead_percent + profit_margin_percent) / 100.0
                grand_total = total_net_cost * (1.0 + combined_markup)
                
                subtotal = round(total_net_cost, 2)
                overhead_amount = round(total_net_cost * (overhead_percent / 100.0), 2)
                profit_amount = round(total_net_cost * (profit_margin_percent / 100.0), 2)
                
                source_str = f"Loaded Project Directory ({project_name})"
                if pboq_path:
                    source_str = f"Active PyQt6 Window (PBOQ Dialog: {os.path.basename(pboq_path)})"
                elif active_class == 'AnalyticsDashboard':
                    source_str = f"Active PyQt6 Window (Analytics Dashboard: {project_name})"
                
                return {
                    "source": source_str,
                    "project_name": project_name,
                    "total_boq_items": total_items,
                    "plugged_items": plugged_items,
                    "priced_items": priced_items,
                    "outstanding_items": max(0, total_items - priced_items),
                    "subtotal": subtotal,
                    "overhead_amount": overhead_amount,
                    "profit_amount": profit_amount,
                    "grand_total": round(grand_total, 2),
                    "currency": currency,
                    "overhead_percent": overhead_percent,
                    "profit_margin_percent": profit_margin_percent,
                    "factor": factor,
                    "pboq_database_path": pboq_path or best_pboq,
                    "project_directory": project_dir
                }
        except:
            pass

    # 3. Fallback B: Query the construction_costs.db for recent estimate information
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
    abs_db_file = db_file if os.path.isabs(db_file) else os.path.join(APP_DIR, db_file)
    if os.path.exists(abs_db_file):
        db_paths.append(("Historical Library", abs_db_file))
        
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

def get_active_project_db_path():
    """
    Returns the absolute path to the active project's primary database (.db) file
    located in the 'Project Database' folder, if a project is loaded.
    """
    try:
        costs_db = DatabaseManager("construction_costs.db")
        project_dir = costs_db.get_setting('last_project_dir', '')
        if project_dir and os.path.exists(project_dir):
            if os.path.basename(project_dir) == "Project Database":
                project_dir = os.path.dirname(project_dir)
            project_db_dir = os.path.join(project_dir, "Project Database")
            if os.path.exists(project_db_dir):
                dbs = [os.path.join(project_db_dir, f) for f in os.listdir(project_db_dir) if f.endswith('.db')]
                proj_name = os.path.basename(project_dir)
                for db_path in dbs:
                    if proj_name.lower() in os.path.basename(db_path).lower():
                        return db_path
                if dbs:
                    return dbs[0]
    except Exception:
        pass
    return None

def search_active_database(query_str):
    """
    Searches the active project database, priced BOQ databases, and the cost library
    for resources or tasks matching the query string.
    """
    if not query_str:
        return {}

    query_lower = query_str.lower().strip()
    is_general_materials = query_lower in ["materials", "material"]
    is_general_labor = query_lower in ["labor", "labour"]
    is_general_equipment = query_lower in ["equipment"]
    is_general_plant = query_lower in ["plant"]

    results = {
        "materials": [],
        "labor": [],
        "equipment": [],
        "plant": [],
        "tasks": [],
        "pboq_items": []
    }
    
    db_paths = []
    
    # 1. Cost library (construction_costs.db)
    abs_costs_db = os.path.join(APP_DIR, "construction_costs.db")
    if os.path.exists(abs_costs_db):
        db_paths.append(("Cost Library", abs_costs_db))
        
    # 2. Project databases (Project Database, Imported Library, Priced BOQs, SOR)
    try:
        costs_db = DatabaseManager("construction_costs.db")
        project_dir = costs_db.get_setting('last_project_dir', '')
        if project_dir and os.path.exists(project_dir):
            if os.path.basename(project_dir) == "Project Database":
                project_dir = os.path.dirname(project_dir)
            for sub in ["Project Database", "Imported Library", "Priced BOQs", "SOR"]:
                sub_dir = os.path.join(project_dir, sub)
                if os.path.exists(sub_dir):
                    for f in os.listdir(sub_dir):
                        if f.endswith('.db'):
                            db_paths.append((sub, os.path.join(sub_dir, f)))
    except Exception:
        pass
        
    seen_paths = set()
    unique_dbs = []
    for source, path in db_paths:
        abs_p = os.path.abspath(path)
        if abs_p not in seen_paths and os.path.exists(path):
            seen_paths.add(abs_p)
            unique_dbs.append((source, path))
            
    for source, path in unique_dbs:
        try:
            conn = sqlite3.connect(path)
            cursor = conn.cursor()
            
            def table_exists(tbl):
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (tbl,))
                return cursor.fetchone() is not None
                
            # Search materials
            if table_exists("materials"):
                cursor.execute("PRAGMA table_info(materials)")
                cols = [c[1] for c in cursor.fetchall()]
                name_col = "name" if "name" in cols else ("trade" if "trade" in cols else None)
                if name_col:
                    if is_general_materials:
                        cursor.execute(f"SELECT * FROM materials LIMIT 30")
                    else:
                        cursor.execute(f"SELECT * FROM materials WHERE LOWER({name_col}) LIKE ?", (f"%{query_lower}%",))
                    rows = cursor.fetchall()
                    for r in rows:
                        item = dict(zip(cols, r))
                        results["materials"].append({
                            "source": source,
                            "database": os.path.basename(path),
                            "name": item.get(name_col),
                            "unit": item.get("unit", "each"),
                            "price": item.get("price") or item.get("rate") or 0.0,
                            "currency": item.get("currency", "GHS")
                        })

            # Search estimate_materials
            if table_exists("estimate_materials"):
                cursor.execute("PRAGMA table_info(estimate_materials)")
                cols = [c[1] for c in cursor.fetchall()]
                if "name" in cols:
                    if is_general_materials:
                        cursor.execute(f"SELECT DISTINCT name, unit, price, currency FROM estimate_materials LIMIT 30")
                    else:
                        cursor.execute(f"SELECT DISTINCT name, unit, price, currency FROM estimate_materials WHERE LOWER(name) LIKE ?", (f"%{query_lower}%",))
                    rows = cursor.fetchall()
                    for r in rows:
                        results["materials"].append({
                            "source": f"{source} (Estimate Resources)",
                            "database": os.path.basename(path),
                            "name": r[0],
                            "unit": r[1] or "each",
                            "price": r[2] or 0.0,
                            "currency": r[3] or "GHS"
                        })
                        
            # Search labor
            if table_exists("labor"):
                cursor.execute("PRAGMA table_info(labor)")
                cols = [c[1] for c in cursor.fetchall()]
                trade_col = "trade" if "trade" in cols else ("name" if "name" in cols else None)
                if trade_col:
                    if is_general_labor:
                        cursor.execute(f"SELECT * FROM labor LIMIT 30")
                    else:
                        cursor.execute(f"SELECT * FROM labor WHERE LOWER({trade_col}) LIKE ?", (f"%{query_lower}%",))
                    rows = cursor.fetchall()
                    for r in rows:
                        item = dict(zip(cols, r))
                        results["labor"].append({
                            "source": source,
                            "database": os.path.basename(path),
                            "trade": item.get(trade_col),
                            "unit": item.get("unit", "hr"),
                            "rate": item.get("rate") or item.get("price") or 0.0,
                            "currency": item.get("currency", "GHS")
                        })

            # Search estimate_labor
            if table_exists("estimate_labor"):
                cursor.execute("PRAGMA table_info(estimate_labor)")
                cols = [c[1] for c in cursor.fetchall()]
                if "name_trade" in cols:
                    if is_general_labor:
                        cursor.execute(f"SELECT DISTINCT name_trade, unit, rate, currency FROM estimate_labor LIMIT 30")
                    else:
                        cursor.execute(f"SELECT DISTINCT name_trade, unit, rate, currency FROM estimate_labor WHERE LOWER(name_trade) LIKE ?", (f"%{query_lower}%",))
                    rows = cursor.fetchall()
                    for r in rows:
                        results["labor"].append({
                            "source": f"{source} (Estimate Resources)",
                            "database": os.path.basename(path),
                            "trade": r[0],
                            "unit": r[1] or "hr",
                            "rate": r[2] or 0.0,
                            "currency": r[3] or "GHS"
                        })
                        
            # Search equipment
            if table_exists("equipment"):
                cursor.execute("PRAGMA table_info(equipment)")
                cols = [c[1] for c in cursor.fetchall()]
                name_col = "name" if "name" in cols else ("trade" if "trade" in cols else None)
                if name_col:
                    if is_general_equipment:
                        cursor.execute(f"SELECT * FROM equipment LIMIT 30")
                    else:
                        cursor.execute(f"SELECT * FROM equipment WHERE LOWER({name_col}) LIKE ?", (f"%{query_lower}%",))
                    rows = cursor.fetchall()
                    for r in rows:
                        item = dict(zip(cols, r))
                        results["equipment"].append({
                            "source": source,
                            "database": os.path.basename(path),
                            "name": item.get(name_col),
                            "unit": item.get("unit", "hr"),
                            "rate": item.get("rate") or item.get("price") or 0.0,
                            "currency": item.get("currency", "GHS")
                        })

            # Search estimate_equipment
            if table_exists("estimate_equipment"):
                cursor.execute("PRAGMA table_info(estimate_equipment)")
                cols = [c[1] for c in cursor.fetchall()]
                if "name_trade" in cols:
                    if is_general_equipment:
                        cursor.execute(f"SELECT DISTINCT name_trade, unit, rate, currency FROM estimate_equipment LIMIT 30")
                    else:
                        cursor.execute(f"SELECT DISTINCT name_trade, unit, rate, currency FROM estimate_equipment WHERE LOWER(name_trade) LIKE ?", (f"%{query_lower}%",))
                    rows = cursor.fetchall()
                    for r in rows:
                        results["equipment"].append({
                            "source": f"{source} (Estimate Resources)",
                            "database": os.path.basename(path),
                            "name": r[0],
                            "unit": r[1] or "hr",
                            "rate": r[2] or 0.0,
                            "currency": r[3] or "GHS"
                        })

            # Search plant
            if table_exists("plant"):
                cursor.execute("PRAGMA table_info(plant)")
                cols = [c[1] for c in cursor.fetchall()]
                name_col = "name" if "name" in cols else ("trade" if "trade" in cols else None)
                if name_col:
                    if is_general_plant:
                        cursor.execute(f"SELECT * FROM plant LIMIT 30")
                    else:
                        cursor.execute(f"SELECT * FROM plant WHERE LOWER({name_col}) LIKE ?", (f"%{query_lower}%",))
                    rows = cursor.fetchall()
                    for r in rows:
                        item = dict(zip(cols, r))
                        results["plant"].append({
                            "source": source,
                            "database": os.path.basename(path),
                            "name": item.get(name_col),
                            "unit": item.get("unit", "hr"),
                            "rate": item.get("rate") or item.get("price") or 0.0,
                            "currency": item.get("currency", "GHS")
                        })

            # Search estimate_plant
            if table_exists("estimate_plant"):
                cursor.execute("PRAGMA table_info(estimate_plant)")
                cols = [c[1] for c in cursor.fetchall()]
                if "name_trade" in cols:
                    if is_general_plant:
                        cursor.execute(f"SELECT DISTINCT name_trade, unit, rate, currency FROM estimate_plant LIMIT 30")
                    else:
                        cursor.execute(f"SELECT DISTINCT name_trade, unit, rate, currency FROM estimate_plant WHERE LOWER(name_trade) LIKE ?", (f"%{query_lower}%",))
                    rows = cursor.fetchall()
                    for r in rows:
                        results["plant"].append({
                            "source": f"{source} (Estimate Resources)",
                            "database": os.path.basename(path),
                            "name": r[0],
                            "unit": r[1] or "hr",
                            "rate": r[2] or 0.0,
                            "currency": r[3] or "GHS"
                        })

            if table_exists("tasks"):
                cursor.execute("PRAGMA table_info(tasks)")
                cols = [c[1] for c in cursor.fetchall()]
                desc_col = "description" if "description" in cols else None
                if desc_col:
                    cursor.execute(f"SELECT * FROM tasks WHERE LOWER({desc_col}) LIKE ?", (f"%{query_lower}%",))
                    rows = cursor.fetchall()
                    for r in rows:
                        item = dict(zip(cols, r))
                        results["tasks"].append({
                            "source": source,
                            "database": os.path.basename(path),
                            "description": item.get(desc_col),
                            "quantity": item.get("quantity", 1.0),
                            "unit": item.get("unit", "each")
                        })

            if table_exists("pboq_items"):
                cursor.execute("PRAGMA table_info(pboq_items)")
                cols = [c[1] for c in cursor.fetchall()]
                desc_col = next((c for c in ["Description", "Column 1", "Column 2"] if c in cols), None)
                if desc_col:
                    cursor.execute(f"SELECT rowid, * FROM pboq_items WHERE LOWER(\"{desc_col}\") LIKE ?", (f"%{query_lower}%",))
                    rows = cursor.fetchall()
                    for r in rows:
                        item = dict(zip(cols, r[1:]))
                        results["pboq_items"].append({
                            "source": source,
                            "database": os.path.basename(path),
                            "rowid": r[0],
                            "description": item.get(desc_col),
                            "unit": item.get("Unit") or item.get("Column 3") or "each",
                            "bill_rate": item.get("Bill Rate") or item.get("BillRate") or "0.00",
                            "bill_amount": item.get("Bill Amount") or item.get("BillAmount") or "0.00",
                            "plug_rate": item.get("PlugRate") or item.get("Plug Rate") or "0.00"
                        })
            
            conn.close()
        except Exception:
            pass
            
    return results


def ingest_project_domains(project_dir=None):
    """
    Ingests and parses project configuration and settings data, resources data,
    Schedule of Rates (SOR) data, priced Bill of Quantities (PBOQ) data,
    and cost/margin analytics data in real-time.
    """
    if not project_dir:
        try:
            costs_db = DatabaseManager("construction_costs.db")
            project_dir = costs_db.get_setting('last_project_dir', '')
        except Exception:
            pass

    if project_dir:
        # Strip trailing "Project Database" to locate relative folders (Priced BOQs, SOR, etc.)
        project_dir = project_dir.replace('\\', '/')
        if os.path.basename(project_dir) == "Project Database":
            project_dir = os.path.dirname(project_dir)

    if not project_dir or not os.path.exists(project_dir):
        return {"error": "No active project directory found."}

    domains = {
        "project_settings": {},
        "resources_summary": {},
        "sor_data": [],
        "pboq_summary": {},
        "analytics_summary": {}
    }

    # 1. Ingest Project Settings Data
    proj_db_dir = os.path.join(project_dir, "Project Database")
    master_db_path = None
    if os.path.exists(proj_db_dir):
        dbs = [f for f in os.listdir(proj_db_dir) if f.lower().endswith('.db') and "rates" not in f.lower()]
        if dbs:
            master_db_path = os.path.join(proj_db_dir, dbs[0])

    overhead_rate = 0.0
    profit_rate = 0.0
    currency = "GHS (₵)"
    client_name = "N/A"
    project_name = os.path.basename(project_dir)

    if master_db_path and os.path.exists(master_db_path):
        try:
            conn = sqlite3.connect(master_db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='estimates'")
            if cursor.fetchone():
                cursor.execute("SELECT project_name, client_name, overhead_percent, profit_margin_percent, currency FROM estimates LIMIT 1")
                row = cursor.fetchone()
                if row:
                    project_name = row[0] or project_name
                    client_name = row[1] or client_name
                    overhead_rate = row[2] or 0.0
                    profit_rate = row[3] or 0.0
                    currency = row[4] or currency

            exchange_rates = []
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='estimate_exchange_rates'")
            if cursor.fetchone():
                cursor.execute("SELECT currency, rate, date, operator FROM estimate_exchange_rates")
                for r in cursor.fetchall():
                    exchange_rates.append({
                        "currency": r[0],
                        "rate": r[1],
                        "date": r[2],
                        "operator": r[3]
                    })
            
            domains["project_settings"] = {
                "project_name": project_name,
                "client_name": client_name,
                "base_currency": currency,
                "overhead_percent": overhead_rate,
                "profit_margin_percent": profit_rate,
                "exchange_rates": exchange_rates,
                "master_database": os.path.basename(master_db_path)
            }
            conn.close()
        except Exception as e:
            domains["project_settings"] = {"error": f"Failed to parse settings: {str(e)}"}
    else:
        domains["project_settings"] = {
            "project_name": project_name,
            "base_currency": currency,
            "overhead_percent": overhead_rate,
            "profit_margin_percent": profit_rate,
            "exchange_rates": []
        }

    # 2. Ingest Resources Data
    resources = {
        "materials": {"count": 0, "sample": []},
        "labor": {"count": 0, "sample": []},
        "equipment": {"count": 0, "sample": []},
        "plant": {"count": 0, "sample": []},
        "indirect_costs": {"count": 0, "sample": []}
    }
    for db_file in ["construction_costs.db", master_db_path]:
        if not db_file or not os.path.exists(db_file):
            continue
        try:
            conn = sqlite3.connect(db_file)
            cursor = conn.cursor()
            for tbl in ["materials", "labor", "equipment", "plant", "indirect_costs"]:
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (tbl,))
                if cursor.fetchone():
                    name_col = "name" if tbl != "labor" else "trade"
                    if tbl == "indirect_costs":
                        name_col = "description"
                    cursor.execute(f"SELECT COUNT(*), GROUP_CONCAT({name_col}) FROM {tbl}")
                    count_row = cursor.fetchone()
                    if count_row and count_row[0] > 0:
                        resources[tbl]["count"] += count_row[0]
                        sample = [x.strip() for x in (count_row[1] or "").split(",") if x.strip()][:5]
                        resources[tbl]["sample"] = list(set(resources[tbl]["sample"] + sample))[:5]
            conn.close()
        except Exception:
            pass
    domains["resources_summary"] = resources

    # 3. Ingest SOR Data
    sor_dir = os.path.join(project_dir, "SOR")
    sor_items = []
    if os.path.exists(sor_dir):
        for f in os.listdir(sor_dir):
            if f.lower().endswith('.db'):
                db_path = os.path.join(sor_dir, f)
                try:
                    conn = sqlite3.connect(db_path)
                    cursor = conn.cursor()
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sor_items'")
                    if cursor.fetchone():
                        cursor.execute("SELECT Sheet, Ref, Description, Quantity, Unit, GrossRate, RateCode FROM sor_items LIMIT 50")
                        for row in cursor.fetchall():
                            sor_items.append({
                                "database": f,
                                "sheet": row[0],
                                "ref": row[1],
                                "description": row[2],
                                "quantity": row[3],
                                "unit": row[4],
                                "gross_rate": row[5],
                                "rate_code": row[6]
                            })
                    conn.close()
                except Exception:
                    pass
    domains["sor_data"] = sor_items

    # 4. Ingest PBOQ Data
    pboq_dir = os.path.join(project_dir, "Priced BOQs")
    pboq_sheets = []
    total_priced_value = 0.0
    total_items_count = 0
    priced_items_count = 0
    plugged_items_count = 0

    if os.path.exists(pboq_dir):
        for f in os.listdir(pboq_dir):
            if f.lower().endswith('.db'):
                db_path = os.path.join(pboq_dir, f)
                
                sheet_net_cost = 0.0
                sheet_total_items = 0
                sheet_priced_items = 0
                sheet_plugged_items = 0
                
                qty_col_idx = -1
                desc_col_idx = -1
                bill_rate_col_idx = -1
                bill_amt_col_idx = -1
                dummy_val = 0.1
                
                state_file = os.path.join(project_dir, "PBOQ States", f + ".json")
                state_data = {}
                if os.path.exists(state_file):
                    try:
                        with open(state_file, 'r', encoding='utf-8') as sf:
                            state_data = json.load(sf)
                            m = state_data.get('mappings', {})
                            qty_col_idx = m.get('qty', -1)
                            desc_col_idx = m.get('desc', -1)
                            bill_rate_col_idx = m.get('bill_rate', -1)
                            bill_amt_col_idx = m.get('bill_amount', -1)
                            dummy_val = state_data.get('dummy_rate', 0.1)
                    except: pass
                    
                try:
                    conn = sqlite3.connect(db_path)
                    cursor = conn.cursor()
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pboq_items'")
                    if not cursor.fetchone():
                        conn.close()
                        continue
                        
                    cursor.execute("PRAGMA table_info(pboq_items)")
                    cols = [info[1] for info in cursor.fetchall()]
                    
                    qty_name = cols[qty_col_idx + 1] if qty_col_idx >= 0 and (qty_col_idx + 1) < len(cols) else next((c for c in cols if c.lower() in ["quantity", "qty"]), None)
                    desc_name = cols[desc_col_idx + 1] if desc_col_idx >= 0 and (desc_col_idx + 1) < len(cols) else next((c for c in cols if c.lower() in ["description", "desc"]), None)
                    bill_rate_name = cols[bill_rate_col_idx + 1] if bill_rate_col_idx >= 0 and (bill_rate_col_idx + 1) < len(cols) else next((c for c in cols if c.lower() in ["bill rate", "billrate", "column 4"]), None)
                    bill_amt_name = cols[bill_amt_col_idx + 1] if bill_amt_col_idx >= 0 and (bill_amt_col_idx + 1) < len(cols) else next((c for c in cols if c.lower() in ["bill amount", "billamount", "column 5"]), None)
                    
                    col_map = {
                        'desc': desc_name,
                        'qty': qty_name,
                        'bill_rate': bill_rate_name,
                        'bill_amt': bill_amt_name,
                        'gross': next((c for c in cols if c.lower() in ["grossrate", "gross_rate"]), None),
                        'plug': next((c for c in cols if c.lower() in ["plugrate", "plug_rate"]), None),
                        'sub': next((c for c in cols if c.lower() in ["subbeerate", "sub_rate"]), None),
                        'prov': next((c for c in cols if c.lower() in ["provsum", "prov_sum"]), None),
                        'pc': next((c for c in cols if c.lower() in ["pcsum", "pc_sum"]), None),
                        'dw': next((c for c in cols if c.lower() in ["daywork"]), None),
                        'rcode': next((c for c in cols if c.lower() in ["ratecode", "rate_code"]), None),
                        'pcode': next((c for c in cols if c.lower() in ["plugcode", "plug_code"]), None)
                    }
                    
                    if not (col_map['desc'] and col_map['qty']):
                        conn.close()
                        continue
                        
                    query_cols = []
                    for k in ['desc', 'qty', 'bill_rate', 'bill_amt', 'gross', 'plug', 'sub', 'prov', 'pc', 'dw', 'rcode', 'pcode']:
                        if col_map[k]: query_cols.append(f"\"{col_map[k]}\"")
                        else: query_cols.append("''")
                        
                    cursor.execute(f"SELECT {', '.join(query_cols)} FROM pboq_items")
                    rows = cursor.fetchall()
                    
                    rate_cache = {}
                    def get_net_rate(rate_code):
                        if not rate_code: return 0.0
                        if rate_code in rate_cache: return rate_cache[rate_code]
                        try:
                            db_dir2 = os.path.join(project_dir, "Project Database")
                            dbs2 = [f2 for f2 in os.listdir(db_dir2) if f2.lower().endswith('.db') and "rates" not in f2.lower()]
                            if dbs2:
                                db_path2 = os.path.join(db_dir2, dbs2[0])
                                conn2 = sqlite3.connect(db_path2)
                                cursor2 = conn2.cursor()
                                cursor2.execute("SELECT net_total FROM estimates WHERE rate_code = ?", (rate_code,))
                                res = cursor2.fetchone()
                                conn2.close()
                                if res:
                                    rate_cache[rate_code] = float(res[0] or 0.0)
                                    return rate_cache[rate_code]
                        except: pass
                        rate_cache[rate_code] = 0.0
                        return 0.0
                        
                    def to_float(val):
                        if not val: return 0.0
                        if isinstance(val, (int, float)): return float(val)
                        try: return float(str(val).replace(',', '').replace(' ', '').replace('₵','').replace('$','').strip())
                        except: return 0.0
                        
                    for r in rows:
                        desc, q, br, ba, gross, plug, sub, prov, pc, dw, rcode, pcode = r
                        desc_low = (desc or "").lower()
                        if not str(desc).strip() or "collection" in desc_low or "summary" in desc_low:
                            continue
                            
                        qty_f = to_float(q)
                        bill_rate_f = to_float(br)
                        bill_amt_f = to_float(ba)
                        
                        if qty_f == 0 and bill_amt_f == 0:
                            continue
                            
                        g_val = to_float(gross)
                        p_val = to_float(plug)
                        s_val = to_float(sub)
                        pr_val = to_float(prov)
                        pc_val = to_float(pc)
                        d_val = to_float(dw)
                        
                        is_row_priced = (g_val > 0 or p_val > 0 or s_val > 0 or pr_val > 0 or pc_val > 0 or d_val > 0)
                        if not is_row_priced:
                            if bill_rate_f > 0 and abs(bill_rate_f - dummy_val) > 0.0001:
                                is_row_priced = True
                                
                        is_priced = is_row_priced
                        
                        active_code = pcode if pcode and str(pcode).strip() else rcode
                        master_net_cost = get_net_rate(active_code) if active_code else 0.0
                        
                        unit_cost = 0.0
                        if pr_val > 0: unit_cost = pr_val
                        elif pc_val > 0: unit_cost = pc_val
                        elif d_val > 0: unit_cost = d_val
                        elif master_net_cost > 0: unit_cost = master_net_cost
                        else:
                            if p_val > 0: unit_cost = p_val
                            elif s_val > 0: unit_cost = s_val
                            elif g_val > 0: unit_cost = g_val
                            else:
                                if bill_amt_f > 0:
                                    unit_cost = bill_amt_f if qty_f <= 1 else 0.0
                                    
                        calc_qty = qty_f if qty_f > 0 else (1.0 if bill_amt_f > 0 else 0.0)
                        item_net_cost = round(unit_cost * calc_qty, 2) if is_priced else 0.0
                        
                        sheet_total_items += 1
                        if is_priced: sheet_priced_items += 1
                        sheet_net_cost += item_net_cost
                        
                        if plug and to_float(plug) > 0:
                            sheet_plugged_items += 1
                            
                    conn.close()
                except Exception:
                    pass
                
                combined_markup = (overhead_rate + profit_rate) / 100.0
                sheet_bid_value = sheet_net_cost * (1.0 + combined_markup)
                
                total_items_count += sheet_total_items
                priced_items_count += sheet_priced_items
                plugged_items_count += sheet_plugged_items
                total_priced_value += sheet_bid_value
                
                pboq_sheets.append({
                    "database": f,
                    "total_items": sheet_total_items,
                    "subtotal": round(sheet_bid_value, 2),
                    "priced_items": sheet_priced_items
                })
                
    domains["pboq_summary"] = {
        "sheets": pboq_sheets,
        "total_items_count": total_items_count,
        "priced_items_count": priced_items_count,
        "plugged_items_count": plugged_items_count,
        "total_priced_value": round(total_priced_value, 2),
        "pricing_completeness_percent": round((priced_items_count / total_items_count * 100) if total_items_count > 0 else 0.0, 2)
    }

    # 5. Ingest Analytics Data
    try:
        combined_markup = (overhead_rate + profit_rate) / 100.0
        net_subtotal = total_priced_value / (1.0 + combined_markup) if total_priced_value > 0 else 0.0
        
        outliers_data = get_outlier_items(
            os.path.join(pboq_dir, pboq_sheets[0]["database"]) if pboq_sheets else None
        )
        
        domains["analytics_summary"] = {
            "net_subtotal": round(net_subtotal, 2),
            "grand_total": round(total_priced_value, 2),
            "overhead_amount": round(net_subtotal * (overhead_rate / 100.0), 2),
            "profit_margin_amount": round(net_subtotal * (profit_rate / 100.0), 2),
            "pricing_variance_outliers_count": len(outliers_data.get("outlier_deviations", [])),
            "manual_plugs_count": len(outliers_data.get("manual_plug_rates", []))
        }
    except Exception:
        domains["analytics_summary"] = {
            "net_subtotal": 0.0,
            "grand_total": total_priced_value,
            "pricing_variance_outliers_count": 0,
            "manual_plugs_count": 0
        }

    return domains


def build_unified_knowledge_graph(project_dir=None):
    """
    Assembles a relation-driven semantic knowledge graph for deep project comprehension:
    1. WBS Parsing: Groups items under phases/sections (Substructure, Superstructure, etc.)
    2. Recipe Coupling: Maps active PBOQ items to their composite buildup recipes
    3. Resource Dependency Mapping: Flags missing dependencies (concrete vs steel vs formwork)
    """
    if not project_dir:
        try:
            costs_db = DatabaseManager("construction_costs.db")
            project_dir = costs_db.get_setting('last_project_dir', '')
        except Exception:
            pass

    if project_dir:
        # Strip trailing "Project Database" to locate relative folders (Priced BOQs, SOR, etc.)
        project_dir = project_dir.replace('\\', '/')
        if os.path.basename(project_dir) == "Project Database":
            project_dir = os.path.dirname(project_dir)

    if not project_dir or not os.path.exists(project_dir):
        return {"error": "No active project directory found."}

    proj_db_dir = os.path.join(project_dir, "Project Database")
    master_db_path = None
    if os.path.exists(proj_db_dir):
        dbs = [f for f in os.listdir(proj_db_dir) if f.lower().endswith('.db') and "rates" not in f.lower()]
        if dbs:
            master_db_path = os.path.join(proj_db_dir, dbs[0])

    graph = {
        "wbs_hierarchy": {},
        "recipe_coupling": {},
        "resource_dependencies_warnings": []
    }

    category_prefixes = {
        "Preliminaries": ["PRLM"],
        "Earthworks": ["ETWK"],
        "Concrete": ["CONC"],
        "Formwork": ["FMWK"],
        "Reinforcement": ["RFMT"],
        "Structural Steelwork": ["STLS"],
        "Blockwork": ["WALL"],
        "Flooring": ["FLRG"],
        "Doors & Windows": ["DRWD"],
        "Plastering": ["PLST"],
        "Painting": ["PNTG"],
        "Roadwork & Fencing": ["RDWK"],
        "Miscellaneous": ["MISC"],
        "External Works": ["EXWK"],
        "Waterproofing": ["WPFG"],
        "Precast": ["PRCT"]
    }

    def get_wbs_section(rate_code, description):
        code_upper = str(rate_code).upper().strip()
        desc_lower = str(description).lower()
        
        for section, prefixes in category_prefixes.items():
            for p in prefixes:
                if code_upper.startswith(p):
                    return section
                    
        if "prelim" in desc_lower or "insurance" in desc_lower or "mobilization" in desc_lower:
            return "Preliminaries"
        elif "excavat" in desc_lower or "earth" in desc_lower or "fill" in desc_lower or "pit" in desc_lower or "trench" in desc_lower:
            return "Earthworks"
        elif "concrete" in desc_lower or "grade c" in desc_lower:
            return "Concrete"
        elif "formwork" in desc_lower or "shutter" in desc_lower or "edge" in desc_lower:
            return "Formwork"
        elif "reinforc" in desc_lower or "rebar" in desc_lower or "mesh" in desc_lower or "stirrup" in desc_lower:
            return "Reinforcement"
        elif "brick" in desc_lower or "block" in desc_lower or "wall" in desc_lower:
            return "Blockwork"
        elif "door" in desc_lower or "window" in desc_lower:
            return "Doors & Windows"
        elif "paint" in desc_lower:
            return "Painting"
        elif "plaster" in desc_lower or "screed" in desc_lower:
            return "Plastering"
            
        return "Miscellaneous"

    pboq_dir = os.path.join(project_dir, "Priced BOQs")
    all_pboq_items = []
    
    if os.path.exists(pboq_dir):
        for f in os.listdir(pboq_dir):
            if f.lower().endswith('.db'):
                db_path = os.path.join(pboq_dir, f)
                try:
                    conn = sqlite3.connect(db_path)
                    cursor = conn.cursor()
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pboq_items'")
                    if cursor.fetchone():
                        cursor.execute("PRAGMA table_info(pboq_items)")
                        cols = [col[1] for col in cursor.fetchall()]
                        
                        desc_col = next((c for c in ["Description", "Column 1", "Column 2"] if c in cols), "Description")
                        qty_col = next((c for c in ["Quantity", "Qty", "Column 3"] if c in cols), "Quantity")
                        bill_rate_col = next((c for c in ["Bill Rate", "BillRate", "Column 4"] if c in cols), "BillRate")
                        bill_amt_col = next((c for c in ["Bill Amount", "BillAmount", "Column 5"] if c in cols), "BillAmount")
                        rate_code_col = next((c for c in ["RateCode", "Rate Code", "rate_code"] if c in cols), "RateCode")
                        plug_code_col = next((c for c in ["PlugCode", "Plug Code", "plug_code"] if c in cols), "PlugCode")
                        sheet_col = "Sheet" if "Sheet" in cols else "sheet"
                        
                        query_cols = [sheet_col, desc_col, qty_col, bill_rate_col, bill_amt_col, rate_code_col, plug_code_col]
                        sel_cols = []
                        for c in query_cols:
                            if c in cols:
                                sel_cols.append(f"\"{c}\"")
                            else:
                                sel_cols.append("''")
                                
                        cursor.execute(f"SELECT rowid, {', '.join(sel_cols)} FROM pboq_items")
                        for row in cursor.fetchall():
                            row_id, sheet, desc, qty, br, ba, rcode, pcode = row
                            desc_low = (desc or "").lower()
                            if not str(desc).strip() or "collection" in desc_low or "summary" in desc_low:
                                continue
                            
                            active_code = pcode if pcode and str(pcode).strip() else rcode
                            section = get_wbs_section(active_code, desc)
                            
                            item_dict = {
                                "row_id": row_id,
                                "database": f,
                                "sheet": sheet,
                                "description": desc,
                                "quantity": qty,
                                "bill_rate": br,
                                "bill_amount": ba,
                                "rate_code": active_code,
                                "wbs_section": section
                            }
                            
                            all_pboq_items.append(item_dict)
                            
                            if sheet not in graph["wbs_hierarchy"]:
                                graph["wbs_hierarchy"][sheet] = {}
                            if section not in graph["wbs_hierarchy"][sheet]:
                                graph["wbs_hierarchy"][sheet][section] = []
                            graph["wbs_hierarchy"][sheet][section].append({
                                "row_id": row_id,
                                "description": desc,
                                "bill_amount": ba,
                                "rate_code": active_code
                            })
                    conn.close()
                except Exception:
                    pass

    # Aggregate all database files under the project folder (e.g. Project Database, Imported Library) and the cost library
    estimate_db_paths = []
    if master_db_path and os.path.exists(master_db_path):
        estimate_db_paths.append(master_db_path)
        
    imported_lib_dir = os.path.join(project_dir, "Imported Library")
    if os.path.exists(imported_lib_dir):
        for f in os.listdir(imported_lib_dir):
            if f.endswith('.db'):
                estimate_db_paths.append(os.path.join(imported_lib_dir, f))
                
    costs_db_path = os.path.join(APP_DIR, "construction_costs.db")
    if os.path.exists(costs_db_path):
        estimate_db_paths.append(costs_db_path)

    buildup_recipes = {}
    for db_path in estimate_db_paths:
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='estimates'")
            if not cursor.fetchone():
                conn.close()
                continue
                
            cursor.execute("SELECT id, rate_code, project_name, net_total, grand_total, category FROM estimates")
            ests = cursor.fetchall()
            for est_id, rate_code, name, net, grand, cat in ests:
                if not rate_code:
                    continue
                    
                # Prefer more detailed buildup recipe if we already loaded one
                if rate_code in buildup_recipes:
                    existing = buildup_recipes[rate_code]
                    if len(existing.get("materials", [])) + len(existing.get("labor", [])) > 1:
                        continue
                
                recipe = {
                    "estimate_id": est_id,
                    "description": name,
                    "net_total": net,
                    "grand_total": grand,
                    "category": cat,
                    "materials": [],
                    "labor": [],
                    "equipment": [],
                    "plant": [],
                    "indirect_costs": []
                }
                
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='estimate_materials'")
                if cursor.fetchone():
                    cursor.execute("SELECT name, quantity, unit, price, currency, formula FROM estimate_materials WHERE task_id IN (SELECT id FROM tasks WHERE estimate_id = ?)", (est_id,))
                    for m in cursor.fetchall():
                        recipe["materials"].append({
                            "name": m[0],
                            "quantity": m[1],
                            "unit": m[2],
                            "price": m[3],
                            "currency": m[4],
                            "formula": m[5]
                        })
                        
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='estimate_labor'")
                if cursor.fetchone():
                    cursor.execute("SELECT name_trade, hours, unit, rate, currency, formula FROM estimate_labor WHERE task_id IN (SELECT id FROM tasks WHERE estimate_id = ?)", (est_id,))
                    for l in cursor.fetchall():
                        recipe["labor"].append({
                            "trade": l[0],
                            "hours": l[1],
                            "unit": l[2],
                            "rate": l[3],
                            "currency": l[4],
                            "formula": l[5]
                        })
                        
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='estimate_plant'")
                if cursor.fetchone():
                    cursor.execute("SELECT name_trade, hours, unit, rate, currency, formula FROM estimate_plant WHERE task_id IN (SELECT id FROM tasks WHERE estimate_id = ?)", (est_id,))
                    for p in cursor.fetchall():
                        recipe["plant"].append({
                            "name": p[0],
                            "hours": p[1],
                            "unit": p[2],
                            "rate": p[3],
                            "currency": p[4],
                            "formula": p[5]
                        })
                        
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='estimate_equipment'")
                if cursor.fetchone():
                    cursor.execute("SELECT name_trade, hours, unit, rate, currency, formula FROM estimate_equipment WHERE task_id IN (SELECT id FROM tasks WHERE estimate_id = ?)", (est_id,))
                    for eq in cursor.fetchall():
                        recipe["equipment"].append({
                            "name": eq[0],
                            "hours": eq[1],
                            "unit": eq[2],
                            "rate": eq[3],
                            "currency": eq[4],
                            "formula": eq[5]
                        })
                        
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='estimate_indirect_costs'")
                if cursor.fetchone():
                    cursor.execute("SELECT description, amount, unit, currency, formula FROM estimate_indirect_costs WHERE task_id IN (SELECT id FROM tasks WHERE estimate_id = ?)", (est_id,))
                    for ind in cursor.fetchall():
                        recipe["indirect_costs"].append({
                            "description": ind[0],
                            "amount": ind[1],
                            "unit": ind[2],
                            "currency": ind[3],
                            "formula": ind[4]
                        })
                
                buildup_recipes[rate_code] = recipe
            conn.close()
        except Exception:
            pass

    for item in all_pboq_items:
        rcode = item["rate_code"]
        if rcode and rcode in buildup_recipes:
            graph["recipe_coupling"][item["description"]] = buildup_recipes[rcode]

    sheets = list(set(item["sheet"] for item in all_pboq_items))
    for sheet in sheets:
        sheet_items = [item for item in all_pboq_items if item["sheet"] == sheet]
        
        concrete_slab_items = []
        has_formwork = False
        has_reinforcement = False
        
        for item in sheet_items:
            desc_low = (item["description"] or "").lower()
            rcode_upper = str(item["rate_code"]).upper()
            
            if "concrete" in desc_low and ("bed" in desc_low or "slab" in desc_low or "foundation" in desc_low or "strip" in desc_low):
                concrete_slab_items.append(item)
                
            if "formwork" in desc_low or "shuttering" in desc_low or rcode_upper.startswith("FMWK"):
                has_formwork = True
                
            if "reinforc" in desc_low or "rebar" in desc_low or "mesh" in desc_low or rcode_upper.startswith("RFMT"):
                has_reinforcement = True
                
        if concrete_slab_items:
            for conc_item in concrete_slab_items:
                if not has_formwork:
                    graph["resource_dependencies_warnings"].append({
                        "sheet": sheet,
                        "wbs_section": conc_item["wbs_section"],
                        "item": conc_item["description"],
                        "rate_code": conc_item["rate_code"],
                        "issue": "Formwork (shuttering) record is missing on sheet for concrete slab/foundation item.",
                        "severity": "High"
                    })
                if not has_reinforcement:
                    graph["resource_dependencies_warnings"].append({
                        "sheet": sheet,
                        "wbs_section": conc_item["wbs_section"],
                        "item": conc_item["description"],
                        "rate_code": conc_item["rate_code"],
                        "issue": "Reinforcement steel (rebar/mesh) record is missing on sheet for concrete slab/foundation item.",
                        "severity": "Medium"
                    })

    return graph


def get_active_project_priced_items(project_dir=None):
    """
    Retrieves all priced items across all PBOQ databases in the project directory,
    properly mapping columns and filtering dummy rates.
    """
    if not project_dir:
        try:
            costs_db = DatabaseManager("construction_costs.db")
            project_dir = costs_db.get_setting('last_project_dir', '')
        except:
            pass

    if project_dir:
        project_dir = project_dir.replace('\\', '/')
        if os.path.basename(project_dir) == "Project Database":
            project_dir = os.path.dirname(project_dir)

    priced_items_list = []
    if not project_dir or not os.path.exists(project_dir):
        return priced_items_list

    pboq_dir = os.path.join(project_dir, "Priced BOQs")
    if os.path.exists(pboq_dir):
        dbs = [os.path.join(pboq_dir, f) for f in os.listdir(pboq_dir) if f.endswith('.db')]
        for path in dbs:
            f = os.path.basename(path)
            sheet_name = f.replace('.db', '')
            
            qty_col_idx = -1
            desc_col_idx = -1
            bill_rate_col_idx = -1
            bill_amt_col_idx = -1
            unit_col_idx = -1
            dummy_val = 0.1
            
            state_file = os.path.join(project_dir, "PBOQ States", f + ".json")
            state_data = {}
            if os.path.exists(state_file):
                try:
                    with open(state_file, 'r', encoding='utf-8') as sf:
                        state_data = json.load(sf)
                        m = state_data.get('mappings', {})
                        qty_col_idx = m.get('qty', -1)
                        desc_col_idx = m.get('desc', -1)
                        bill_rate_col_idx = m.get('bill_rate', -1)
                        bill_amt_col_idx = m.get('bill_amount', -1)
                        unit_col_idx = m.get('unit', -1)
                        dummy_val = state_data.get('dummy_rate', 0.1)
                except: pass
                
            try:
                conn = sqlite3.connect(path)
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pboq_items'")
                if not cursor.fetchone():
                    conn.close()
                    continue
                    
                cursor.execute("PRAGMA table_info(pboq_items)")
                cols = [info[1] for info in cursor.fetchall()]
                
                qty_name = cols[qty_col_idx + 1] if qty_col_idx >= 0 and (qty_col_idx + 1) < len(cols) else next((c for c in cols if c.lower() in ["quantity", "qty"]), None)
                desc_name = cols[desc_col_idx + 1] if desc_col_idx >= 0 and (desc_col_idx + 1) < len(cols) else next((c for c in cols if c.lower() in ["description", "desc"]), None)
                bill_rate_name = cols[bill_rate_col_idx + 1] if bill_rate_col_idx >= 0 and (bill_rate_col_idx + 1) < len(cols) else next((c for c in cols if c.lower() in ["bill rate", "billrate", "column 4"]), None)
                bill_amt_name = cols[bill_amt_col_idx + 1] if bill_amt_col_idx >= 0 and (bill_amt_col_idx + 1) < len(cols) else next((c for c in cols if c.lower() in ["bill amount", "billamount", "column 5"]), None)
                unit_name = cols[unit_col_idx + 1] if unit_col_idx >= 0 and (unit_col_idx + 1) < len(cols) else next((c for c in cols if c.lower() in ["unit"]), None)
                
                col_map = {
                    'desc': desc_name,
                    'qty': qty_name,
                    'bill_rate': bill_rate_name,
                    'bill_amt': bill_amt_name,
                    'unit': unit_name,
                    'gross': next((c for c in cols if c.lower() in ["grossrate", "gross_rate"]), None),
                    'plug': next((c for c in cols if c.lower() in ["plugrate", "plug_rate"]), None),
                    'sub': next((c for c in cols if c.lower() in ["subbeerate", "sub_rate"]), None),
                    'prov': next((c for c in cols if c.lower() in ["provsum", "prov_sum"]), None),
                    'pc': next((c for c in cols if c.lower() in ["pcsum", "pc_sum"]), None),
                    'dw': next((c for c in cols if c.lower() in ["daywork"]), None),
                    'rcode': next((c for c in cols if c.lower() in ["ratecode", "rate_code"]), None),
                    'pcode': next((c for c in cols if c.lower() in ["plugcode", "plug_code"]), None),
                    'sheet': next((c for c in cols if c.lower() == 'sheet'), None)
                }
                
                if not (col_map['desc'] and col_map['qty']):
                    conn.close()
                    continue
                    
                query_cols = []
                for k in ['desc', 'qty', 'bill_rate', 'bill_amt', 'gross', 'plug', 'sub', 'prov', 'pc', 'dw', 'rcode', 'pcode', 'unit', 'sheet']:
                    if col_map[k]: query_cols.append(f"\"{col_map[k]}\"")
                    else: query_cols.append("''")
                    
                cursor.execute(f"SELECT {', '.join(query_cols)} FROM pboq_items")
                rows = cursor.fetchall()
                
                rate_cache = {}
                def get_net_rate(rate_code):
                    if not rate_code: return 0.0
                    if rate_code in rate_cache: return rate_cache[rate_code]
                    try:
                        db_dir2 = os.path.join(project_dir, "Project Database")
                        dbs2 = [f2 for f2 in os.listdir(db_dir2) if f2.lower().endswith('.db') and "rates" not in f2.lower()]
                        if dbs2:
                            db_path2 = os.path.join(db_dir2, dbs2[0])
                            conn2 = sqlite3.connect(db_path2)
                            cursor2 = conn2.cursor()
                            cursor2.execute("SELECT net_total FROM estimates WHERE rate_code = ?", (rate_code,))
                            res = cursor2.fetchone()
                            conn2.close()
                            if res:
                                rate_cache[rate_code] = float(res[0] or 0.0)
                                return rate_cache[rate_code]
                    except: pass
                    rate_cache[rate_code] = 0.0
                    return 0.0
                    
                def to_float(val):
                    if not val: return 0.0
                    if isinstance(val, (int, float)): return float(val)
                    try: return float(str(val).replace(',', '').replace(' ', '').replace('₵','').replace('$','').strip())
                    except: return 0.0
                    
                for r in rows:
                    desc, q, br, ba, gross, plug, sub, prov, pc, dw, rcode, pcode, unit, row_sheet = r
                    desc_low = (desc or "").lower()
                    if not str(desc).strip() or "collection" in desc_low or "summary" in desc_low:
                        continue
                        
                    qty_f = to_float(q)
                    bill_rate_f = to_float(br)
                    bill_amt_f = to_float(ba)
                    
                    if qty_f == 0 and bill_amt_f == 0:
                        continue
                        
                    g_val = to_float(gross)
                    p_val = to_float(plug)
                    s_val = to_float(sub)
                    pr_val = to_float(prov)
                    pc_val = to_float(pc)
                    d_val = to_float(dw)
                    
                    is_row_priced = (g_val > 0 or p_val > 0 or s_val > 0 or pr_val > 0 or pc_val > 0 or d_val > 0)
                    if not is_row_priced:
                        if bill_rate_f > 0 and abs(bill_rate_f - dummy_val) > 0.0001:
                            is_row_priced = True
                            
                    is_priced = is_row_priced
                    
                    if is_priced:
                        active_code = pcode if pcode and str(pcode).strip() else rcode
                        master_net_cost = get_net_rate(active_code) if active_code else 0.0
                        
                        unit_cost = 0.0
                        if pr_val > 0: unit_cost = pr_val
                        elif pc_val > 0: unit_cost = pc_val
                        elif d_val > 0: unit_cost = d_val
                        elif master_net_cost > 0: unit_cost = master_net_cost
                        else:
                            if p_val > 0: unit_cost = p_val
                            elif s_val > 0: unit_cost = s_val
                            elif g_val > 0: unit_cost = g_val
                            else:
                                if bill_amt_f > 0:
                                    unit_cost = bill_amt_f if qty_f <= 1 else 0.0
                                    
                        calc_qty = qty_f if qty_f > 0 else (1.0 if bill_amt_f > 0 else 0.0)
                        item_net_cost = round(unit_cost * calc_qty, 2)
                        
                        priced_items_list.append({
                            "sheet": row_sheet or sheet_name,
                            "description": desc,
                            "qty": qty_f,
                            "unit": unit or "each",
                            "net_rate": unit_cost,
                            "net_amount": item_net_cost
                        })
                        
                conn.close()
            except Exception:
                pass
                
    return priced_items_list


def get_context_suggestions(main_window=None):
    """
    Dynamically generates 3-4 relevant suggested prompts based on the current
    active window context or loaded project state.
    """
    suggestions = []
    
    # Check if there is an active window in the PyQt6 workspace
    active_win = None
    if main_window:
        try:
            active_win = main_window._get_active_estimate_window()
        except:
            pass
            
    active_class = getattr(active_win, '__class__', None).__name__ if active_win else None
    
    if active_win and active_class == 'PBOQDialog':
        suggestions = [
            "Analyze project outliers",
            "Show plugged rates needing review",
            "Generate subcontractor markup comparison",
            "Check for concrete slab under-measurement"
        ]
    elif active_win and hasattr(active_win, 'estimate'):
        # Rate Build-up Editor
        est = active_win.estimate
        rate_code = getattr(est, 'rate_code', '')
        if rate_code and rate_code != 'N/A':
            suggestions = [
                f"Explain recipe breakdown for {rate_code}",
                f"Check alternative rates for {rate_code}",
                "Suggest subcontractor quotes for this rate",
                "Show active estimate KPIs"
            ]
        else:
            suggestions = [
                "Explain composite rate buildup",
                "Optimize labor-plant ratios",
                "Show active estimate KPIs",
                "Search historical rates for Concrete"
            ]
    else:
        # Fallback to general estimation queries based on loaded project
        try:
            summary = query_active_estimate_summary(main_window)
            if summary and "status" not in summary:
                proj_name = summary.get("project_name", "")
                suggestions = [
                    f"Show active estimate KPIs for {proj_name}",
                    "Analyze project outliers",
                    "Search historical rates for Concrete",
                    "Verify under-measurement warnings"
                ]
            else:
                suggestions = [
                    "Show active estimate KPIs",
                    "Analyze project outliers",
                    "Search historical rates for Concrete",
                    "What if concrete prices increase by 10%?"
                ]
        except:
            suggestions = [
                "Show active estimate KPIs",
                "Analyze project outliers",
                "Search historical rates for Concrete",
                "What if concrete prices increase by 10%?"
            ]
            
    return suggestions[:4]


def generate_report(project_dir=None, report_type="executive_summary"):
    """
    AI-triggered PDF report generation using report_generator.py.
    """
    if project_dir is None:
        try:
            costs_db = DatabaseManager("construction_costs.db")
            project_dir = costs_db.get_setting('last_project_dir', '')
        except Exception:
            pass
            
    if not project_dir or not os.path.exists(project_dir):
        return {"status": "error", "message": "No active project directory found or it does not exist."}
        
    project_dir = project_dir.replace('\\', '/')
    if os.path.basename(project_dir) == "Project Database":
        project_dir = os.path.dirname(project_dir)
        
    try:
        from report_generator import ExecutiveAnalyticsReportGenerator
        output_pdf_path = os.path.join(project_dir, "Executive_Project_Intelligence_Report.pdf").replace('\\', '/')
        generator = ExecutiveAnalyticsReportGenerator(project_dir)
        success = generator.generate_report(output_pdf_path)
        if success:
            return {"status": "success", "file_path": output_pdf_path}
        else:
            return {"status": "error", "message": "Failed to compile the PDF report."}
    except Exception as e:
        return {"status": "error", "message": f"Error during report generation: {str(e)}"}


def get_subcontractor_quotes(project_dir=None):
    """
    Scan all .db files in project_dir/Priced BOQs/.
    Run schema-adaptive queries joining subcontractor_quotes and pboq_items on row_idx=rowid.
    Group by (package, subcontractor) and return bid totals and item counts.
    """
    if project_dir is None:
        try:
            costs_db = DatabaseManager("construction_costs.db")
            project_dir = costs_db.get_setting('last_project_dir', '')
        except Exception:
            pass
            
    if not project_dir or not os.path.exists(project_dir):
        return []
        
    project_dir = project_dir.replace('\\', '/')
    if os.path.basename(project_dir) == "Project Database":
        project_dir = os.path.dirname(project_dir)
        
    pboq_dir = os.path.join(project_dir, "Priced BOQs")
    if not os.path.exists(pboq_dir):
        return []
        
    quotes = []
    
    try:
        db_files = [f for f in os.listdir(pboq_dir) if f.lower().endswith('.db')]
        for db_file in db_files:
            db_path = os.path.join(pboq_dir, db_file)
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Check if subcontractor_quotes table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='subcontractor_quotes'")
            if not cursor.fetchone():
                conn.close()
                continue
                
            query = """
                SELECT 
                    q.package_name AS package,
                    q.subcontractor_name AS subcontractor,
                    COUNT(q.row_idx) AS item_count,
                    SUM(COALESCE(p.quantity, 0) * COALESCE(q.rate, 0)) AS total_quoted
                FROM subcontractor_quotes q
                LEFT JOIN pboq_items p ON p.rowid = q.row_idx
                GROUP BY q.package_name, q.subcontractor_name
            """
            try:
                cursor.execute(query)
                rows = cursor.fetchall()
                for row in rows:
                    quotes.append({
                        "package": row["package"],
                        "subcontractor": row["subcontractor"],
                        "items_count": row["item_count"],
                        "total_quoted": float(row["total_quoted"]) if row["total_quoted"] is not None else 0.0,
                        "db_file": db_file
                    })
            except Exception:
                try:
                    fallback_query = """
                        SELECT 
                            package_name AS package,
                            subcontractor_name AS subcontractor,
                            COUNT(row_idx) AS item_count,
                            SUM(COALESCE(rate, 0)) AS total_quoted
                        FROM subcontractor_quotes
                        GROUP BY package_name, subcontractor_name
                    """
                    cursor.execute(fallback_query)
                    rows = cursor.fetchall()
                    for row in rows:
                        quotes.append({
                            "package": row["package"],
                            "subcontractor": row["subcontractor"],
                            "items_count": row["item_count"],
                            "total_quoted": float(row["total_quoted"]) if row["total_quoted"] is not None else 0.0,
                            "db_file": db_file,
                            "is_fallback": True
                        })
                except Exception:
                    pass
            finally:
                conn.close()
    except Exception:
        pass
        
    return quotes


def run_what_if_scenario(project_dir=None, resource_type="materials", resource_name_pattern="", adjustment_percent=0.0):
    """
    Runs in-memory what-if scenarios modeling resource price adjustments
    and calculates cascading subtotal, markup, and grand total changes.
    """
    if project_dir is None:
        try:
            costs_db = DatabaseManager("construction_costs.db")
            project_dir = costs_db.get_setting('last_project_dir', '')
        except Exception:
            pass
            
    if not project_dir or not os.path.exists(project_dir):
        return {"error": "No active project directory found."}
        
    project_dir = project_dir.replace('\\', '/')
    if os.path.basename(project_dir) == "Project Database":
        project_dir = os.path.dirname(project_dir)
        
    proj_db_dir = os.path.join(project_dir, "Project Database")
    master_db_path = None
    if os.path.exists(proj_db_dir):
        dbs = [f for f in os.listdir(proj_db_dir) if f.lower().endswith('.db') and "rates" not in f.lower()]
        if dbs:
            master_db_path = os.path.join(proj_db_dir, dbs[0])
            
    if not master_db_path or not os.path.exists(master_db_path):
        return {"error": "Master database not found."}
        
    # Parse adjustment
    adj = 0.0
    if isinstance(adjustment_percent, str):
        cleaned = adjustment_percent.replace('%', '').strip()
        if cleaned.startswith('+'):
            cleaned = cleaned[1:]
        try:
            adj = float(cleaned)
            if '%' in adjustment_percent:
                adj /= 100.0
        except ValueError:
            pass
    else:
        adj = float(adjustment_percent)
        
    multiplier = 1.0 + adj
    
    conn = sqlite3.connect(master_db_path)
    cursor = conn.cursor()
    
    # Get overhead and profit margin
    overhead_percent = 0.0
    profit_percent = 0.0
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='estimates'")
    if cursor.fetchone():
        cursor.execute("SELECT overhead_percent, profit_margin_percent FROM estimates LIMIT 1")
        row = cursor.fetchone()
        if row:
            overhead_percent = row[0] or 0.0
            profit_percent = row[1] or 0.0
            
    # Task resources
    cursor.execute("SELECT id, description FROM tasks")
    tasks = [{"id": r[0], "description": r[1]} for r in cursor.fetchall()]
    
    matched_items = []
    before_net_total = 0.0
    after_net_total = 0.0
    
    resource_type_lower = resource_type.lower()
    pattern_lower = resource_name_pattern.lower()
    
    for task in tasks:
        task_id = task["id"]
        
        # 1. Materials
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='estimate_materials'")
        if cursor.fetchone():
            cursor.execute("SELECT name, quantity, price FROM estimate_materials WHERE task_id = ?", (task_id,))
            for name, qty, price in cursor.fetchall():
                qty = qty or 0.0
                price = price or 0.0
                before_val = qty * price
                before_net_total += before_val
                
                is_match = (resource_type_lower in ["materials", "material"]) and (pattern_lower in name.lower())
                if is_match:
                    after_price = price * multiplier
                    after_val = qty * after_price
                    matched_items.append({
                        "name": name,
                        "type": "material",
                        "quantity": qty,
                        "before_price": price,
                        "after_price": after_price,
                        "task": task["description"]
                    })
                else:
                    after_val = before_val
                after_net_total += after_val
                
        # 2. Labor
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='estimate_labor'")
        if cursor.fetchone():
            cursor.execute("SELECT name_trade, hours, rate FROM estimate_labor WHERE task_id = ?", (task_id,))
            for trade, hours, rate in cursor.fetchall():
                hours = hours or 0.0
                rate = rate or 0.0
                before_val = hours * rate
                before_net_total += before_val
                
                is_match = (resource_type_lower in ["labor", "labour"]) and (pattern_lower in trade.lower())
                if is_match:
                    after_rate = rate * multiplier
                    after_val = hours * after_rate
                    matched_items.append({
                        "name": trade,
                        "type": "labor",
                        "quantity": hours,
                        "before_price": rate,
                        "after_price": after_rate,
                        "task": task["description"]
                    })
                else:
                    after_val = before_val
                after_net_total += after_val
                
        # 3. Plant
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='estimate_plant'")
        if cursor.fetchone():
            cursor.execute("SELECT name_trade, hours, rate FROM estimate_plant WHERE task_id = ?", (task_id,))
            for name, hours, rate in cursor.fetchall():
                hours = hours or 0.0
                rate = rate or 0.0
                before_val = hours * rate
                before_net_total += before_val
                
                is_match = (resource_type_lower in ["plant"]) and (pattern_lower in name.lower())
                if is_match:
                    after_rate = rate * multiplier
                    after_val = hours * after_rate
                    matched_items.append({
                        "name": name,
                        "type": "plant",
                        "quantity": hours,
                        "before_price": rate,
                        "after_price": after_rate,
                        "task": task["description"]
                    })
                else:
                    after_val = before_val
                after_net_total += after_val
                
        # 4. Equipment
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='estimate_equipment'")
        if cursor.fetchone():
            cursor.execute("SELECT name_trade, hours, rate FROM estimate_equipment WHERE task_id = ?", (task_id,))
            for name, hours, rate in cursor.fetchall():
                hours = hours or 0.0
                rate = rate or 0.0
                before_val = hours * rate
                before_net_total += before_val
                
                is_match = (resource_type_lower in ["equipment"]) and (pattern_lower in name.lower())
                if is_match:
                    after_rate = rate * multiplier
                    after_val = hours * after_rate
                    matched_items.append({
                        "name": name,
                        "type": "equipment",
                        "quantity": hours,
                        "before_price": rate,
                        "after_price": after_rate,
                        "task": task["description"]
                    })
                else:
                    after_val = before_val
                after_net_total += after_val

        # 5. Indirect Costs
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='estimate_indirect_costs'")
        if cursor.fetchone():
            cursor.execute("SELECT description, amount FROM estimate_indirect_costs WHERE task_id = ?", (task_id,))
            for desc, amount in cursor.fetchall():
                amount = amount or 0.0
                before_val = amount
                before_net_total += before_val
                
                is_match = (resource_type_lower in ["indirect", "indirect_costs", "indirect cost"]) and (pattern_lower in desc.lower())
                if is_match:
                    after_amount = amount * multiplier
                    after_val = after_amount
                    matched_items.append({
                        "name": desc,
                        "type": "indirect",
                        "quantity": 1,
                        "before_price": amount,
                        "after_price": after_amount,
                        "task": task["description"]
                    })
                else:
                    after_val = before_val
                after_net_total += after_val
                
    conn.close()
    
    # Recalculate cascading totals: task subtotals -> estimate net -> markup -> grand total
    before_overhead = before_net_total * (overhead_percent / 100.0)
    before_profit = (before_net_total + before_overhead) * (profit_percent / 100.0)
    before_grand_total = before_net_total + before_overhead + before_profit
    
    after_overhead = after_net_total * (overhead_percent / 100.0)
    after_profit = (after_net_total + after_overhead) * (profit_percent / 100.0)
    after_grand_total = after_net_total + after_overhead + after_profit
    
    delta_net = after_net_total - before_net_total
    delta_grand = after_grand_total - before_grand_total
    delta_percent = (delta_grand / before_grand_total * 100.0) if before_grand_total != 0.0 else 0.0
    
    return {
        "matched_items": matched_items,
        "before": {
            "net_total": before_net_total,
            "overhead": before_overhead,
            "profit": before_profit,
            "grand_total": before_grand_total
        },
        "after": {
            "net_total": after_net_total,
            "overhead": after_overhead,
            "profit": after_profit,
            "grand_total": after_grand_total
        },
        "delta": {
            "net": delta_net,
            "grand": delta_grand,
            "percent": delta_percent
        }
    }


def recommend_composite_buildup(item_description, unit="each", project_dir=None):
    """
    Searches historical library and project databases for a composite rate buildup
    similar to the requested item description.
    """
    import re
    if project_dir is None:
        try:
            costs_db = DatabaseManager("construction_costs.db")
            project_dir = costs_db.get_setting('last_project_dir', '')
        except Exception:
            pass
            
    if project_dir:
        project_dir = project_dir.replace('\\', '/')
        if os.path.basename(project_dir) == "Project Database":
            project_dir = os.path.dirname(project_dir)
            
    db_paths = []
    rates_db_path = "construction_rates.db"
    if os.path.exists(rates_db_path):
        db_paths.append(("Historical Library", rates_db_path))
        
    if project_dir and os.path.exists(project_dir):
        for sub_folder in ["Imported Library", "Project Database", "Priced BOQs", "SOR"]:
            folder_path = os.path.join(project_dir, sub_folder)
            if os.path.exists(folder_path):
                for f in os.listdir(folder_path):
                    if f.endswith('.db'):
                        db_paths.append((f, os.path.join(folder_path, f)))
                        
    best_match = None
    best_score = -1
    best_db_path = None
    
    target_words = set(w.lower() for w in re.split(r'\W+', item_description) if len(w) > 2)
    if not target_words:
        target_words = {item_description.lower()}
        
    for db_name, db_path in db_paths:
        try:
            db = DatabaseManager(db_path)
            rates = db.get_rates_data()
            for r in rates:
                desc = str(r.get('project_name', '') or '')
                code = str(r.get('rate_code', '') or '')
                
                desc_words = set(w.lower() for w in re.split(r'\W+', desc) if len(w) > 2)
                overlap = len(target_words.intersection(desc_words))
                
                score = overlap
                r_unit = r.get('unit', '')
                if r_unit and unit and r_unit.lower().strip() == unit.lower().strip():
                    score += 0.5
                    
                if score > best_score and score > 0:
                    best_score = score
                    best_match = r
                    best_db_path = db_path
        except Exception:
            pass
            
    if best_match and best_db_path:
        try:
            db = DatabaseManager(best_db_path)
            est = db.load_estimate_details(best_match['id'])
            if est:
                recipe = {
                    "matched_rate_code": est.rate_code,
                    "description": est.project_name,
                    "unit": est.unit,
                    "net_rate": est.net_total,
                    "gross_rate": est.grand_total,
                    "confidence": "high" if best_score >= 3 else ("medium" if best_score >= 1.5 else "low"),
                    "materials": [],
                    "labor": [],
                    "plant": [],
                    "equipment": [],
                    "indirect_costs": []
                }
                
                for task in est.tasks:
                    for m in task.materials:
                        recipe["materials"].append({
                            "name": m["name"],
                            "qty": m["qty"],
                            "unit": m["unit"],
                            "unit_cost": m["unit_cost"],
                            "currency": m.get("currency", "USD")
                        })
                    for l in task.labor:
                        recipe["labor"].append({
                            "trade": l["trade"],
                            "hours": l["hours"],
                            "unit": l.get("unit", "hr"),
                            "rate": l["rate"],
                            "currency": l.get("currency", "USD")
                        })
                    for p in task.plant:
                        recipe["plant"].append({
                            "name": p["name"],
                            "hours": p["hours"],
                            "unit": p.get("unit", "hr"),
                            "rate": p["rate"],
                            "currency": p.get("currency", "USD")
                        })
                    for eq in task.equipment:
                        recipe["equipment"].append({
                            "name": eq["name"],
                            "hours": eq["hours"],
                            "unit": eq.get("unit", "hr"),
                            "rate": eq["rate"],
                            "currency": eq.get("currency", "USD")
                        })
                    for ind in task.indirect_costs:
                        recipe["indirect_costs"].append({
                            "description": ind["description"],
                            "amount": ind["amount"],
                            "unit": ind.get("unit", "each"),
                            "currency": ind.get("currency", "USD")
                        })
                        
                return recipe
        except Exception:
            pass
            
    suggestions = []
    try:
        rates_db = DatabaseManager("construction_rates.db")
        rates = rates_db.get_rates_data()
        for r in rates[:3]:
            suggestions.append(f"{r.get('rate_code')} - {r.get('project_name')} ({r.get('unit')})")
    except Exception:
        pass
        
    return {
        "status": "no_match",
        "suggestions": suggestions or ["CONC1A - Reinforced concrete slab 200mm (m3)", "EXC1A - Excavation & Earthworks (m3)"]
    }




