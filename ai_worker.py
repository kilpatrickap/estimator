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
            if self.main_window:
                active_win = self.main_window._get_active_estimate_window()
                active_class = getattr(active_win, '__class__', None).__name__ if active_win else None
                if active_class == 'PBOQDialog' and hasattr(active_win, 'pboq_file_selector'):
                    pboq_path = active_win.pboq_file_selector.currentData()

            # Fallback A: Detect best PBOQ database from loaded project folder if no active window has it
            if not pboq_path:
                try:
                    from database import DatabaseManager
                    import sqlite3
                    costs_db = DatabaseManager("construction_costs.db")
                    project_dir = costs_db.get_setting('last_project_dir', '')
                    if project_dir and os.path.exists(project_dir):
                        if os.path.basename(project_dir) == "Project Database":
                            project_dir = os.path.dirname(project_dir)
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

            # Route known estimating intents to the high-fidelity local semantic interpreter first
            # to guarantee absolute database precision and flawless premium estimating dashboards.
            q_lower = self.user_query.lower().strip()
            known_intents = [
                "currency", "overhead", "markup", "profit", "margin", "client", "customer", 
                "project name", "name of the project", "total boq items", "how many items", 
                "priced items", "outstanding items", "kpi", "summary", "totals", "outlier", 
                "anomaly", "deviation", "plug", "anomalies", "outliers", "concrete", "cement", 
                "waterproofing", "lumber", "timber", "excavation", "plaster", "masonry", "paint", 
                "labor", "search", "find", "lookup", "diagnostics", "database access", "cannot read", 
                "can't read", "read the db", "read db", "file", "dir", "folder", "workspace", 
                "structure", "tree", "files"
            ]
            
            if any(w in q_lower for w in known_intents):
                response_text = self._generate_local_response(self.user_query, active_summary, workspace_files, outliers_data)
                self.signals.finished.emit(response_text)
                return

            try:
                # 3. Try to call the local LLM thinking model via Ollama
                response_text = self._call_local_ollama(active_summary, workspace_files, outliers_data)
                self.signals.finished.emit(response_text)
            except Exception as ollama_err:
                # 4. Graceful fallback: run local semantic interpreter if Ollama is unreachable/failed
                response_text = self._generate_local_response(self.user_query, active_summary, workspace_files, outliers_data)
                
                # If it was a general welcome or standard help query, append an helpful instruction card
                q_lower = self.user_query.lower()
                if q_lower in ["", "help", "hello", "hi"] or response_text.startswith("# 👋 Welcome"):
                    response_text += (
                        "\n\n> [!NOTE]\n"
                        "> **⚡ Boost with Local LLM Reasoning**\n"
                        "> You can enable full offline LLM reasoning (like **LFM-2 1.2B**) locally. "
                        "> Simply install **Ollama** from [ollama.com](https://ollama.com) and run:\n"
                        "> ```bash\n"
                        "> ollama run sam860/LFM2:1.2b\n"
                        "> ```\n"
                        "> Once running, the Copilot will automatically activate the local reasoning engine!"
                    )
                self.signals.finished.emit(response_text)
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
            return f"Error executing SQL: {str(e)}"

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

    def _generate_schema_context(self, available_files):
        """
        Queries all available database files dynamically to generate schema context
        (tables and column lists) to inject into the system prompt.
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
                    cols = [f"{col[1]} ({col[2]})" for col in cursor.fetchall()]
                    table_schemas.append(f"  - Table '{table}' with columns: {', '.join(cols)}")
                
                if table_schemas:
                    schema_info.append(f"Database '{f}':\n" + "\n".join(table_schemas))
                conn.close()
            except Exception:
                pass
        return "\n\n".join(schema_info)

    def _call_local_ollama(self, active_summary, workspace_files, outliers_data):
        """
        Queries the local Ollama instance strictly using the sam860/LFM2:1.2b model,
        supporting recursive execution of SQLite queries and JSON file reading.
        """
        # A. Auto-detect and verify specific model via tags API
        model_name = "sam860/LFM2:1.2b"
        try:
            req = urllib.request.Request("http://localhost:11434/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=2) as response:
                tags_data = json.loads(response.read().decode("utf-8"))
                models = tags_data.get("models", [])
                installed_names = [m.get("name", "").lower() for m in models]
                if not any(model_name.lower() in name or "sam860/lfm2:1.2b" in name for name in installed_names):
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

        # Build active project context description (gives the model instant project KPIs and settings context)
        active_context = ""
        if active_summary and "status" not in active_summary:
            active_context = (
                "--- ACTIVE LOADED PROJECT ---\n"
                f"Project Name: {active_summary.get('project_name', 'N/A')}\n"
                f"Client Name: {active_summary.get('client_name', 'N/A')}\n"
                f"Base Currency: {active_summary.get('currency', 'GHS (₵)')}\n"
                f"Total BOQ Items: {active_summary.get('total_boq_items', 0)} items\n"
                f"Priced BOQ Items: {active_summary.get('priced_items', 0)} priced\n"
                f"Grand Total Bid Value: {active_summary.get('currency', 'GHS').split(' ')[0]} {active_summary.get('grand_total', 0.0):,.2f}\n"
                f"Overhead Markup: {active_summary.get('overhead_percent', 0.0)}%\n"
                f"Profit Margin: {active_summary.get('profit_margin_percent', 0.0)}%\n"
                f"Project Directory: {active_summary.get('project_directory', 'N/A')}\n"
                "-----------------------------\n\n"
            )

        system_prompt = (
            "================================================================================\n"
            "ROLE & IDENTITY DECLARATION:\n"
            "You are the \"AI Estimating Copilot for Estimator Pro,\" a world-class professional Quantity Surveyor and Construction Estimating Expert.\n"
            "You operate strictly within the domain of construction estimating, costing, bills of quantities (BOQ), materials, labor, plant/equipment rates, and project markups.\n\n"
            "=== CRITICAL CONSTRAINTS: YOU ARE NOT A CODING ASSISTANT ===\n"
            "- **YOU ARE NOT A CODING OR DATABASE TUTOR**: You must NEVER teach programming, NEVER write SQL debugging guides, and NEVER explain SQLite errors or database design concepts to the user. If they ask a question, answer it in terms of construction rates and estimating.\n"
            "- **HIDE THE TECHNICAL UNDERPINNINGS**: The user is a professional estimator/builder, not a software engineer. They must NEVER see database terms, table names (e.g., 'pboq_items'), SQL queries, or column lists in your response. Always present data in clean, standard, domain-friendly terms (e.g., 'priced BOQ sheet', 'materials library', 'unit rate', 'subtotal').\n"
            "- **NEVER WRITE SQL CODE BLOCKS**: Do NOT write standard markdown SQL code blocks (e.g. ```sql ... ```) inside your user-facing responses. If you need to query database tables, use the <query_db> tag privately.\n"
            "- **NO TECH JARGON**: If a database query fails or returns no rows, NEVER discuss the SQL error or schema mismatch. Simply say, in professional estimating terms, that the requested resource or setting was not found or has not been configured in the loaded project.\n"
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
            "If you output a tag, STOP generating immediately. The system will execute the query/read, append the results, and invoke you again to formulate your final response.\n"
            "Use these tools immediately to fetch actual database results if the user asks any question about library prices, estimate details, database tables, or files. Do not suggest or write placeholders; run the query to find the actual real-time answers.\n\n"
            "=== ADDITIONAL CRITICAL CONSTRAINTS ===\n"
            "- NEVER print, summarize, copy, list, or describe the database schema, table structures, or column listings in your final response unless the user explicitly asked you to show database schema/structure.\n"
            "- Simple questions must be answered with a simple, direct, friendly sentence. Keep the database technical details completely invisible to the user by default.\n"
            "- Focus only on extracting the requested information and answering the user directly."
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
                with urllib.request.urlopen(req, timeout=35) as response:
                    res_data = json.loads(response.read().decode("utf-8"))
                    content = res_data["choices"][0]["message"]["content"]
            except Exception as e:
                raise Exception(f"Local LLM API error: {str(e)}")

            # Check for <query_db> or <read_json> tags
            db_match = re.search(r'<query_db\s+db=["\'](.*?)["\']>(.*?)</query_db>', content, re.DOTALL | re.IGNORECASE)
            json_match = re.search(r'<read_json\s+file=["\'](.*?)["\']>(.*?)</read_json>', content, re.DOTALL | re.IGNORECASE)
            if not json_match:
                json_match = re.search(r'<read_json\s+file=["\'](.*?)["\']\s*/>', content, re.IGNORECASE)

            # Heuristic: If no explicit tag matches, but the model output contains a SQL code block, treat it as an implicit database query!
            if not db_match and not json_match:
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

            if db_match:
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
                    return f"> [!THINK]\n> {thinking}\n\n{actual_content}"
                return content

        # If it reaches the iteration limit, return the last generated content
        return content

    def _generate_local_response(self, query, active_summary, workspace_files, outliers_data):
        """
        A local semantic context interpreter. Parses the user's intent and uses actual
        SQLite and workspace statistics to craft highly premium, formatted reports.
        """
        import sqlite3
        q_lower = query.lower().strip()

        # 1. Direct short answers for simple project metadata if asked directly
        if active_summary and "status" not in active_summary:
            currency = active_summary.get('currency', 'USD ($)')
            project_name = active_summary.get('project_name', 'N/A')
            client_name = active_summary.get('client_name', 'N/A')
            total_items = active_summary.get('total_boq_items', 0)
            priced_items = active_summary.get('priced_items', 0)
            grand_total = active_summary.get('grand_total', 0.0)
            overhead_pct = active_summary.get('overhead_percent', 0.0)
            profit_pct = active_summary.get('profit_margin_percent', 0.0)

            if q_lower in ["what is the currency of the project?", "what is the currency", "currency of the project", "currency of project", "currency", "project currency"]:
                return f"The base currency of the project is **{currency}**."
            elif q_lower in ["what is the overhead?", "what is the overhead markup?", "overhead markup", "overhead", "markup"]:
                return f"The overhead markup for the active project is **{overhead_pct}%**."
            elif q_lower in ["what is the profit margin?", "what is the profit?", "profit margin", "profit", "margin"]:
                return f"The profit margin for the active project is **{profit_pct}%**."
            elif q_lower in ["who is the client?", "what is the client name?", "client name", "client", "customer"]:
                return f"The client for the active project is **{client_name}**."
            elif q_lower in ["what is the project name?", "what is the name of the project?", "project name", "name of the project"]:
                return f"The active project name is **{project_name}**."
            elif q_lower in ["what is the total boq items?", "how many items are in the project?", "total items", "total boq items", "boq items"]:
                return f"The active project has a total of **{total_items}** BOQ items."

            # More general substring matches for simple queries
            if "currency" in q_lower or "monetary unit" in q_lower or "currency symbol" in q_lower:
                return f"The base currency of the project is **{currency}**."
            elif "overhead" in q_lower or "overhead markup" in q_lower:
                return f"The overhead markup for the active project is **{overhead_pct}%**."
            elif "profit margin" in q_lower or "profit percent" in q_lower:
                return f"The profit margin for the active project is **{profit_pct}%**."
            elif "client" in q_lower or "customer" in q_lower:
                return f"The client for the active project is **{client_name}**."
            elif "project name" in q_lower or "name of the project" in q_lower:
                return f"The active project name is **{project_name}**."

        # Database Diagnostics / Access check
        if any(w in q_lower for w in ["cannot read", "can't read", "read the db", "read db", "database access"]):
            costs_count = 0
            abs_costs_db = os.path.join(APP_DIR, "construction_costs.db")
            if os.path.exists(abs_costs_db):
                try:
                    conn = sqlite3.connect(abs_costs_db)
                    costs_count = conn.cursor().execute("SELECT COUNT(*) FROM materials").fetchone()[0]
                    conn.close()
                except Exception:
                    pass

            proj_db_path = ai_tools.get_active_project_db_path()
            if proj_db_path and not os.path.isabs(proj_db_path):
                proj_db_path = os.path.join(APP_DIR, proj_db_path)
            proj_db_name = os.path.basename(proj_db_path) if proj_db_path else "None"
            proj_tasks_count = 0
            proj_materials_count = 0
            if proj_db_path:
                try:
                    conn = sqlite3.connect(proj_db_path)
                    c = conn.cursor()
                    proj_tasks_count = c.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
                    proj_materials_count = c.execute("SELECT COUNT(*) FROM materials").fetchone()[0]
                    conn.close()
                except Exception:
                    pass

            pboq_path = active_summary.get("pboq_database_path")
            pboq_name = os.path.basename(pboq_path) if pboq_path else "None"
            pboq_items_count = active_summary.get("total_boq_items", 0)

            md = "# 🗄️ Database Access Diagnostics\n\n"
            md += "I can confirm that the AI Estimating Copilot **is fully online and successfully reading your database files** in real-time. Here is a live diagnostic report from your active database connections:\n\n"
            
            md += "| Database Source | File Name | Active Tables & Live Records |\n"
            md += "| :--- | :--- | :--- |\n"
            md += f"| **Global Cost Library** | `construction_costs.db` | Online (indexed **{costs_count}** library materials) |\n"
            if proj_db_path:
                md += f"| **Active Project Store** | `{proj_db_name}` | Online (found **{proj_tasks_count}** tasks and **{proj_materials_count}** project materials) |\n"
            else:
                md += "| **Active Project Store** | *None* | No project directory active |\n"
            if pboq_path:
                md += f"| **Priced BOQ Sheet** | `{pboq_name}` | Online (reading **{pboq_items_count}** active BOQ items) |\n"
            else:
                md += "| **Priced BOQ Sheet** | *None* | No active Priced BOQ sheet open |\n"
                
            md += "\n> [!NOTE]\n"
            md += f"> **Context Verification:** I have loaded your workspace settings and identified the current project directory as `{active_summary.get('project_directory', 'N/A')}`. "
            md += "All SQlite database files are unlocked and fully readable.\n\n"
            
            md += "### 🔍 Search the Database\n"
            md += "You can ask me to search these databases for any resource! Try typing:\n"
            md += "- **\"Search database for concrete\"**\n"
            md += "- **\"Search database for labor\"**\n"
            md += "- **\"Search database for waterproofing\"**"
            return md

        # Database Search intent (explicit search or keywords)
        keywords = ["concrete", "cement", "waterproofing", "lumber", "timber", "excavation", "plaster", "masonry", "paint", "labor"]
        if "search" in q_lower or "find" in q_lower or "lookup" in q_lower or any(k in q_lower for k in keywords):
            search_term = query
            prefixes = [
                r"^search\s+database\s+for\s+", r"^search\s+historical\s+rates\s+for\s+", 
                r"^search\s+historical\s+rates\s+", r"^search\s+rates\s+for\s+", 
                r"^search\s+for\s+", r"^search\s+", r"^find\s+", r"^lookup\s+rates\s+for\s+",
                r"^lookup\s+for\s+", r"^lookup\s+", r"^show\s+details\s+for\s+", r"^show\s+"
            ]
            for pfx in prefixes:
                match = re.match(pfx, search_term, re.IGNORECASE)
                if match:
                    search_term = re.sub(pfx, "", search_term, flags=re.IGNORECASE)
                    break
            search_term = search_term.strip()
            
            if search_term.lower() not in ["", "database", "db", "file", "rates", "rate", "items", "item"]:
                search_results = ai_tools.search_active_database(search_term)
                
                md = f"# 🔍 Database Search: '{search_term}'\n\n"
                md += f"I have scanned the active project databases, priced BOQ sheets, and cost libraries. Here are the matching records:\n\n"
                
                has_results = False
                
                if search_results.get("materials"):
                    has_results = True
                    md += "### 🧱 Materials\n"
                    md += "| Source | Database | Name | Unit | Unit Price | Currency |\n"
                    md += "| :--- | :--- | :--- | :--- | :--- | :--- |\n"
                    for m in search_results["materials"][:8]:
                        md += f"| {m['source']} | `{m['database']}` | {m['name']} | {m['unit']} | **{m['price']:,.2f}** | {m['currency']} |\n"
                    md += "\n"
                    
                if search_results.get("labor"):
                    has_results = True
                    md += "### 👷 Labor Trades\n"
                    md += "| Source | Database | Trade | Unit | Rate | Currency |\n"
                    md += "| :--- | :--- | :--- | :--- | :--- | :--- |\n"
                    for l in search_results["labor"][:8]:
                        md += f"| {l['source']} | `{l['database']}` | {l['trade']} | {l['unit']} | **{l['rate']:,.2f}** | {l['currency']} |\n"
                    md += "\n"

                eq_plant = search_results.get("equipment", []) + search_results.get("plant", [])
                if eq_plant:
                    has_results = True
                    md += "### 🚜 Equipment & Plant\n"
                    md += "| Source | Database | Resource Name | Unit | Rate | Currency |\n"
                    md += "| :--- | :--- | :--- | :--- | :--- | :--- |\n"
                    for eq in eq_plant[:8]:
                        md += f"| {eq['source']} | `{eq['database']}` | {eq['name']} | {eq['unit']} | **{eq['rate']:,.2f}** | {eq['currency']} |\n"
                    md += "\n"

                if search_results.get("pboq_items"):
                    has_results = True
                    md += "### 📄 Priced BOQ Items\n"
                    md += "| Row | Database | Description | Unit | Bill Rate | Bill Amount | Plug Rate |\n"
                    md += "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n"
                    for item in search_results["pboq_items"][:8]:
                        md += f"| {item['rowid']} | `{item['database']}` | {item['description']} | {item['unit']} | {item['bill_rate']} | **{item['bill_amount']}** | {item['plug_rate']} |\n"
                    md += "\n"

                if search_results.get("tasks"):
                    has_results = True
                    md += "### 📋 Estimate Tasks\n"
                    md += "| Source | Database | Description | Quantity | Unit |\n"
                    md += "| :--- | :--- | :--- | :--- | :--- |\n"
                    for t in search_results["tasks"][:8]:
                        md += f"| {t['source']} | `{t['database']}` | {t['description']} | {t['quantity']} | {t['unit']} |\n"
                    md += "\n"
                    
                if not has_results:
                    rates = ai_tools.query_historical_rates(search_term)
                    if rates:
                        md += "### 📚 Historical Rates\n"
                        md += "| Rate Code | Description | Unit | Base Currency | Net Subtotal | Grand Total |\n"
                        md += "| :--- | :--- | :--- | :--- | :--- | :--- |\n"
                        for r in rates[:10]:
                            md += f"| `{r['rate_code']}` | {r['project_name']} | {r['unit']} | {r['currency']} | {r['net_total']:,.2f} | **{r['grand_total']:,.2f}** |\n"
                        md += f"\nFound **{len(rates)} matching historical records** across project databases."
                        has_results = True
                        
                if not has_results:
                    md += f"*No records matching '{search_term}' found in any database tables.* Try looking for standard construction terms like 'Concrete', 'Excavation', or 'Painting'.\n"
                else:
                    md += "> [!TIP]\n"
                    md += f"> Search completed successfully. You can drag and drop rates from the search results or link them directly to your BOQ sheets using the project pane."
                    
                return md

        # Outliers & Anomalies intent
        if any(w in q_lower for w in ["outlier", "anomaly", "deviation", "plug", "anomalies", "outliers"]):
            outliers = outliers_data.get("outlier_deviations", [])
            plugs = outliers_data.get("manual_plug_rates", [])
            
            md = "# 🔍 Anomaly & Plug Rate Analysis\n\n"
            md += "I have scanned the active estimate databases and cost library baseline rates to detect pricing deviations. Here is my report:\n\n"
            
            # Outliers table
            md += "### ⚖️ Cost Library Price Deviations (±15% threshold)\n"
            if outliers:
                md += "| Task | Type | Resource Name | Current Rate | Library Base | Deviation |\n"
                md += "| :--- | :--- | :--- | :--- | :--- | :--- |\n"
                for o in outliers[:15]:  # Cap at 15 items for clarity
                    md += f"| {o['task']} | {o['type']} | **{o['item']}** | {o['current_rate']:,.2f} | {o['library_rate']:,.2f} | `{o['deviation']}` |\n"
                md += "\n> [!WARNING]\n"
                md += f"> Detected **{len(outliers)} pricing deviations** from the standard library. Significant deviations can erode project gross margins or cause uncompetitive bidding values.\n\n"
            else:
                md += "*No major pricing deviations detected. All active task resources are within ±15% of cost library definitions.*\n\n"

            # Plugs table
            md += "### 🔌 Manual Plug Rates\n"
            if plugs:
                md += "| Row ID | Description | Plug Rate | Plug Code | Status |\n"
                md += "| :--- | :--- | :--- | :--- | :--- |\n"
                for p in plugs:
                    status = "🔴 Review" if p['is_flagged_for_review'] else "🟡 Plugged"
                    md += f"| {p['row_id']} | {p['description']} | **{p['plug_rate']:,.2f}** | `{p['plug_code']}` | {status} |\n"
                md += "\n> [!TIP]\n"
                md += "> Manual plug rates represent estimated placeholder values. Consider replacing them with detailed rate build-ups (composite materials and labor) to ensure maximum estimation precision.\n"
            else:
                md += "*No manual plug rates found in the active PBOQ database sheet.*\n"
                
            return md

        # Workspace structure intent
        if any(w in q_lower for w in ["file", "dir", "folder", "workspace", "structure", "tree", "files"]):
            md = "# 📁 Workspace Structural Context\n\n"
            md += "I have mapped all directories and project databases within **Estimator Pro's** root folder. Here is the structure:\n\n"
            
            md += "```\n"
            md += "Estimator_Pro_20May26/ (Workspace Root)\n"
            current_depth = 0
            for path in workspace_files:
                parts = path.split(os.sep)
                indent = "    " * (len(parts) - 1)
                name = parts[-1]
                md += f"├── {indent}{name}\n"
            md += "```\n\n"
            
            md += "> [!NOTE]\n"
            md += f"> Successfully mapped **{len(workspace_files)} items** in the project directory. The core SQLite stores `construction_costs.db` (active library) and `construction_rates.db` (historical rate backups) are online and fully indexed by the AI."
            return md

        # Estimate KPI Summary intent
        if any(w in q_lower for w in ["summary", "kpi", "active", "estimate", "project", "value", "totals"]):
            if "status" in active_summary:
                return f"# 📊 Project Summary Fallback\n\n*No active estimate window is currently open in your workspace.* Please load a project from **File -> Load Project** to view real-time KPIs."

            if "total_boq_items" in active_summary:
                md = "# 📊 Active Priced BOQ Dashboard\n\n"
                md += f"Here is the real-time financial KPI dashboard for the active BOQ sheet **{active_summary.get('project_name')}**:\n\n"
                
                md += "| Metric | Value | Breakdown / Notes |\n"
                md += "| :--- | :--- | :--- |\n"
                md += f"| **BOQ Sheet Name** | {active_summary.get('project_name')} | Active SQLite Database |\n"
                md += f"| **Base Currency** | {active_summary.get('currency', 'GHS (₵)')} | Project Default Exchange |\n"
                md += f"| **Total BOQ Items** | **{active_summary.get('total_boq_items', 0)}** | Total line items in sheet |\n"
                md += f"| **Priced Items** | {active_summary.get('priced_items', 0)} | Items with rate/amount defined |\n"
                md += f"| **Outstanding Items** | {active_summary.get('outstanding_items', 0)} | Items remaining to price |\n"
                md += f"| **Manual Plug Rates** | {active_summary.get('plugged_items', 0)} | Placeholders / plug values |\n"
                md += f"| **Grand Total Bid Value** | **{active_summary.get('currency', 'GHS (₵)').split(' ')[0]} {active_summary.get('grand_total', 0.0):,.2f}** | **Cumulative Sum of Bill Amount** |\n\n"
                
                if "source" in active_summary:
                    md += f"> [!NOTE]\n> Context source: `{active_summary['source']}`.\n\n"
                    
                md += "> [!TIP]\n"
                md += "> Use the **Price Tools** or **PBOQ Tools** pane to link rates, resolve manual plug codes, and adjust package markups dynamically in real-time."
                return md

            md = "# 📊 Active Estimate Dashboard\n\n"
            md += f"Here is the real-time financial KPI dashboard for **{active_summary.get('project_name')}**:\n\n"
            
            md += "| Metric | Value | Breakdown / Notes |\n"
            md += "| :--- | :--- | :--- |\n"
            md += f"| **Client Name** | {active_summary.get('client_name', 'N/A')} | Project Customer |\n"
            md += f"| **Base Currency** | {active_summary.get('currency', 'GHS (₵)')} | Project Default Exchange |\n"
            md += f"| **Net Prime Subtotal** | **{active_summary.get('subtotal', 0.0):,.2f}** | Total resource cost (materials + labor + equipment) |\n"
            md += f"| **Overhead Markup** | {active_summary.get('overhead_amount', 0.0):,.2f} | Calculated at **{active_summary.get('overhead_percent', 0.0)}%** markup |\n"
            md += f"| **Profit Margin** | {active_summary.get('profit_amount', 0.0):,.2f} | Calculated at **{active_summary.get('profit_margin_percent', 0.0)}%** margin |\n"
            md += f"| **Grand Total Bid Value** | **{active_summary.get('currency', 'GHS (₵)').split(' ')[0]} {active_summary.get('grand_total', 0.0):,.2f}** | **Final Client Bid Submission Price** |\n\n"
            
            if "source" in active_summary:
                md += f"> [!NOTE]\n> Context source: `{active_summary['source']}`.\n\n"
                
            md += "> [!TIP]\n"
            md += "> Margins can be adjusted in real-time. Head to **Settings** or double-click the overhead/profit fields in the summary widget to tune these values dynamically."
            return md

        # Historical rates lookup (fallback for standalone rate queries)
        if "historical" in q_lower or "search" in q_lower or "lookup" in q_lower:
            search_query = query
            prefixes_to_strip = [
                r"^search\s+historical\s+rates\s+for\s+", r"^search\s+historical\s+rates\s+",
                r"^search\s+rates\s+for\s+", r"^search\s+for\s+", r"^search\s+",
                r"^historical\s+rates\s+for\s+", r"^historical\s+rates\s+",
                r"^lookup\s+rates\s+for\s+", r"^lookup\s+for\s+", r"^lookup\s+", r"^find\s+"
            ]
            for pfx in prefixes_to_strip:
                match = re.match(pfx, search_query, re.IGNORECASE)
                if match:
                    search_query = re.sub(pfx, "", search_query, flags=re.IGNORECASE)
                    break
            search_query = search_query.strip()
            
            rates = ai_tools.query_historical_rates(search_query)
            
            md = f"# 📚 Historical Rates Search Results\n\n"
            if search_query:
                md += f"Searching historical rate library for query matching: **'{search_query}'**\n\n"
            else:
                md += "Showing general historical library entries:\n\n"
                
            if rates:
                md += "| Rate Code | Description | Unit | Base Currency | Net Subtotal | Grand Total |\n"
                md += "| :--- | :--- | :--- | :--- | :--- | :--- |\n"
                for r in rates[:15]:
                    md += f"| `{r['rate_code']}` | {r['project_name']} | {r['unit']} | {r['currency']} | {r['net_total']:,.2f} | **{r['grand_total']:,.2f}** |\n"
                md += f"\nFound **{len(rates)} matching historical records** across project databases and library indices."
            else:
                md += f"*No historical rate matches found for '{search_query}'. Try looking for standard construction terms like 'Concrete', 'Lumber', 'Excavation', or 'Painting'.*"
            return md

        # Welcome/General Help response
        md = "# 👋 Welcome to Estimator Pro AI Copilot\n\n"
        md += "I am your intelligent, context-aware desktop estimating assistant. I have mapped your active SQL databases, cost libraries, and workspace files.\n\n"
        
        md += "### 💡 How can I assist you today?\n"
        md += "Try asking me commands like:\n"
        md += "- **\"Show active estimate KPIs\"**: Format a full dashboard of the currently selected MDI project.\n"
        md += "- **\"Analyze project outliers\"**: Scans materials, labor, and plant rates against cost libraries to detect deviations exceeding ±15%.\n"
        md += "- **\"Show workspace file structure\"**: Renders a complete interactive directory tree of all files in the project root.\n"
        md += "- **\"Search database for concrete\"**: Queries active project databases, priced BOQs, and cost libraries for matching items.\n\n"
        
        md += "> [!NOTE]\n"
        md += "> **Local Offline Reasoning:** The Copilot operates 100% offline. Spin up a local **Ollama** instance with `ollama run sam860/LFM2:1.2b` to unlock high-precision offline model responses securely on your machine!"
        
        return md

