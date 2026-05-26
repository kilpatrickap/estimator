import os
import json
import re
import sqlite3
import urllib.request
import urllib.error
from PyQt6.QtCore import QRunnable, QObject, pyqtSignal
import ai_tools

APP_DIR = os.path.dirname(os.path.abspath(__file__))

class AICopilotSignals(QObject):
    """
    Defines thread-safe signals for communication between background
    asynchronous workers and the main PyQt6 GUI thread.
    """
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    partial_message = pyqtSignal(str)

class AICopilotWorker(QRunnable):
    """
    Asynchronous QRunnable background worker executing context-aware queries
    against SQLite databases, local workspace structures, and local LLM thinking models.
    """
    def __init__(self, user_query, main_window=None):
        super().__init__()
        self.user_query = user_query
        self.main_window = main_window
        self.signals = AICopilotSignals()

    def run(self):
        try:
            # 1. Extract active project paths from MainWindow if available
            pboq_path = None
            project_dir = None
            if self.main_window:
                active_win = self.main_window._get_active_estimate_window()
                active_class = getattr(active_win, '__class__', None).__name__ if active_win else None
                if active_class == 'PBOQDialog' and hasattr(active_win, 'pboq_file_selector'):
                    pboq_path = active_win.pboq_file_selector.currentData()
                    if pboq_path:
                        project_dir = os.path.dirname(os.path.dirname(pboq_path))
                elif active_class == 'AnalyticsDashboard' and hasattr(active_win, 'project_dir'):
                    project_dir = active_win.project_dir

            # Resolve project_dir from settings if not set
            if not project_dir:
                try:
                    from database import DatabaseManager
                    costs_db = DatabaseManager("construction_costs.db")
                    project_dir = costs_db.get_setting('last_project_dir', '')
                except:
                    pass

            if project_dir and os.path.exists(project_dir):
                project_dir = project_dir.replace('\\', '/')
                if os.path.basename(project_dir) == "Project Database":
                    project_dir = os.path.dirname(project_dir)
                
                # Try to load last active/viewed PBOQ sheet from viewer_state.json
                state_file = os.path.join(project_dir, "PBOQ States", "viewer_state.json")
                if os.path.exists(state_file):
                    try:
                        with open(state_file, 'r') as sf:
                            state_data = json.load(sf)
                            last_bill = state_data.get('last_bill')
                            if last_bill:
                                cand_path = os.path.join(project_dir, "Priced BOQs", last_bill)
                                if os.path.exists(cand_path):
                                    pboq_path = cand_path
                    except:
                        pass

            # Fallback A: Detect best PBOQ database from loaded project folder if no active window has it
            if not pboq_path and project_dir:
                try:
                    pboq_dir = os.path.join(project_dir, "Priced BOQs")
                    if os.path.exists(pboq_dir):
                        dbs = [os.path.join(pboq_dir, f) for f in os.listdir(pboq_dir) if f.endswith('.db')]
                        best_pboq = None
                        max_items = -1
                        for p in dbs:
                            try:
                                conn = sqlite3.connect(p)
                                cursor = conn.cursor()
                                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pboq_items'")
                                if cursor.fetchone():
                                    cursor.execute("SELECT COUNT(*) FROM pboq_items")
                                    total_items = cursor.fetchone()[0]
                                    if total_items > max_items or (total_items == max_items and os.path.basename(p).startswith("PBOQ_")):
                                        max_items = total_items
                                        best_pboq = p
                                conn.close()
                            except Exception:
                                pass
                        if best_pboq:
                            pboq_path = best_pboq
                except Exception:
                    pass

            # 2. Gather full local context from project tools
            workspace_files = ai_tools.get_workspace_structure()
            active_summary = ai_tools.query_active_estimate_summary(self.main_window)
            outliers_data = ai_tools.get_outlier_items(pboq_path)

            # Resolve target local LLM model dynamically
            model_name = "lfm2:24b"
            try:
                from database import DatabaseManager
                costs_db = DatabaseManager("construction_costs.db")
                model_name = costs_db.get_setting("ai_model_name", "lfm2:24b")
            except Exception:
                pass

            try:
                # 3. Try to call the local LLM thinking model via Ollama
                response_text = self._call_local_ollama(active_summary, workspace_files, outliers_data)
                self.signals.finished.emit(response_text)
            except Exception as ollama_err:
                # 4. Handle connection or model loading error strictly: notify the user and offer setup instructions
                error_msg = str(ollama_err)
                notice = (
                    f"### 🔌 Cannot Connect to AI Reasoner\n\n"
                    f"The AI Estimating Copilot requires a running local Ollama instance with the **{model_name}** model installed. "
                    f"We encountered the following issue:\n"
                    f"> **{error_msg}**\n\n"
                    f"#### 🛠️ How to start the AI Reasoner:\n"
                    f"1. **Download & Install Ollama** from [ollama.com](https://ollama.com).\n"
                    f"2. **Download the model** by running the following command in your terminal:\n"
                    f"   ```bash\n"
                    f"   ollama run {model_name}\n"
                    f"   ```\n"
                    f"3. **Ensure Ollama is running** in the background, then try sending your query again."
                )
                self.signals.finished.emit(notice)
        except Exception as e:
            self.signals.error.emit(f"AI Worker Execution Error: {str(e)}")

    def _resolve_file_path(self, target_path):
        """
        Resolves the absolute path of a database or JSON file by checking the app directory,
        recursively searching the workspace, and scanning the active project directory if loaded.
        """
        if not target_path:
            return None
            
        target_path = target_path.replace('\\', '/')
        
        # 1. If absolute, check if it exists
        if os.path.isabs(target_path) and os.path.exists(target_path):
            return target_path
            
        # 2. Check directly in APP_DIR
        direct_app = os.path.join(APP_DIR, target_path)
        if os.path.exists(direct_app):
            return direct_app
            
        # 3. Check relative to APP_DIR if target_path has basename
        basename = os.path.basename(target_path)
        direct_app_base = os.path.join(APP_DIR, basename)
        if os.path.exists(direct_app_base):
            return direct_app_base
            
        # 4. Walk APP_DIR to find match
        for root, dirs, files in os.walk(APP_DIR):
            dirs[:] = [d for d in dirs if d not in {'.git', '.idea', '__pycache__', '.pytest_cache', '.vscode', 'PyTest'}]
            for f in files:
                full_f = os.path.join(root, f)
                rel_f = os.path.relpath(full_f, APP_DIR).replace('\\', '/')
                if rel_f == target_path or f == target_path or f == basename:
                    return full_f
                    
        # 5. Check in loaded project directory
        try:
            from database import DatabaseManager
            costs_db = DatabaseManager("construction_costs.db")
            project_dir = costs_db.get_setting('last_project_dir', '')
            if project_dir and os.path.exists(project_dir):
                proj_base = os.path.basename(project_dir)
                
                # Strip the project base prefix if present
                clean_target = target_path
                if target_path.startswith(f"{proj_base}/"):
                    clean_target = target_path[len(proj_base)+1:]
                    
                direct_proj = os.path.join(project_dir, clean_target)
                if os.path.exists(direct_proj):
                    return direct_proj
                    
                # Search recursively inside project folder
                for root, dirs, files in os.walk(project_dir):
                    for f in files:
                        full_f = os.path.join(root, f)
                        rel_f = os.path.relpath(full_f, project_dir).replace('\\', '/')
                        if rel_f == clean_target or f == clean_target or f == basename:
                            return full_f
        except Exception:
            pass
            
        # 6. Fuzzy alphanumeric fallback (ignores typos like missing underscores, spaces, hyphens)
        clean_target = re.sub(r'[^a-zA-Z0-9]', '', target_path.lower())
        if clean_target.endswith('db') or clean_target.endswith('json'):
            # Match APP_DIR
            for root, dirs, files in os.walk(APP_DIR):
                dirs[:] = [d for d in dirs if d not in {'.git', '.idea', '__pycache__', '.pytest_cache', '.vscode', 'PyTest'}]
                for f in files:
                    if re.sub(r'[^a-zA-Z0-9]', '', f.lower()) == clean_target:
                        return os.path.join(root, f)
            # Match project_dir
            try:
                from database import DatabaseManager
                costs_db = DatabaseManager("construction_costs.db")
                project_dir = costs_db.get_setting('last_project_dir', '')
                if project_dir and os.path.exists(project_dir):
                    for root, dirs, files in os.walk(project_dir):
                        for f in files:
                            if re.sub(r'[^a-zA-Z0-9]', '', f.lower()) == clean_target:
                                return os.path.join(root, f)
            except Exception:
                pass
            
        return None

    def _execute_sql(self, db_name, sql_query):
        """
        Executes a custom SQLite query on a specified database file and formats the result as a markdown table.
        """
        resolved_db = self._resolve_file_path(db_name)
        if not resolved_db:
            return f"Error: Database file '{db_name}' could not be located in the workspace or active project directory."
            
        try:
            conn = sqlite3.connect(resolved_db)
            cursor = conn.cursor()
            cursor.execute(sql_query)
            rows = cursor.fetchall()
            
            # Extract column headers
            cols = [description[0] for description in cursor.description] if cursor.description else []
            conn.close()
            
            if not rows:
                return "Query completed successfully. No rows returned."
                
            # Build markdown table representation
            md = "| " + " | ".join(cols) + " |\n"
            md += "| " + " | ".join(["---"] * len(cols)) + " |\n"
            for row in rows[:50]:  # Limit output to prevent context window explosion
                row_str = [str(val) if val is not None else "NULL" for val in row]
                md += "| " + " | ".join(row_str) + " |\n"
                
            if len(rows) > 50:
                md += f"\n*(Showing first 50 of {len(rows)} rows)*"
            return md
        except Exception as e:
            error_str = str(e)
            try:
                import re
                table_match = re.search(r'FROM\s+["\']?([a-zA-Z0-9_]+)["\']?', sql_query, re.IGNORECASE)
                if table_match:
                    tbl = table_match.group(1)
                    cursor.execute(f"PRAGMA table_info(\"{tbl}\");")
                    cols = [row[1] for row in cursor.fetchall()]
                    if cols:
                        return f"Error executing SQL: {error_str}. Note that table '{tbl}' has columns: {', '.join(cols)}. Please correct the SQL query to use only these columns."
            except Exception:
                pass
            return f"Error executing SQL: {error_str}"

    def _read_json(self, file_name):
        """
        Locates and reads the contents of a JSON file.
        """
        resolved_file = self._resolve_file_path(file_name)
        if not resolved_file:
            return f"Error: JSON file '{file_name}' could not be located in the workspace or active project directory."
            
        try:
            with open(resolved_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return json.dumps(data, indent=2)
        except Exception as e:
            return f"Error reading JSON: {str(e)}"

    def _format_proactive_context_as_response(self, extra_context):
        """
        Extracts rate/search data from the pre-built extra_context string and formats
        it as a clean markdown table. Used as a fallback when the LLM returns an empty response
        but the proactive context already contains the answer.
        """
        lines = extra_context.split('\n')
        response_parts = []
        
        # Extract historical/library rate entries
        rate_entries = []
        material_entries = []
        for line in lines:
            line = line.strip()
            if line.startswith("- Code:"):
                # Parse: "- Code: CONC1A | Desc: Plain concrete | Unit: m3 | Currency: USD | Net: 155.93 | Grand Total: 155.93 (Source: Library)"
                parts = {}
                for segment in line[2:].split(" | "):
                    if ": " in segment:
                        key, val = segment.split(": ", 1)
                        # Strip source suffix like "(Source: Library)"
                        if "(" in val:
                            val = val[:val.rfind("(")].strip()
                        parts[key.strip()] = val.strip()
                if parts:
                    rate_entries.append(parts)
            elif line.startswith("- Material:"):
                parts = {}
                for segment in line[2:].split(" | "):
                    if ": " in segment:
                        key, val = segment.split(": ", 1)
                        if "(" in val:
                            val = val[:val.rfind("(")].strip()
                        parts[key.strip()] = val.strip()
                if parts:
                    material_entries.append(parts)
        
        if rate_entries:
            response_parts.append("### Historical & Library Rates\n")
            response_parts.append("| Rate Code | Description | Unit | Currency | Net Rate | Grand Total |")
            response_parts.append("| --- | --- | --- | --- | --- | --- |")
            for r in rate_entries:
                response_parts.append(
                    f"| {r.get('Code', '-')} | {r.get('Desc', '-')} | {r.get('Unit', '-')} "
                    f"| {r.get('Currency', '-')} | {r.get('Net', '-')} | {r.get('Grand Total', '-')} |"
                )
        
        if material_entries:
            response_parts.append("\n### Matching Materials\n")
            response_parts.append("| Material | Unit | Price | Currency |")
            response_parts.append("| --- | --- | --- | --- |")
            for m in material_entries:
                response_parts.append(
                    f"| {m.get('Material', '-')} | {m.get('Unit', '-')} "
                    f"| {m.get('Price', '-')} | {m.get('Currency', '-')} |"
                )
        
        if response_parts:
            return "\n".join(response_parts)
        
        # If we couldn't parse structured data, return a generic message
        return "I found matching data in your project libraries. Please try asking a more specific question to see detailed results."

    def _generate_schema_context(self, available_files):
        """
        Queries all available database files dynamically to generate a compact schema context
        (databases, their tables, and columns) to inject into the system prompt.
        """
        schema_info = []
        for f in available_files:
            if not f.endswith('.db'):
                continue
            resolved = self._resolve_file_path(f)
            if not resolved:
                continue
            try:
                conn = sqlite3.connect(resolved)
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = [row[0] for row in cursor.fetchall() if not row[0].startswith('sqlite_')]
                
                table_schemas = []
                for table in tables:
                    cursor.execute(f"PRAGMA table_info(\"{table}\");")
                    cols = [row[1] for row in cursor.fetchall()]
                    table_schemas.append(f"{table} ({', '.join(cols)})")
                conn.close()
                
                if table_schemas:
                    schema_info.append(f"Database '{f}' contains tables:\n  - " + "\n  - ".join(table_schemas))
            except Exception:
                pass
        return "\n".join(schema_info)

    def _call_local_ollama(self, active_summary, workspace_files, outliers_data):
        """
        Queries the local Ollama instance dynamically using the configured local LLM model,
        supporting recursive execution of SQLite queries and JSON file reading.
        """
        # A. Auto-detect and verify specific model via tags API
        model_name = "lfm2:24b"
        try:
            from database import DatabaseManager
            costs_db = DatabaseManager("construction_costs.db")
            model_name = costs_db.get_setting("ai_model_name", "lfm2:24b")
        except Exception:
            pass

        try:
            req = urllib.request.Request("http://localhost:11434/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=2) as response:
                tags_data = json.loads(response.read().decode("utf-8"))
                models = tags_data.get("models", [])
                installed_names = [m.get("name", "").lower() for m in models]
                if not any(model_name.lower() in name or name.startswith(model_name.lower()) for name in installed_names):
                    raise Exception(f"Required model '{model_name}' is not installed in Ollama.")
        except urllib.error.URLError:
            raise Exception("Ollama is not running locally.")
        except Exception as e:
            # Trigger fallback to the offline rule interpreter
            raise Exception(str(e))

        # Scan for db and json files to list in system prompt dynamically (using workspace/project relative paths)
        available_files = []
        for root, dirs, files in os.walk(APP_DIR):
            dirs[:] = [d for d in dirs if d not in {'.git', '.idea', '__pycache__', '.pytest_cache', '.vscode', 'PyTest'}]
            for f in files:
                if f.endswith('.db') or f.endswith('.json'):
                    rel = os.path.relpath(os.path.join(root, f), APP_DIR).replace('\\', '/')
                    available_files.append(rel)
        try:
            from database import DatabaseManager
            costs_db = DatabaseManager("construction_costs.db")
            project_dir = costs_db.get_setting('last_project_dir', '')
            if project_dir and os.path.exists(project_dir):
                for root, dirs, files in os.walk(project_dir):
                    for f in files:
                        if f.endswith('.db') or f.endswith('.json'):
                            rel = os.path.relpath(os.path.join(root, f), project_dir).replace('\\', '/')
                            proj_base = os.path.basename(project_dir)
                            path_in_project = f"{proj_base}/{rel}".replace('\\', '/')
                            if path_in_project not in available_files:
                                available_files.append(path_in_project)
        except Exception:
            pass

        # Generate database schemas to give model precise, real-time knowledge of all tables and columns
        schema_context = self._generate_schema_context(available_files)

        # Build active project context description dynamically
        active_context = ""
        if active_summary and "status" not in active_summary:
            lines = ["--- ACTIVE LOADED PROJECT ---"]
            for key, val in active_summary.items():
                if key in ["source", "pboq_database_path", "project_directory"]:
                    continue
                
                title = key.replace('_', ' ').replace('boq', 'BOQ').title()
                
                if isinstance(val, float) and "percent" not in key:
                    currency_prefix = active_summary.get('currency', 'GHS').split(' ')[0]
                    lines.append(f"{title}: {currency_prefix} {val:,.2f}")
                elif isinstance(val, float):
                    lines.append(f"{title}: {val:.2f}%")
                else:
                    lines.append(f"{title}: {val}")
            
            lines.append("-----------------------------\n\n")
            active_context = "\n".join(lines)

        # Proactive context generation for local LLM helper
        extra_context = ""
        query_lower = self.user_query.lower()
        
        # 1. PBOQ Price Outliers & Anomalies Context
        if outliers_data:
            devs = outliers_data.get("outlier_deviations", [])
            plugs = outliers_data.get("manual_plug_rates", [])
            if devs or plugs:
                extra_context += "--- ACTIVE PROJECT PRICE OUTLIERS & ANOMALIES ---\n"
                if devs:
                    extra_context += "Deviations of ±15% from library baseline:\n"
                    for d in devs[:10]:
                        extra_context += f"  - {d['type']} '{d['item']}' in task '{d['task']}': Current rate {d['current_rate']} vs Library rate {d['library_rate']} (Dev: {d['deviation']})\n"
                if plugs:
                    extra_context += "Manual Plug Rates:\n"
                    for p in plugs[:10]:
                        extra_context += f"  - Row {p['row_id']}: '{p['description']}' plugged at {p['plug_rate']} (Flagged: {p['is_flagged_for_review']})\n"
                extra_context += "------------------------------------------------\n\n"

        # 2. Rate buildup recipe coupling context
        found_codes = []
        for word in re.split(r'[^a-zA-Z0-9\-]', self.user_query):
            if len(word) >= 4 and not word.isdigit():
                found_codes.append(word.upper())
                
        if found_codes:
            try:
                graph_data = ai_tools.build_unified_knowledge_graph()
                recipe_coupling = graph_data.get("recipe_coupling", {})
                for code in found_codes:
                    recipe = None
                    for name, r in recipe_coupling.items():
                        if str(r.get("rate_code", "")).upper() == code:
                            recipe = r
                            break
                    if not recipe:
                        # Scan all project estimate databases to find the composite buildup
                        fallback_dbs = []
                        db_path = ai_tools.get_active_project_db_path()
                        if db_path and os.path.exists(db_path):
                            fallback_dbs.append(db_path)
                            
                        # Also check Imported Library
                        try:
                            costs_db = sqlite3.connect(os.path.join(APP_DIR, "construction_costs.db"))
                            cursor = costs_db.cursor()
                            cursor.execute("SELECT value FROM settings WHERE key='last_project_dir'")
                            row = cursor.fetchone()
                            if row and row[0]:
                                pdir = row[0].replace('\\', '/')
                                # Resolve clean path
                                for sub in ["Imported Library", "Project Database", "Priced BOQs", "SOR", "PBOQ States", "Received RFQs"]:
                                    if pdir.endswith("/" + sub):
                                        pdir = pdir[:-len(sub)-1]
                                    elif "/" + sub + "/" in pdir:
                                        pdir = pdir.split("/" + sub)[0]
                                        
                                imp_dir = os.path.join(pdir, "Imported Library")
                                if os.path.exists(imp_dir):
                                    for f in os.listdir(imp_dir):
                                        if f.endswith('.db'):
                                            fallback_dbs.append(os.path.join(imp_dir, f))
                            costs_db.close()
                        except Exception:
                            pass
                            
                        # Also check construction_costs.db
                        costs_db_path = os.path.join(APP_DIR, "construction_costs.db")
                        if os.path.exists(costs_db_path):
                            fallback_dbs.append(costs_db_path)
                            
                        for fdb in fallback_dbs:
                            try:
                                conn = sqlite3.connect(fdb)
                                cursor = conn.cursor()
                                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='estimates'")
                                if not cursor.fetchone():
                                    conn.close()
                                    continue
                                    
                                cursor.execute("SELECT id, project_name, net_total, grand_total, category FROM estimates WHERE UPPER(rate_code) = ?", (code,))
                                res = cursor.fetchone()
                                if res:
                                    est_id, name, net, grand, cat = res
                                    candidate = {
                                        "rate_code": code,
                                        "description": name,
                                        "net_total": net,
                                        "grand_total": grand,
                                        "category": cat,
                                        "materials": [], "labor": [], "plant": [], "equipment": [], "indirect_costs": []
                                    }
                                    
                                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='estimate_materials'")
                                    if cursor.fetchone():
                                        cursor.execute("SELECT name, quantity, unit, price, currency FROM estimate_materials WHERE task_id IN (SELECT id FROM tasks WHERE estimate_id = ?)", (est_id,))
                                        candidate["materials"] = [{"name": r[0], "quantity": r[1], "unit": r[2], "price": r[3], "currency": r[4]} for r in cursor.fetchall()]
                                        
                                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='estimate_labor'")
                                    if cursor.fetchone():
                                        cursor.execute("SELECT name_trade, hours, unit, rate, currency FROM estimate_labor WHERE task_id IN (SELECT id FROM tasks WHERE estimate_id = ?)", (est_id,))
                                        candidate["labor"] = [{"trade": r[0], "hours": r[1], "unit": r[2], "rate": r[3], "currency": r[4]} for r in cursor.fetchall()]
                                        
                                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='estimate_plant'")
                                    if cursor.fetchone():
                                        cursor.execute("SELECT name_trade, hours, unit, rate, currency FROM estimate_plant WHERE task_id IN (SELECT id FROM tasks WHERE estimate_id = ?)", (est_id,))
                                        candidate["plant"] = [{"name": r[0], "hours": r[1], "unit": r[2], "rate": r[3], "currency": r[4]} for r in cursor.fetchall()]
                                        
                                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='estimate_equipment'")
                                    if cursor.fetchone():
                                        cursor.execute("SELECT name_trade, hours, unit, rate, currency FROM estimate_equipment WHERE task_id IN (SELECT id FROM tasks WHERE estimate_id = ?)", (est_id,))
                                        candidate["equipment"] = [{"name": r[0], "hours": r[1], "unit": r[2], "rate": r[3], "currency": r[4]} for r in cursor.fetchall()]
                                        
                                    conn.close()
                                    
                                    # If this estimate is detailed, choose it and stop searching
                                    if len(candidate["materials"]) + len(candidate["labor"]) > 1 or not recipe:
                                        recipe = candidate
                                        if len(candidate["materials"]) + len(candidate["labor"]) > 1:
                                            break
                                else:
                                    conn.close()
                            except Exception:
                                pass

                    if recipe:
                        def safe_format(val):
                            if val is None:
                                return "0.00"
                            try:
                                return f"{float(val):.2f}"
                            except (ValueError, TypeError):
                                return str(val)

                        extra_context += f"--- COMPOSITE RATE BUILDUP RECIPE FOR '{code}' ---\n"
                        extra_context += f"Description: {recipe.get('description')}\n"
                        extra_context += f"Net Rate Cost: {safe_format(recipe.get('net_total'))}\n"
                        extra_context += f"Adjusted Gross Rate: {safe_format(recipe.get('grand_total'))}\n"
                        if recipe.get("materials"):
                            extra_context += "Underlying Materials:\n"
                            for m in recipe["materials"]:
                                extra_context += f"  - Material: {m['name']} | Qty: {safe_format(m['quantity'])} | Price: {safe_format(m['price'])} {m.get('currency', 'USD')}\n"
                        if recipe.get("labor"):
                            extra_context += "Underlying Labor:\n"
                            for l in recipe["labor"]:
                                extra_context += f"  - Labor: {l['trade']} | Hours: {safe_format(l['hours'])} hr @ {safe_format(l['rate'])} {l.get('currency', 'USD')}\n"
                        if recipe.get("plant"):
                            extra_context += "Underlying Plant:\n"
                            for p in recipe["plant"]:
                                extra_context += f"  - Plant: {p['name']} | Hours: {safe_format(p['hours'])} hr @ {safe_format(p['rate'])} {p.get('currency', 'USD')}\n"
                        if recipe.get("equipment"):
                            extra_context += "Underlying Equipment:\n"
                            for eq in recipe["equipment"]:
                                extra_context += f"  - Equipment: {eq['name']} | Hours: {safe_format(eq['hours'])} hr @ {safe_format(eq['rate'])} {eq.get('currency', 'USD')}\n"
                        extra_context += "--------------------------------------------------\n\n"
            except Exception:
                pass

        # 3. WBS & Under-Measurement QS Warnings Context
        if any(k in query_lower for k in ["wbs", "hierarchy", "section", "under-measurement", "dependency", "slab", "concrete"]):
            try:
                graph_data = ai_tools.build_unified_knowledge_graph()
                wbs = graph_data.get("wbs_hierarchy", {})
                warnings = graph_data.get("resource_dependencies_warnings", [])
                
                if wbs and any(k in query_lower for k in ["wbs", "hierarchy", "section"]):
                    extra_context += "--- ACTIVE PROJECT WBS HIERARCHY SUMMARY ---\n"
                    for sheet, sections in wbs.items():
                        extra_context += f"Sheet: '{sheet}':\n"
                        for sec, items in sections.items():
                            extra_context += f"  Section: '{sec}':\n"
                            for it in items[:6]:
                                extra_context += f"    - Item: {it['description']} | Code: {it['rate_code']} | Amt: {it['bill_amount']}\n"
                    extra_context += "--------------------------------------------\n\n"
                    
                if warnings and any(k in query_lower for k in ["under-measurement", "dependency", "slab", "concrete"]):
                    extra_context += "--- ACTIVE PROJECT QS DEPENDENCY WARNINGS ---\n"
                    for w in warnings:
                        extra_context += f"  - WARNING in sheet '{w['sheet']}' section '{w['wbs_section']}': '{w['item']}' (Code: {w['rate_code']}) -> {w['issue']} (Severity: {w['severity']})\n"
                    extra_context += "---------------------------------------------\n\n"
            except Exception:
                pass

        # 4. Ingest / SOR Domains Context
        if any(k in query_lower for k in ["sor", "schedule of rates", "ingest", "settings", "exchange"]):
            try:
                domains_data = ai_tools.ingest_project_domains()
                settings = domains_data.get("project_settings", {})
                pboq = domains_data.get("pboq_summary", {})
                analytics = domains_data.get("analytics_summary", {})
                
                extra_context += "--- INGESTED PROJECT DOMAINS METADATA ---\n"
                if settings:
                    extra_context += f"Project settings: Overhead: {settings.get('overhead_percent')}%, Profit: {settings.get('profit_margin_percent')}%, Currency: {settings.get('base_currency')}\n"
                if pboq:
                    extra_context += f"PBOQ summary: Total items: {pboq.get('total_items_count')}, Priced: {pboq.get('priced_items_count')}, Total Value: {pboq.get('total_priced_value')}\n"
                if analytics:
                    extra_context += f"Analytics: Net Subtotal: {analytics.get('net_subtotal')}, Grand Total: {analytics.get('grand_total')}\n"
                extra_context += "-----------------------------------------\n\n"
            except Exception:
                pass

        # 5. Priced BOQ Items Context
        if any(k in query_lower for k in ["list", "show", "priced", "boq", "item"]):
            try:
                priced_items = ai_tools.get_active_project_priced_items(project_dir)
                if priced_items:
                    extra_context += "--- ACTIVE PROJECT PRICED BOQ ITEMS ---\n"
                    extra_context += "| Sheet | Description | Quantity | Unit | Net Rate | Net Amount |\n"
                    extra_context += "| --- | --- | --- | --- | --- | --- |\n"
                    for item in priced_items:
                        qty = item.get('qty', 0.0)
                        try:
                            rate = float(item.get('net_rate', 0.0))
                            rate_str = f"{rate:.2f}"
                        except:
                            rate_str = str(item.get('net_rate', 0.0))
                        try:
                            amt = float(item.get('net_amount', 0.0))
                            amt_str = f"{amt:.2f}"
                        except:
                            amt_str = str(item.get('net_amount', 0.0))
                        extra_context += f"| {item['sheet']} | {item['description']} | {qty} | {item['unit']} | {rate_str} | {amt_str} |\n"
                    extra_context += "---------------------------------------\n\n"
            except Exception:
                pass

        # 6. Proactive Database & Historical Rate Search Context
        search_terms = []
        stop_words = {"show", "search", "find", "query", "historical", "rates", "rate", "for", "the", "a", "an", "is", "in", "active", "project", "database", "library", "libraries", "costs", "cost"}
        for word in re.split(r'[^a-zA-Z0-9\-]', query_lower):
            if len(word) >= 3 and word not in stop_words and not word.isdigit():
                search_terms.append(word)
                
        if search_terms:
            try:
                search_query = " ".join(search_terms[:2])
                hist_rates = ai_tools.query_historical_rates(search_query)
                db_results = ai_tools.search_active_database(search_query)
                
                if hist_rates or any(db_results.values()):
                    extra_context += f"--- REAL-TIME SEARCH RESULTS FOR '{search_query}' ---\n"
                    if hist_rates:
                        extra_context += "Matching Historical/Library Estimates & Rates:\n"
                        for r in hist_rates[:15]:
                            extra_context += f"  - Code: {r.get('rate_code')} | Desc: {r.get('project_name')} | Unit: {r.get('unit')} | Currency: {r.get('currency')} | Net: {r.get('net_total')} | Grand Total: {r.get('grand_total')} (Source: {r.get('_source_db', 'Library')})\n"
                    
                    for category, items in db_results.items():
                        if items:
                            extra_context += f"Matching {category.title()} in active databases:\n"
                            for item in items[:10]:
                                if category == "materials":
                                    extra_context += f"  - Material: {item['name']} | Price: {item['price']} {item['currency']} | Unit: {item['unit']} (Source: {item['source']})\n"
                                elif category == "labor":
                                    extra_context += f"  - Labor Trade: {item['trade']} | Rate: {item['rate']} {item['currency']} | Unit: {item['unit']} (Source: {item['source']})\n"
                                elif category == "equipment":
                                    extra_context += f"  - Equipment: {item['name']} | Rate: {item['rate']} {item['currency']} | Unit: {item['unit']} (Source: {item['source']})\n"
                                elif category == "plant":
                                    extra_context += f"  - Plant: {item['name']} | Rate: {item['rate']} {item['currency']} | Unit: {item['unit']} (Source: {item['source']})\n"
                                elif category == "tasks":
                                    extra_context += f"  - Task: {item['description']} | Qty: {item['quantity']} {item['unit']} (Source: {item['source']})\n"
                                elif category == "pboq_items":
                                    extra_context += f"  - Priced BOQ: {item['description']} | Bill Rate: {item['bill_rate']} | Plug: {item['plug_rate']} | Unit: {item['unit']} (Source: {item['source']})\n"
                    extra_context += "-----------------------------------------------------\n\n"
                    
                    # PROACTIVE CONTEXT SIGNAL: Instruct the LLM to use pre-fetched data directly
                    if hist_rates or any(db_results.values()):
                        extra_context += (
                            "[SYSTEM DIRECTIVE: The REAL-TIME SEARCH RESULTS above already contain the data matching the user's query. "
                            "You MUST present this data directly in a clean, professional markdown table as your answer. "
                            "Do NOT issue any additional <query_db> calls or write any SQL. "
                            "Format the results with columns: Rate Code, Description, Unit, Currency, Net Rate, Grand Total. "
                            "If materials/labor/equipment matches are also present, include them in a separate table below.]\n\n"
                        )
            except Exception:
                pass

        system_prompt = (
            "================================================================================\n"
            "ROLE & IDENTITY DECLARATION:\n"
            "You are the \"AI Estimating Copilot for Estimator Pro,\" a world-class professional Quantity Surveyor and Construction Estimating Expert.\n"
            "You operate strictly within the domain of construction estimating, costing, bills of quantities (BOQ), materials, labor, plant/equipment rates, and project markups.\n\n"
            "=== ACTIVE PROJECT REAL-TIME QS DATA ===\n"
            f"{extra_context}"
            "========================================\n\n"
            "=== MANDATORY DATA USAGE RULE (HIGHEST PRIORITY) ===\n"
            "If the 'REAL-TIME SEARCH RESULTS', 'ACTIVE PROJECT PRICED BOQ ITEMS', 'COMPOSITE RATE BUILDUP RECIPE', or 'ACTIVE PROJECT PRICE OUTLIERS' sections above contain data that answers or is relevant to the user's question, "
            "you MUST use that pre-fetched data directly in your response. Do NOT issue additional <query_db> calls, do NOT write SQL, and do NOT hallucinate or invent prices. "
            "Present the pre-fetched data in a clean, professional markdown table with appropriate columns (e.g., Rate Code | Description | Unit | Currency | Net Rate | Grand Total). "
            "If no pre-fetched data is present for the user's query, THEN and ONLY THEN should you use <query_db> to fetch data.\n"
            "========================================\n\n"
            "=== CRITICAL CONSTRAINTS: YOU ARE NOT A CODING ASSISTANT ===\n"
            "- **YOU ARE NOT A CODING OR DATABASE TUTOR**: You must NEVER teach programming, NEVER write SQL debugging guides, and NEVER explain SQLite errors or database design concepts to the user. If they ask a question, answer it in terms of construction rates and estimating.\n"
            "- **HIDE THE TECHNICAL UNDERPINNINGS**: The user is a professional estimator/builder, not a software engineer. They must NEVER see database terms, table names (e.g., 'pboq_items'), SQL queries, or column lists in your response. Always present data in clean, standard, domain-friendly terms (e.g., 'priced BOQ sheet', 'materials library', 'unit rate', 'subtotal').\n"
            "- **NEVER WRITE SQL CODE BLOCKS**: Do NOT write standard markdown SQL code blocks (e.g. ```sql ... ```) inside your user-facing responses. If you need to query database tables, use the <query_db> tag privately.\n"
            "- **NO TECH JARGON**: If a database query fails or returns no rows, NEVER discuss the SQL error or schema mismatch. Simply say, in professional estimating terms, that the requested resource or setting was not found or has not been configured in the loaded project.\n"
            "- **SELF-CORRECTION ON ERROR**: If a <query_result> returns an SQL error with column hints (e.g., 'table X has columns: a, b, c'), you MUST silently retry with the correct column names. NEVER show or describe the error to the user under any circumstances.\n"
            "================================================================================\n\n"
            "=== CRITICAL DIRECT ANSWER GUIDELINE ===\n"
            "If the user asks a simple or direct question about the loaded project (such as the project currency, project name, client name, total BOQ items, priced items, grand total bid value, overhead markup, profit margin, or other metadata) that is already present in the '--- ACTIVE LOADED PROJECT ---' block below, you MUST answer the question directly and concisely in a single sentence (e.g., 'The base currency of the project is USD ($).') based on that block. Do NOT write any SQLite database queries, do NOT write SQL code blocks, do NOT use any <query_db> tags, and do NOT print any tables, columns, schema metadata, observations, or key observations.\n"
            "========================================\n\n"
            f"{active_context}"
            "Here is the database schema context of the project:\n"
            f"{schema_context}\n\n"
            "CRITICAL SQLite METADATA INSTRUCTIONS:\n"
            "- Since the database is SQLite, you CANNOT use 'INFORMATION_SCHEMA' or 'DESCRIBE'.\n"
            "- To get column names and types in SQLite, run: PRAGMA table_info(tableName);\n"
            "- To list tables, run: SELECT name FROM sqlite_master WHERE type='table';\n\n"
            "INSTRUCTIONS FOR DB QUERYING & FILE ACCESS:\n"
            "- To query an SQLite database, write exactly:\n"
            "<query_db db=\"DATABASENAME\">SQL_QUERY</query_db>\n"
            "For example: <query_db db=\"construction_costs.db\">SELECT * FROM materials LIMIT 5;</query_db>\n\n"
            "- To read a JSON file, write exactly:\n"
            "<read_json file=\"FILENAME\"></read_json>\n"
            "For example: <read_json file=\"settings.json\"></read_json>\n\n"
            "- To fetch the Unified Project Knowledge Graph (which groups priced items by WBS, maps recipes/buildup chains, and detects concrete slab under-measurement warnings), write exactly:\n"
            "<get_knowledge_graph />\n\n"
            "- To ingest all project settings, resources summary lists, Schedule of Rates (SOR) items, priced BOQs metadata, and dynamic margin/outlier analytics, write exactly:\n"
            "<ingest_project_domains />\n\n"
            "If you output a tag, STOP generating immediately. The system will execute the query/read/graph ingestion, append the results, and invoke you again to formulate your final response.\n"
            "Use these tools immediately to fetch actual database results or structural knowledge graph details if the user asks any question about library prices, estimate details, WBS sections, rate recipes, under-measurement warnings, database tables, or files. Do not suggest or write placeholders; run the query or tool to find the actual real-time answers.\n\n"
            "=== ADDITIONAL CRITICAL CONSTRAINTS ===\n"
            "- NEVER print, summarize, copy, list, or describe the database schema, table structures, or column listings in your final response unless the user explicitly asked you to show database schema/structure.\n"
            "- Simple questions must be answered with a simple, direct, friendly sentence. Keep the database technical details completely invisible to the user by default.\n"
            "- Focus only on extracting the requested information and answering the user directly.\n"
            "- You MUST always produce a substantive, non-empty response. Never return only whitespace or thinking tags."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": self.user_query}
        ]

        url = "http://localhost:11434/v1/chat/completions"
        headers = {"Content-Type": "application/json"}

        for iteration in range(5):
            data = {
                "model": model_name,
                "messages": messages,
                "temperature": 0.2,
                "stream": False
            }

            req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=60) as response:
                    res_data = json.loads(response.read().decode("utf-8"))
                    content = res_data["choices"][0]["message"]["content"]
            except Exception as e:
                raise Exception(f"Local LLM API error: {str(e)}")

            # Check for <query_db>, <read_json>, <get_knowledge_graph>, or <ingest_project_domains> tags
            db_match = re.search(r'<query[-_]?db\s+db=["\']?([^"\'\s>]+)["\']?>(.*?)(?:</query[-_]?db>|$)', content, re.DOTALL | re.IGNORECASE)
            json_match = re.search(r'<read[-_]?json\s+file=["\']?([^"\'\s>]+)["\']?>(.*?)(?:</read[-_]?json>|$)', content, re.DOTALL | re.IGNORECASE)
            if not json_match:
                json_match = re.search(r'<read[-_]?json\s+file=["\']?([^"\'\s>]+)["\']?\s*/?>', content, re.IGNORECASE)
                
            graph_match = re.search(r'<get_knowledge_graph\s*/?>', content, re.IGNORECASE)
            if not graph_match:
                graph_match = re.search(r'<get_knowledge_graph\s*>(.*?)(?:</get_knowledge_graph>|$)', content, re.DOTALL | re.IGNORECASE)
                
            domains_match = re.search(r'<ingest_project_domains\s*/?>', content, re.IGNORECASE)
            if not domains_match:
                domains_match = re.search(r'<ingest_project_domains\s*>(.*?)(?:</ingest_project_domains>|$)', content, re.DOTALL | re.IGNORECASE)

            # Heuristic: If no explicit tag matches, but the model output contains a SQL code block, treat it as an implicit database query!
            if not db_match and not json_match and not graph_match and not domains_match:
                sql_block_match = re.search(r'```(?:sql|sqlite)\n(.*?)\n```', content, re.DOTALL | re.IGNORECASE)
                if sql_block_match:
                    sql_query = sql_block_match.group(1).strip()
                    
                    # Detect database name from content or user query
                    detected_db = None
                    # 1. Direct match
                    for f in available_files:
                        if f.endswith('.db') and f.lower() in content.lower():
                            detected_db = f
                            break
                    # 2. Prioritize Project Database if name collides
                    if not detected_db:
                        project_dbs = [f for f in available_files if f.endswith('.db') and "project database" in f.lower() and os.path.basename(f).lower() in content.lower()]
                        if project_dbs:
                            detected_db = project_dbs[0]
                    # 3. Suffix match
                    if not detected_db:
                        for f in available_files:
                            basename = os.path.basename(f)
                            if basename.lower() in content.lower() or basename.lower() in self.user_query.lower():
                                detected_db = f
                                break
                    # 4. Fallbacks
                    if not detected_db:
                        pboq_path = active_summary.get('pboq_database_path')
                        if pboq_path:
                            detected_db = os.path.basename(pboq_path)
                        else:
                            detected_db = "construction_costs.db"
                            
                    db_name = detected_db
                    
                    # Append assistant's partial message requesting the tool
                    messages.append({"role": "assistant", "content": content})
                    
                    # Execute tool
                    result = self._execute_sql(db_name, sql_query)
                    
                    # Append system tool result
                    messages.append({
                        "role": "user",
                        "content": f"[System Tool Result - Automatically executed SQL query on '{db_name}']:\n<query_result>\n{result}\n</query_result>"
                    })
                    continue

            if graph_match:
                # Append assistant's partial message requesting the tool
                messages.append({"role": "assistant", "content": content})
                
                # Execute tool
                try:
                    graph_data = ai_tools.build_unified_knowledge_graph()
                    result = json.dumps(graph_data, indent=2)
                except Exception as e:
                    result = f"Error building knowledge graph: {str(e)}"
                
                # Append system tool result
                messages.append({
                    "role": "user",
                    "content": f"[System Tool Result]:\n<get_knowledge_graph_result>\n{result}\n</get_knowledge_graph_result>"
                })
                continue
                
            elif domains_match:
                # Append assistant's partial message requesting the tool
                messages.append({"role": "assistant", "content": content})
                
                # Execute tool
                try:
                    domains_data = ai_tools.ingest_project_domains()
                    result = json.dumps(domains_data, indent=2)
                except Exception as e:
                    result = f"Error ingesting project domains: {str(e)}"
                
                # Append system tool result
                messages.append({
                    "role": "user",
                    "content": f"[System Tool Result]:\n<ingest_project_domains_result>\n{result}\n</ingest_project_domains_result>"
                })
                continue

            elif db_match:
                db_name = db_match.group(1).strip()
                sql_query = db_match.group(2).strip()
                
                # Append assistant's partial message requesting the tool
                messages.append({"role": "assistant", "content": content})
                
                # Execute tool
                result = self._execute_sql(db_name, sql_query)
                
                # Append system tool result
                messages.append({
                    "role": "user",
                    "content": f"[System Tool Result]:\n<query_result>\n{result}\n</query_result>"
                })
                continue
                
            elif json_match:
                file_name = json_match.group(1).strip()
                
                # Append assistant's partial message requesting the tool
                messages.append({"role": "assistant", "content": content})
                
                # Execute tool
                result = self._read_json(file_name)
                
                # Append system tool result
                messages.append({
                    "role": "user",
                    "content": f"[System Tool Result]:\n<read_json_result>\n{result}\n</read_json_result>"
                })
                continue
                
            else:
                # No more tools called, parse and return final content
                think_match = re.search(r'<think>(.*?)</think>', content, re.DOTALL)
                if think_match:
                    thinking = think_match.group(1).strip()
                    actual_content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
                    
                    # EMPTY RESPONSE GUARD: If the LLM produced only <think> tags with no actual answer,
                    # generate a meaningful fallback instead of returning a blank bubble.
                    if not actual_content:
                        # Try to produce a useful response from the pre-fetched context
                        if extra_context and "REAL-TIME SEARCH RESULTS" in extra_context:
                            return (
                                "I found the following results from your project libraries:\n\n"
                                + self._format_proactive_context_as_response(extra_context)
                            )
                        return "I processed your query but couldn't formulate a complete answer. Please try rephrasing your question, or ask something more specific about the active project."
                    
                    return f"> [!THINK]\n> {thinking}\n\n{actual_content}"
                
                # EMPTY RESPONSE GUARD: Handle completely empty LLM output
                if not content or not content.strip():
                    if extra_context and "REAL-TIME SEARCH RESULTS" in extra_context:
                        return (
                            "I found the following results from your project libraries:\n\n"
                            + self._format_proactive_context_as_response(extra_context)
                        )
                    return "I processed your query but couldn't formulate a complete answer. Please try rephrasing your question, or ask something more specific about the active project."
                
                return content

        # If it reaches the iteration limit, return the last generated content
        if not content or not content.strip():
            if extra_context and "REAL-TIME SEARCH RESULTS" in extra_context:
                return (
                    "I found the following results from your project libraries:\n\n"
                    + self._format_proactive_context_as_response(extra_context)
                )
            return "I processed your query but couldn't formulate a complete answer. Please try rephrasing your question, or ask something more specific about the active project."
        return content
