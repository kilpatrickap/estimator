import os
import json
import re
import sqlite3
import urllib.request
import urllib.error
from PyQt6.QtCore import QRunnable, QObject, pyqtSignal
import ai_tools

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_AI_MODEL = "lfm2.5:8b"

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
    def __init__(self, user_query, main_window=None, conversation_history=None):
        super().__init__()
        self.user_query = user_query
        self.main_window = main_window
        self.conversation_history = conversation_history or []
        self.signals = AICopilotSignals()
        self.recipe_tag = ""

    def _classify_intent(self, query_lower):
        """
        Classifies the user query into one or more intent categories to determine
        which proactive context blocks to inject. Returns a set of intent strings.
        This replaces the fragile per-keyword gating with broader semantic matching.
        """
        intents = set()

        # Greeting / small-talk detection (skip heavy context injection)
        greeting_patterns = ["hello", "hi ", "hey ", "thanks", "thank you", "bye", "okay", "ok ", "yes", "no ", "sure"]
        if any(query_lower.startswith(g) or query_lower == g.strip() for g in greeting_patterns):
            intents.add("greeting")
            return intents

        # Analysis / overview intent — broad patterns that users naturally use
        analysis_patterns = ["analy", "review", "assess", "evaluat", "examin", "audit",
                             "summary", "summarize", "summarise", "overview", "status",
                             "health", "tell me about", "how is", "how's", "look at",
                             "what about", "check ", "inspect", "diagnos", "the project",
                             "this project", "active project", "current project", "my project",
                             "kpi", "estimate"]
        if any(p in query_lower for p in analysis_patterns):
            intents.add("analysis")

        # Outlier / anomaly intent
        outlier_patterns = ["outlier", "anomal", "deviation", "flag", "plug", "variance",
                            "unusual", "suspicious", "wrong", "issue", "problem", "concern"]
        if any(p in query_lower for p in outlier_patterns):
            intents.add("outlier")

        # Search / lookup intent
        search_patterns = ["search", "find", "show", "list", "get ", "what ", "rate",
                           "price", "cost", "material", "labor", "labour", "equipment",
                           "plant", "concrete", "steel", "masonry", "plaster", "timber",
                           "painting", "electrical", "plumbing", "excavat", "formwork"]
        if any(p in query_lower for p in search_patterns):
            intents.add("search")

        # BOQ / items intent
        boq_patterns = ["boq", "pboq", "bill", "item", "priced", "unpriced", "outstanding",
                        "sheet", "quantity", "quantities"]
        if any(p in query_lower for p in boq_patterns):
            intents.add("boq")

        # WBS / structure intent
        wbs_patterns = ["wbs", "hierarchy", "section", "structure", "breakdown",
                        "dependency", "under-measurement"]
        if any(p in query_lower for p in wbs_patterns):
            intents.add("wbs")

        # Domain / settings intent
        domain_patterns = ["sor", "schedule of rates", "ingest", "settings", "exchange",
                           "currency", "overhead", "profit", "margin", "markup", "kpi", "estimate"]
        if any(p in query_lower for p in domain_patterns):
            intents.add("domains")

        # Subcontractor intent
        sub_patterns = ["sub", "subcontractor", "quote", "rfq", "tender"]
        if any(p in query_lower for p in sub_patterns):
            intents.add("subcontractor")

        # Action intent
        action_patterns = ["generate", "create", "draft", "build", "compile", "export",
                           "report", "pdf", "auto-price", "recommend"]
        if any(p in query_lower for p in action_patterns):
            intents.add("action")

        # Examples / help intent
        example_patterns = ["example", "what can you", "what do you", "help me",
                            "how to use", "what should i ask", "give me"]
        if any(p in query_lower for p in example_patterns):
            intents.add("examples")

        # If no specific intent detected, default to analysis (broad catch-all)
        if not intents:
            intents.add("analysis")

        return intents

    def _generate_project_snapshot_fallback(self, active_summary):
        """
        Generates a useful project KPI summary response from the active_summary data.
        Used as an intelligent fallback when the LLM fails to produce output.
        """
        if not active_summary or "status" in active_summary:
            return None

        currency = str(active_summary.get('currency', 'GHS')).split(' ')[0]
        proj_name = active_summary.get('project_name', 'Active Project')
        lines = [f"### 📊 Project Summary: {proj_name}\n"]

        if 'total_boq_items' in active_summary:
            total = active_summary.get('total_boq_items', 0)
            priced = active_summary.get('priced_items', 0)
            outstanding = active_summary.get('outstanding_items', 0)
            plugged = active_summary.get('plugged_items', 0)
            lines.append(f"| Metric | Value |")
            lines.append(f"| --- | --- |")
            lines.append(f"| Total BOQ Items | {total} |")
            lines.append(f"| Priced Items | {priced} |")
            lines.append(f"| Outstanding Items | {outstanding} |")
            lines.append(f"| Plugged Rates | {plugged} |")
            lines.append(f"| Net Subtotal | {currency} {active_summary.get('subtotal', 0):,.2f} |")
            lines.append(f"| Overhead ({active_summary.get('overhead_percent', 0):.1f}%) | {currency} {active_summary.get('overhead_amount', 0):,.2f} |")
            lines.append(f"| Profit ({active_summary.get('profit_margin_percent', 0):.1f}%) | {currency} {active_summary.get('profit_amount', 0):,.2f} |")
            lines.append(f"| **Grand Total** | **{currency} {active_summary.get('grand_total', 0):,.2f}** |")
        else:
            lines.append(f"| Metric | Value |")
            lines.append(f"| --- | --- |")
            lines.append(f"| Rate Code | {active_summary.get('rate_code', 'N/A')} |")
            lines.append(f"| Category | {active_summary.get('category', 'N/A')} |")
            lines.append(f"| Net Subtotal | {currency} {active_summary.get('subtotal', 0):,.2f} |")
            lines.append(f"| Grand Total | {currency} {active_summary.get('grand_total', 0):,.2f} |")

        if active_summary.get('plugged_items', 0) > 0:
            lines.append(f"\n> [!WARNING]\n> This project has **{active_summary['plugged_items']} plugged rates** that should be reviewed before final submission.")
        if active_summary.get('outstanding_items', 0) > 0:
            lines.append(f"\n> [!NOTE]\n> There are **{active_summary['outstanding_items']} unpriced items** remaining in the BOQ.")

        lines.append("\n### 💡 Suggested Next Steps")
        lines.append("- Ask me to **\"Analyze project outliers\"** to find pricing anomalies")
        lines.append("- Ask me to **\"Show active estimate KPIs\"** for a detailed breakdown")
        lines.append("- Ask me to **\"Search historical rates for [material]\"** to compare pricing")

        return "\n".join(lines)


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

            # 2. Gather local context from project tools (lazy: skip expensive calls until needed)
            active_summary = ai_tools.query_active_estimate_summary(self.main_window)
            # Outlier scanning deferred — only loaded if query references outliers/anomalies
            outliers_data = None

            # Resolve target local LLM model dynamically
            model_name = DEFAULT_AI_MODEL
            try:
                from database import DatabaseManager
                costs_db = DatabaseManager("construction_costs.db")
                model_name = costs_db.get_setting("ai_model_name", DEFAULT_AI_MODEL)
            except Exception:
                pass


            try:
                # 3. Try to call the local LLM thinking model via Ollama
                response_text = self._call_local_ollama(active_summary, outliers_data, pboq_path)
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

    def _auto_correct_query(self, sql_query):
        """
        Pre-execution query rewriting helper that maps columns to correct database column names.
        """
        query_lower = sql_query.lower()
        modified_query = sql_query
        
        # Rewrite for materials
        if "materials" in query_lower:
            modified_query = re.sub(r'\bdescription\b', 'name', modified_query, flags=re.IGNORECASE)
            modified_query = re.sub(r'\btrade\b', 'name', modified_query, flags=re.IGNORECASE)
            
        # Rewrite for labor
        if "labor" in query_lower or "labour" in query_lower:
            modified_query = re.sub(r'\bname\b', 'trade', modified_query, flags=re.IGNORECASE)
            modified_query = re.sub(r'\bdescription\b', 'trade', modified_query, flags=re.IGNORECASE)
            
        # Rewrite for equipment
        if "equipment" in query_lower:
            modified_query = re.sub(r'\bdescription\b', 'name', modified_query, flags=re.IGNORECASE)
            modified_query = re.sub(r'\btrade\b', 'name', modified_query, flags=re.IGNORECASE)
            
        # Rewrite for plant
        if "plant" in query_lower:
            modified_query = re.sub(r'\bdescription\b', 'name', modified_query, flags=re.IGNORECASE)
            modified_query = re.sub(r'\btrade\b', 'name', modified_query, flags=re.IGNORECASE)
            
        # Rewrite for indirect_costs
        if "indirect_costs" in query_lower or "indirect_cost" in query_lower:
            modified_query = re.sub(r'\bname\b', 'description', modified_query, flags=re.IGNORECASE)
            modified_query = re.sub(r'\btrade\b', 'description', modified_query, flags=re.IGNORECASE)
            
        # Rewrite for estimate_materials
        if "estimate_materials" in query_lower:
            modified_query = re.sub(r'\bdescription\b', 'name', modified_query, flags=re.IGNORECASE)
            modified_query = re.sub(r'\btrade\b', 'name', modified_query, flags=re.IGNORECASE)

        # Rewrite for estimate_labor
        if "estimate_labor" in query_lower:
            modified_query = re.sub(r'\bname\b', 'name_trade', modified_query, flags=re.IGNORECASE)
            modified_query = re.sub(r'\btrade\b', 'name_trade', modified_query, flags=re.IGNORECASE)
            modified_query = re.sub(r'\bdescription\b', 'name_trade', modified_query, flags=re.IGNORECASE)
            modified_query = re.sub(r'\bprice\b', 'rate', modified_query, flags=re.IGNORECASE)

        # Rewrite for estimate_equipment
        if "estimate_equipment" in query_lower:
            modified_query = re.sub(r'\bname\b', 'name_trade', modified_query, flags=re.IGNORECASE)
            modified_query = re.sub(r'\btrade\b', 'name_trade', modified_query, flags=re.IGNORECASE)
            modified_query = re.sub(r'\bdescription\b', 'name_trade', modified_query, flags=re.IGNORECASE)
            modified_query = re.sub(r'\bprice\b', 'rate', modified_query, flags=re.IGNORECASE)

        # Rewrite for estimate_plant
        if "estimate_plant" in query_lower:
            modified_query = re.sub(r'\bname\b', 'name_trade', modified_query, flags=re.IGNORECASE)
            modified_query = re.sub(r'\btrade\b', 'name_trade', modified_query, flags=re.IGNORECASE)
            modified_query = re.sub(r'\bdescription\b', 'name_trade', modified_query, flags=re.IGNORECASE)
            modified_query = re.sub(r'\bprice\b', 'rate', modified_query, flags=re.IGNORECASE)

        # Rewrite for estimate_indirect_costs
        if "estimate_indirect_costs" in query_lower or "estimate_indirect_cost" in query_lower:
            modified_query = re.sub(r'\bname\b', 'description', modified_query, flags=re.IGNORECASE)
            modified_query = re.sub(r'\btrade\b', 'description', modified_query, flags=re.IGNORECASE)
            modified_query = re.sub(r'\bprice\b', 'amount', modified_query, flags=re.IGNORECASE)
            modified_query = re.sub(r'\brate\b', 'amount', modified_query, flags=re.IGNORECASE)
            
        return modified_query

    def _execute_sql(self, db_name, sql_query):
        """
        Executes a custom SQLite query on a specified database file and formats the result as a markdown table.
        """
        # Automatically redirect project-specific table queries from global cost library to active project database
        if db_name in ["construction_costs.db", "constructioncosts.db"]:
            try:
                active_proj_db = ai_tools.get_active_project_db_path()
                if active_proj_db:
                    project_tables = ["estimates", "tasks", "estimate_materials", "estimate_labor", "estimate_equipment", "estimate_plant", "estimate_indirect_costs", "estimate_sub_rates", "estimate_exchange_rates", "pboq_items"]
                    query_lower = sql_query.lower()
                    if any(re.search(rf"\b{tbl}\b", query_lower) for tbl in project_tables):
                        db_name = active_proj_db
            except Exception:
                pass

        resolved_db = self._resolve_file_path(db_name)
        if not resolved_db:
            return f"Error: Database file '{db_name}' could not be located in the workspace or active project directory."
            
        try:
            conn = sqlite3.connect(resolved_db)
            cursor = conn.cursor()
            
            # Split queries by semicolon to support multiple queries executed sequentially
            statements = [s.strip() for s in sql_query.split(';') if s.strip()]
            
            if not statements:
                conn.close()
                return "Query completed successfully. No rows returned."
                
            combined_md = []
            for stmt in statements:
                # Apply pre-execution column mappings
                stmt = self._auto_correct_query(stmt)
                
                try:
                    cursor.execute(stmt)
                    rows = cursor.fetchall()
                    cols = [description[0] for description in cursor.description] if cursor.description else []
                    
                    if not rows:
                        combined_md.append(f"`{stmt}`:\nQuery completed successfully. No rows returned.\n")
                        continue
                        
                    md = f"`{stmt}`:\n\n| " + " | ".join(cols) + " |\n"
                    md += "| " + " | ".join(["---"] * len(cols)) + " |\n"
                    for row in rows[:50]:
                        row_str = [str(val) if val is not None else "NULL" for val in row]
                        md += "| " + " | ".join(row_str) + " |\n"
                        
                    if len(rows) > 50:
                        md += f"\n*(Showing first 50 of {len(rows)} rows)*\n"
                    combined_md.append(md)
                except Exception as stmt_err:
                    error_str = str(stmt_err)
                    
                    # Try dynamic self-correction on exception and retry once
                    try:
                        table_match = re.search(r'FROM\s+["\']?([a-zA-Z0-9_]+)["\']?', stmt, re.IGNORECASE)
                        if table_match:
                            tbl = table_match.group(1)
                            cursor.execute(f"PRAGMA table_info(\"{tbl}\");")
                            columns = [row[1] for row in cursor.fetchall()]
                            if columns:
                                corrected_stmt = stmt
                                has_corrections = False
                                for col in columns:
                                    err_match = re.search(r'no such column:\s+([a-zA-Z0-9_]+)', error_str)
                                    if err_match:
                                        bad_col = err_match.group(1)
                                        # Map bad description/desc/name/trade column names
                                        if bad_col.lower() in ['description', 'desc', 'name'] and col.lower() in ['description', 'desc', 'name', 'name_trade', 'trade']:
                                            corrected_stmt = re.sub(rf'\b{bad_col}\b', col, corrected_stmt, flags=re.IGNORECASE)
                                            has_corrections = True
                                        # Map bad price/rate/amount/cost/unit_cost column names
                                        elif bad_col.lower() in ['price', 'rate', 'amount', 'unit_cost', 'cost'] and col.lower() in ['price', 'rate', 'amount', 'unit_cost', 'cost']:
                                            corrected_stmt = re.sub(rf'\b{bad_col}\b', col, corrected_stmt, flags=re.IGNORECASE)
                                            has_corrections = True
                                            
                                if has_corrections:
                                    try:
                                        cursor.execute(corrected_stmt)
                                        rows = cursor.fetchall()
                                        cols = [description[0] for description in cursor.description] if cursor.description else []
                                        
                                        if not rows:
                                            combined_md.append(f"`{corrected_stmt}`:\nQuery completed successfully. No rows returned.\n")
                                            continue
                                            
                                        md = f"`{corrected_stmt}`:\n\n| " + " | ".join(cols) + " |\n"
                                        md += "| " + " | ".join(["---"] * len(cols)) + " |\n"
                                        for row in rows[:50]:
                                            row_str = [str(val) if val is not None else "NULL" for val in row]
                                            md += "| " + " | ".join(row_str) + " |\n"
                                            
                                        if len(rows) > 50:
                                            md += f"\n*(Showing first 50 of {len(rows)} rows)*\n"
                                        combined_md.append(md)
                                        continue
                                    except Exception:
                                        pass
                    except Exception:
                        pass
                        
                    # If self-correction was unsuccessful or not applicable, fall back to returning the raw error
                    # with table schema information so that calling environments (like tests or agent loops)
                    # can perform their own self-correction logic.
                    try:
                        table_match = re.search(r'FROM\s+["\']?([a-zA-Z0-9_]+)["\']?', stmt, re.IGNORECASE)
                        if table_match:
                            tbl = table_match.group(1)
                            cursor.execute(f"PRAGMA table_info(\"{tbl}\");")
                            cols = [row[1] for row in cursor.fetchall()]
                            if cols:
                                combined_md.append(f"Error executing SQL: {error_str}. Note that table '{tbl}' has columns: {', '.join(cols)}. Please correct the SQL query to use only these columns.\n")
                                continue
                    except Exception:
                        pass
                    combined_md.append(f"Error executing SQL: {error_str}\n")
                    
            conn.close()
            return "\n\n".join(combined_md)
        except Exception as e:
            return "The requested estimating database could not be accessed."

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

    def _call_local_ollama(self, active_summary, outliers_data, pboq_path=None):
        """
        Queries the local Ollama instance dynamically using the configured local LLM model,
        supporting recursive execution of SQLite queries and JSON file reading.
        """
        query_lower = self.user_query.lower()
        
        # Resolve project_dir dynamically at function scope
        project_dir = None
        if self.main_window:
            try:
                active_win = self.main_window._get_active_estimate_window()
                active_class = getattr(active_win, '__class__', None).__name__ if active_win else None
                if active_class == 'PBOQDialog' and hasattr(active_win, 'pboq_file_selector'):
                    pboq_path_cand = active_win.pboq_file_selector.currentData()
                    if pboq_path_cand:
                        project_dir = os.path.dirname(os.path.dirname(pboq_path_cand))
                elif active_class == 'AnalyticsDashboard' and hasattr(active_win, 'project_dir'):
                    project_dir = active_win.project_dir
            except:
                pass

        if not project_dir:
            try:
                from database import DatabaseManager
                costs_db = DatabaseManager("construction_costs.db")
                project_dir = costs_db.get_setting('last_project_dir', '')
            except:
                pass

        if project_dir:
            project_dir = project_dir.replace('\\', '/')
            if os.path.basename(project_dir) == "Project Database":
                project_dir = os.path.dirname(project_dir)

        # A. Auto-detect and verify specific model via tags API
        model_name = DEFAULT_AI_MODEL
        try:
            from database import DatabaseManager
            costs_db = DatabaseManager("construction_costs.db")
            model_name = costs_db.get_setting("ai_model_name", DEFAULT_AI_MODEL)
        except Exception:
            pass


        try:
            req = urllib.request.Request("http://localhost:11434/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=10) as response:
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

        # Generate database schemas ONLY if the query likely needs SQL access (skip for greetings/simple Q&A)
        schema_keywords = ["database", "table", "query", "sql", "schema", "column", "rate", "material", "labor",
                           "equipment", "plant", "cost", "price", "estimate", "boq", "pboq", "indirect", "task"]
        needs_schema = any(k in query_lower for k in schema_keywords)
        
        # Suppress schema for high-level tool intents (what-if, reports, draft rates) to prevent LLM confusion
        is_what_if = "what if" in query_lower or "what-if" in query_lower or "scenario" in query_lower
        is_report = "report" in query_lower or "pdf" in query_lower or "executive summary" in query_lower
        is_draft = "draft" in query_lower or "rate buildup" in query_lower or "buildup" in query_lower
        if is_what_if or is_report or is_draft:
            needs_schema = False

        schema_context = self._generate_schema_context(available_files) if needs_schema else ""

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

        # Fetch real-time screen-focused context (Feature 4: Screen-Aware Context)
        focused_str = ""
        if self.main_window and hasattr(self.main_window, 'get_focused_item_context'):
            try:
                focused_context = self.main_window.get_focused_item_context()
                if focused_context:
                    win_type = focused_context.get("active_window_type")
                    if win_type == "PBOQDialog":
                        sel_row = focused_context.get("selected_row", {})
                        if sel_row:
                            focused_str += "--- SCREEN-AWARE CONTEXT: CURRENTLY FOCUSED/SELECTED ROW IN SHEET ---\n"
                            focused_str += f"Sheet Name: {sel_row.get('sheet_name')}\n"
                            focused_str += f"Row Number: {sel_row.get('row_index', 0) + 1}\n"
                            focused_str += "Column Values:\n"
                            for col_name, val in sel_row.get("columns", {}).items():
                                focused_str += f"  - {col_name}: {val}\n"
                            focused_str += "--------------------------------------------------------------------\n\n"
                    elif win_type == "RateBuildUpDialog":
                        est_ctx = focused_context.get("estimate_context", {})
                        if est_ctx:
                            focused_str += "--- SCREEN-AWARE CONTEXT: CURRENTLY OPEN RATE BUILD-UP RECIPE ---\n"
                            focused_str += f"Rate Code: {est_ctx.get('rate_code')}\n"
                            focused_str += f"Description: {est_ctx.get('project_name')}\n"
                            focused_str += f"Category: {est_ctx.get('category')} | Rate Type: {est_ctx.get('rate_type')} | Unit: {est_ctx.get('unit')}\n"
                            focused_str += f"Currency: {est_ctx.get('currency')} | Adjustment Factor: {est_ctx.get('adjustment_factor')}\n"
                            focused_str += f"Subtotal: {est_ctx.get('subtotal')} | Overhead: {est_ctx.get('overhead')}% | Profit: {est_ctx.get('profit')}%\n"
                            focused_str += f"Grand Total: {est_ctx.get('grand_total')}\n"
                            
                            if est_ctx.get("tasks"):
                                focused_str += "Composite Recipe Tasks & Components:\n"
                                for t in est_ctx.get("tasks"):
                                    focused_str += f"  * Task: {t.get('description')} (Qty: {t.get('quantity')} {t.get('unit')})\n"
                                    for m in t.get("materials", []):
                                        focused_str += f"    - Material: {m.get('name')} | Qty: {m.get('qty')} | Price: {m.get('price')} | Total: {m.get('total')}\n"
                                    for l in t.get("labor", []):
                                        focused_str += f"    - Labor: {l.get('trade')} | Hours: {l.get('hours')} | Rate: {l.get('rate')} | Total: {l.get('total')}\n"
                                    for p in t.get("plant", []):
                                        focused_str += f"    - Plant: {p.get('name')} | Rate: {p.get('rate')} | Total: {p.get('total')}\n"
                                    for e in t.get("equipment", []):
                                        focused_str += f"    - Equipment: {e.get('name')} | Rate: {e.get('rate')} | Total: {e.get('total')}\n"
                                    for ic in t.get("indirect_costs", []):
                                        focused_str += f"    - Indirect Cost: {ic.get('description')} | Amount: {ic.get('amount')} | Total: {ic.get('total')}\n"
                            focused_str += "-----------------------------------------------------------------\n\n"
            except Exception:
                pass

        # Proactive context generation for local LLM helper
        extra_context = focused_str
        query_lower = self.user_query.lower()

        # SMART INTENT CLASSIFICATION: Determine what context to inject based on query intent
        intents = self._classify_intent(query_lower)

        # 1. PBOQ Price Outliers & Anomalies Context (triggered by 'outlier' or 'analysis' intent)
        if "outlier" in intents or "analysis" in intents:
            if outliers_data is None:
                outliers_data = ai_tools.get_outlier_items(pboq_path)
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
                    clean_code = re.sub(r'[^A-Z0-9]', '', code)
                    for name, r in recipe_coupling.items():
                        r_code = str(r.get("rate_code", "")).upper()
                        clean_r_code = re.sub(r'[^A-Z0-9]', '', r_code)
                        if clean_code and clean_r_code and (clean_code == clean_r_code or clean_code in clean_r_code or clean_r_code in clean_code):
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
                                    
                                cursor.execute("SELECT id, project_name, net_total, grand_total, category, rate_code FROM estimates")
                                res = None
                                matched_db_rate_code = code
                                for est_row in cursor.fetchall():
                                    est_id_cand, name_cand, net_cand, grand_cand, cat_cand, db_rate_code = est_row
                                    db_rate_code_upper = str(db_rate_code or "").upper()
                                    clean_db_code = re.sub(r'[^A-Z0-9]', '', db_rate_code_upper)
                                    if clean_code and clean_db_code and (clean_code == clean_db_code or clean_code in clean_db_code or clean_db_code in clean_code):
                                        res = (est_id_cand, name_cand, net_cand, grand_cand, cat_cand)
                                        matched_db_rate_code = db_rate_code_upper
                                        break
                                        
                                if res:
                                    est_id, name, net, grand, cat = res
                                    candidate = {
                                        "rate_code": matched_db_rate_code,
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

        # 2b. Priced BOQ item search context (triggered if query contains specific rate codes/plug codes)
        if found_codes and project_dir and os.path.exists(project_dir):
            pboq_dir = os.path.join(project_dir, "Priced BOQs")
            if os.path.exists(pboq_dir):
                dbs = [os.path.join(pboq_dir, f) for f in os.listdir(pboq_dir) if f.endswith('.db')]
                for code in found_codes:
                    matching_pboq_rows = []
                    for path in dbs:
                        sheet_db_name = os.path.basename(path)
                        sheet_name_fallback = sheet_db_name.replace('.db', '')
                        
                        # Load mapping info from state file
                        qty_col_idx = -1
                        desc_col_idx = -1
                        bill_rate_col_idx = -1
                        bill_amt_col_idx = -1
                        unit_col_idx = -1
                        
                        state_file = os.path.join(project_dir, "PBOQ States", sheet_db_name + ".json")
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
                            except:
                                pass
                                
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
                            
                            cursor.execute("SELECT * FROM pboq_items")
                            rows = cursor.fetchall()
                            conn.close()
                            
                            for row in rows:
                                row_dict = dict(zip(cols, row))
                                match = False
                                for k, v in row_dict.items():
                                    if v and ("code" in k.lower() or k.lower() in ["ratecode", "rate_code", "plugcode", "plug_code", "rate code", "plug code"]):
                                        val_upper = str(v).strip().upper()
                                        clean_val = re.sub(r'[^A-Z0-9]', '', val_upper)
                                        clean_code = re.sub(r'[^A-Z0-9]', '', code)
                                        if len(clean_code) >= 3 and len(clean_val) >= 3:
                                            if clean_code == clean_val or clean_code in clean_val or clean_val in clean_code:
                                                match = True
                                                break
                                if match:
                                    sheet_val = row_dict.get('Sheet') or row_dict.get('sheet') or (col_map.get('sheet') and row_dict.get(col_map['sheet'])) or sheet_name_fallback
                                    desc_val = row_dict.get('Description') or (col_map['desc'] and row_dict.get(col_map['desc'])) or "N/A"
                                    qty_val = row_dict.get('Quantity') or (col_map['qty'] and row_dict.get(col_map['qty'])) or 0.0
                                    unit_val = row_dict.get('Unit') or (col_map['unit'] and row_dict.get(col_map['unit'])) or "each"
                                    bill_rate_val = row_dict.get('Bill Rate') or (col_map['bill_rate'] and row_dict.get(col_map['bill_rate'])) or 0.0
                                    bill_amt_val = row_dict.get('Bill Amount') or (col_map['bill_amt'] and row_dict.get(col_map['bill_amt'])) or 0.0
                                    plug_code_val = row_dict.get('PlugCode') or (col_map['pcode'] and row_dict.get(col_map['pcode'])) or ""
                                    plug_rate_val = row_dict.get('PlugRate') or (col_map['plug'] and row_dict.get(col_map['plug'])) or 0.0
                                    rate_code_val = row_dict.get('RateCode') or (col_map['rcode'] and row_dict.get(col_map['rcode'])) or ""
                                    gross_rate_val = row_dict.get('GrossRate') or (col_map['gross'] and row_dict.get(col_map['gross'])) or 0.0
                                    is_flagged = row_dict.get('IsFlagged') or row_dict.get('is_flagged') or "No"
                                    
                                    matching_pboq_rows.append({
                                        "sheet": sheet_val,
                                        "description": desc_val,
                                        "qty": qty_val,
                                        "unit": unit_val,
                                        "bill_rate": bill_rate_val,
                                        "bill_amount": bill_amt_val,
                                        "plug_code": plug_code_val,
                                        "plug_rate": plug_rate_val,
                                        "rate_code": rate_code_val,
                                        "gross_rate": gross_rate_val,
                                        "is_flagged": is_flagged
                                    })
                        except Exception as pboq_err:
                            pass
                            
                    if matching_pboq_rows:
                        extra_context += f"--- MATCHING BOQ LINE ITEMS FOR '{code}' IN Priced BOQs ---\n"
                        for item in matching_pboq_rows:
                            extra_context += f"Sheet: {item['sheet']}\n"
                            extra_context += f"Description: {item['description']}\n"
                            extra_context += f"Quantity: {item['qty']} | Unit: {item['unit']}\n"
                            extra_context += f"Bill Rate: {item['bill_rate']} | Bill Amount: {item['bill_amount']}\n"
                            if item['plug_code'] or item['plug_rate']:
                                extra_context += f"Plug Code: {item['plug_code']} | Plug Rate: {item['plug_rate']}\n"
                            if item['rate_code'] or item['gross_rate']:
                                extra_context += f"Rate Code: {item['rate_code']} | Gross Rate: {item['gross_rate']}\n"
                            extra_context += f"Is Flagged for Review: {item['is_flagged']}\n"
                            extra_context += f"--------------------------------------------------\n"
                        extra_context += "\n"

        # 3. WBS & Under-Measurement QS Warnings Context
        if "wbs" in intents or any(k in query_lower for k in ["wbs", "hierarchy", "section", "under-measurement", "dependency", "slab", "concrete"]):
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
        if "domains" in intents or any(k in query_lower for k in ["sor", "schedule of rates", "ingest", "settings", "exchange"]):
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
        if "boq" in intents or "analysis" in intents or any(k in query_lower for k in ["list", "show", "priced", "boq", "item"]):
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

        # 7. Subcontractor Quotes Context
        if "subcontractor" in intents or any(k in query_lower for k in ["sub", "subcontractor", "quote", "rfq", "tender"]):
            try:
                sub_quotes = ai_tools.get_subcontractor_quotes(project_dir)
                if sub_quotes:
                    extra_context += "--- RECEIVED SUBCONTRACTOR QUOTES ---\n"
                    extra_context += "| Package | Subcontractor | Items Count | Total Quoted | Database File |\n"
                    extra_context += "| --- | --- | --- | --- | --- |\n"
                    for sq in sub_quotes:
                        try:
                            tq = float(sq['total_quoted'])
                            tq_str = f"{tq:.2f}"
                        except:
                            tq_str = str(sq['total_quoted'])
                        extra_context += f"| {sq['package']} | {sq['subcontractor']} | {sq['items_count']} | {tq_str} | {sq['db_file']} |\n"
                    extra_context += "--------------------------------------\n\n"
                    
                    extra_context += (
                        "[SYSTEM DIRECTIVE: The RECEIVED SUBCONTRACTOR QUOTES above already contain the subcontractor quotes data. "
                        "You MUST present this data directly in a clean, professional markdown table as your answer. "
                        "Do NOT issue any additional <query_db> calls or write any SQL. "
                        "Keep any technical database queries hidden and show only clear, user-friendly subcontractor pricing details.]\n\n"
                    )
            except Exception:
                pass

        # 6. Proactive Database & Historical Rate Search Context (GUARDED: skip for greetings/short queries)
        greeting_words = {"hello", "hi", "hey", "thanks", "thank", "bye", "okay", "ok", "yes", "no", "sure", "help", "what", "how", "why", "who", "when"}
        search_terms = []
        stop_words = {"show", "search", "find", "query", "historical", "rates", "rate", "for", "the", "a", "an", "is", "in", "active", "project", "database", "library", "libraries", "costs", "cost"}
        for word in re.split(r'[^a-zA-Z0-9\-]', query_lower):
            if len(word) >= 3 and word not in stop_words and word not in greeting_words and not word.isdigit():
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
            f"You are the AI Estimating Copilot for Estimator Pro (local '{model_name}' model). "
            "You are a world-class Quantity Surveyor and Construction Estimating Expert. "
            "You operate strictly within construction estimating, costing, BOQ, materials, labor, plant/equipment rates, and markups.\n\n"
            f"{extra_context}"
            "### MANDATORY DATA USAGE RULE\n"
            "1. If pre-fetched data (SEARCH RESULTS, BOQ ITEMS, RATE RECIPES, OUTLIERS) answers the query, present it directly as a markdown table. Do NOT issue <query_db> calls.\n"
            "2. For simple project metadata questions (currency, name, total, overhead, profit) answered by the ACTIVE PROJECT block, respond in one sentence. No SQL.\n"
            "3. NEVER show SQL, table names, column names, schema, or database errors to the user. Use domain terms only (e.g., 'priced BOQ sheet', 'unit rate').\n"
            "3b. NEVER use HTML tags like <br>, <b>, <p>, or <table> in your output. Use ONLY standard markdown: **bold**, newlines, bullet points (- or *), numbered lists, and markdown tables (| col | col |).\n\n"
            "### SELF-CORRECTION ON ERROR\n"
            "4. If a <query_result> returns an error with column hints, silently retry with correct columns. Never expose errors.\n"
            "5. Always produce a substantive response. Never return only whitespace or thinking tags.\n\n"
            "### HANDLING VAGUE, GENERAL, OR KPI QUERIES\n"
            "6. If the user asks a general or KPI question like 'analyze the project', 'how is the pricing?', 'review the estimate', 'show active estimate kpis', 'show project kpis', 'tell me about this', or any broad request:\n"
            "   a. Summarize the active project in a clean markdown table of KPIs (listing Name, Total BOQ Items, Priced Items, Outstanding Items, Plugged Rates, Subtotal, Overhead, Profit, and Grand Total) using the ACTIVE LOADED PROJECT block data.\n"
            "   b. Highlight any pricing anomalies, plugged rates, or outliers if data is available in the context above.\n"
            "   c. Provide 2-3 actionable recommendations (e.g., 'Review the plugged rates', 'Consider adjusting the concrete rate').\n"
            "   d. NEVER ask the user to clarify database tables/schemas or respond with 'I couldn't formulate an answer' if ANY project data is available in the ACTIVE PROJECT block or pre-fetched data above.\n\n"
            "### HANDLING EXAMPLE REQUESTS\n"
            "7. If the user asks for examples, help, or 'what can you do', provide 6-8 specific example questions they can ask, grouped by category:\n"
            "   - Project Analysis: 'Show active estimate KPIs', 'Analyze project outliers'\n"
            "   - Rate Lookup: 'Search historical rates for Concrete', 'Show me all labor rates'\n"
            "   - Reports: 'Generate an executive summary report'\n"
            "   - Subcontractors: 'Show subcontractor quotes', 'Compare sub quotes'\n\n"
            "### HANDLING WHAT-IF SCENARIOS\n"
            "8. If the user asks a what-if question (e.g., 'What if concrete prices increase by 10%?', 'what if labor rates decrease by 5%?', or any scenario query):\n"
            "   a. You MUST output a single `<what_if>` tool call.\n"
            "   b. Identify the resource type ('material', 'labor', 'equipment', 'plant'), name (e.g., 'concrete', 'steel', 'mason'), and adjustment (e.g., '+10%', '-5%').\n"
            "   c. Example: `<what_if resource=\"material\" name=\"concrete\" adjustment=\"+10%\" />`\n"
            "   d. Do NOT write any conversational text before outputting the tag. Just output the tag and STOP.\n"
            "   e. Once the tool executes and returns the `<what_if_result>` data block, you MUST summarize the changes in a comparative markdown table showing: Net Subtotal, Overhead, Profit, and Grand Total with columns: Cost Category, Before Adjustment, After Adjustment, Delta, and % Change. Also list the matched items that were adjusted in a separate markdown table underneath.\n\n"
            "### HANDLING DRAFT RATE REQUESTS\n"
            "9. If the user asks to draft a rate, create a rate buildup, or recommend a rate for an item (e.g., 'draft a rate for 1:2:4 concrete'):\n"
            "   a. You MUST output a single `<draft_rate>` tool call.\n"
            "   b. Specify description (e.g., '1:2:4 concrete') and unit (e.g., 'm3', 'm2').\n"
            "   c. Example: `<draft_rate description=\"1:2:4 concrete\" unit=\"m3\" />`\n"
            "   d. Do NOT write any conversational text before outputting the tag. Just output the tag and STOP.\n\n"
            "### HANDLING REPORT GENERATION REQUESTS\n"
            "10. If the user asks to generate a report, export a report, or create a PDF report:\n"
            "   a. You MUST output a single `<generate_report type=\"executive_summary\" />` tool call.\n"
            "   b. Do NOT write any conversational text before outputting the tag. Just output the tag and STOP.\n\n"
            f"{active_context}"
        )

        # Conditionally add schema context and tool instructions only when needed
        if schema_context:
            system_prompt += (
                f"Database schema:\n{schema_context}\n\n"
                "SQLite notes: Use PRAGMA table_info(tableName) for columns, SELECT name FROM sqlite_master WHERE type='table' for tables.\n\n"
            )

        system_prompt += (
            "TOOLS (output tag then STOP, system executes and returns result):\n"
            "- <query_db db=\"DBNAME\">SQL</query_db>  Query SQLite database\n"
            "- <read_json file=\"NAME\"></read_json>  Read JSON file\n"
            "- <get_knowledge_graph />  WBS hierarchy, recipe chains, QS warnings\n"
            "- <ingest_project_domains />  Project settings, SOR, resources, analytics\n"
            "- <generate_report type=\"executive_summary\" />  Generate PDF report\n"
            "- <what_if resource=\"TYPE\" name=\"NAME\" adjustment=\"±N%\" />  What-if scenario\n"
            "- <draft_rate description=\"DESC\" unit=\"UNIT\" />  Recommend rate buildup\n"
        )

        messages = [{"role": "system", "content": system_prompt}]

        # OPTIMIZATION: Trim conversation history to last 6 turns with 1200-char truncation
        # (Increased from 500 to preserve multi-turn context for follow-up questions)
        trimmed_history = self.conversation_history[-6:] if len(self.conversation_history) > 6 else self.conversation_history
        for turn in trimmed_history:
            role = turn.get("role")
            content = turn.get("content", "")
            if role == "assistant":
                content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
            # Truncate very long messages to keep context window lean
            if len(content) > 1200:
                content = content[:1200] + "..."
            messages.append({"role": role, "content": content})

        # OPTIMIZATION: Suppress thinking mode for simple queries (/no_think) on Qwen models
        simple_patterns = ["hello", "hi ", "hey", "thanks", "what is the", "what's the",
                           "show me the", "currency", "project name", "overhead", "profit",
                           "grand total", "how many"]
        is_simple = len(self.user_query.split()) <= 8 or any(p in query_lower for p in simple_patterns)
        is_qwen = "qwen" in model_name.lower()
        user_msg = self.user_query + " /no_think" if (is_simple and is_qwen) else self.user_query
        messages.append({"role": "user", "content": user_msg})


        url = "http://localhost:11434/v1/chat/completions"
        headers = {"Content-Type": "application/json"}

        for iteration in range(5):
            # Stream only on the final iteration (no tool calls detected) — intermediate tool calls use non-streaming
            is_potentially_final = (iteration > 0) or is_simple
            data = {
                "model": model_name,
                "messages": messages,
                "temperature": 0.2,
                "stream": is_potentially_final,
                "options": {
                    "num_ctx": 8192,
                    "num_predict": 2048,
                    "num_batch": 512,
                    "num_gpu": 99,
                }
            }

            req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=300) as response:
                    if is_potentially_final:
                        # Streaming: read NDJSON chunks and emit partial_message signals
                        content = ""
                        try:
                            if hasattr(response, 'data') or not hasattr(response, '__iter__'):
                                lines_source = response.read().splitlines()
                            else:
                                lines_source = response
                        except Exception:
                            lines_source = response.read().splitlines()

                        for raw_line in lines_source:
                            if isinstance(raw_line, bytes):
                                line = raw_line.decode("utf-8").strip()
                            else:
                                line = raw_line.strip()
                            if not line:
                                continue
                            # OpenAI-compatible SSE format: "data: {...}"
                            if line.startswith("data: "):
                                line = line[6:]
                            if line == "[DONE]":
                                break
                            try:
                                chunk_data = json.loads(line)
                                choices = chunk_data.get("choices", [])
                                if choices:
                                    if "message" in choices[0]:
                                        msg = choices[0]["message"]
                                        chunk_text = msg.get("content", "")
                                        if not chunk_text:
                                            chunk_text = msg.get("reasoning", "") or msg.get("reasoning_content", "")
                                    else:
                                        delta = choices[0].get("delta", {})
                                        chunk_text = delta.get("content", "")
                                        if not chunk_text:
                                            chunk_text = delta.get("reasoning", "") or delta.get("reasoning_content", "")
                                    if chunk_text:
                                        content += chunk_text
                                        
                                        # Get content without thinking tags to check for tool calls
                                        clean_content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
                                        is_tool_call = clean_content.startswith("<")
                                        
                                        if not is_tool_call:
                                            self.signals.partial_message.emit(chunk_text)
                            except (json.JSONDecodeError, KeyError, IndexError):
                                continue
                    else:
                        # Non-streaming: read full response
                        res_data = json.loads(response.read().decode("utf-8"))
                        msg = res_data["choices"][0]["message"]
                        content = msg.get("content", "")
                        if not content:
                            content = msg.get("reasoning", "") or msg.get("reasoning_content", "")
            except Exception as e:
                raise Exception(f"Local LLM API error: {str(e)}")

            # Check for <query_db>, <read_json>, <get_knowledge_graph>, or <ingest_project_domains> tags
            db_match = re.search(r'<query[-_]?db\s+db=["\']?([^"\'>]+)["\']?>(.*?)(?:</query[-_]?db>|$)', content, re.DOTALL | re.IGNORECASE)
            json_match = re.search(r'<read[-_]?json\s+file=["\']?([^"\'>]+)["\']?>(.*?)(?:</read[-_]?json>|$)', content, re.DOTALL | re.IGNORECASE)
            if not json_match:
                json_match = re.search(r'<read[-_]?json\s+file=["\']?([^"\'>]+)["\']?\s*/?>', content, re.IGNORECASE)
                
            graph_match = re.search(r'<get_knowledge_graph\s*/?>', content, re.IGNORECASE)
            if not graph_match:
                graph_match = re.search(r'<get_knowledge_graph\s*>(.*?)(?:</get_knowledge_graph>|$)', content, re.DOTALL | re.IGNORECASE)
                
            domains_match = re.search(r'<ingest_project_domains\s*/?>', content, re.IGNORECASE)
            if not domains_match:
                domains_match = re.search(r'<ingest_project_domains\s*>(.*?)(?:</ingest_project_domains>|$)', content, re.DOTALL | re.IGNORECASE)

            report_match = re.search(r'<generate[-_]?report\s+type=["\']?([^"\'>]+)["\']?\s*/?>', content, re.IGNORECASE)
            if not report_match:
                report_match = re.search(r'<generate[-_]?report\s+type=["\']?([^"\'>]+)["\']?\s*>(.*?)(?:</generate[-_]?report>|$)', content, re.DOTALL | re.IGNORECASE)
                
            # Order-independent parsing for what_if tag
            what_if_match = None
            what_if_tag = re.search(r'<what[-_]?if\s+([^>]+)/?>', content, re.IGNORECASE)
            if what_if_tag:
                attrs = what_if_tag.group(1)
                res_match = re.search(r'resource=["\']([^"\']+)["\']', attrs, re.IGNORECASE) or re.search(r'resource=([^\s>]+)', attrs, re.IGNORECASE)
                name_match = re.search(r'name=["\']([^"\']+)["\']', attrs, re.IGNORECASE) or re.search(r'name=([^\s>]+)', attrs, re.IGNORECASE)
                adj_match = re.search(r'adjustment=["\']([^"\']+)["\']', attrs, re.IGNORECASE) or re.search(r'adjustment=([^\s>]+)', attrs, re.IGNORECASE)
                if res_match and name_match and adj_match:
                    class WhatIfMatch:
                        def group(self, idx):
                            val = [res_match.group(1) or res_match.group(2), 
                                   name_match.group(1) or name_match.group(2), 
                                   adj_match.group(1) or adj_match.group(2)][idx - 1]
                            return val.strip()
                    what_if_match = WhatIfMatch()

            # Order-independent parsing for draft_rate tag
            draft_rate_match = None
            draft_rate_tag = re.search(r'<draft[-_]?rate\s+([^>]+)/?>', content, re.IGNORECASE)
            if draft_rate_tag:
                attrs = draft_rate_tag.group(1)
                desc_match = re.search(r'description=["\']([^"\']+)["\']', attrs, re.IGNORECASE) or re.search(r'description=([^\s>]+)', attrs, re.IGNORECASE)
                unit_match = re.search(r'unit=["\']([^"\']+)["\']', attrs, re.IGNORECASE) or re.search(r'unit=([^\s>]+)', attrs, re.IGNORECASE)
                if desc_match and unit_match:
                    class DraftRateMatch:
                        def group(self, idx):
                            val = [desc_match.group(1) or desc_match.group(2), 
                                   unit_match.group(1) or unit_match.group(2)][idx - 1]
                            return val.strip()
                    draft_rate_match = DraftRateMatch()

            # Heuristic: If no explicit tag matches, but the model output contains a SQL code block, treat it as an implicit database query!
            if not db_match and not json_match and not graph_match and not domains_match and not report_match and not what_if_match and not draft_rate_match:
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

            elif report_match:
                report_type = report_match.group(1).strip()
                messages.append({"role": "assistant", "content": content})
                try:
                    res = ai_tools.generate_report(project_dir, report_type)
                    if res.get("status") == "success":
                        result = f"Success! PDF report generated at: {res.get('file_path')}"
                    else:
                        result = f"Error: {res.get('message')}"
                except Exception as e:
                    result = f"Error generating report: {str(e)}"
                messages.append({
                    "role": "user",
                    "content": f"[System Tool Result]:\n<generate_report_result>\n{result}\n</generate_report_result>"
                })
                continue

            elif what_if_match:
                res_type = what_if_match.group(1).strip()
                res_name = what_if_match.group(2).strip()
                res_adj = what_if_match.group(3).strip()
                messages.append({"role": "assistant", "content": content})
                try:
                    res = ai_tools.run_what_if_scenario(project_dir, res_type, res_name, res_adj)
                    result = json.dumps(res, indent=2)
                except Exception as e:
                    result = f"Error running what-if scenario: {str(e)}"
                messages.append({
                    "role": "user",
                    "content": f"[System Tool Result]:\n<what_if_result>\n{result}\n</what_if_result>"
                })
                continue

            elif draft_rate_match:
                desc = draft_rate_match.group(1).strip()
                unit = draft_rate_match.group(2).strip()
                messages.append({"role": "assistant", "content": content})
                try:
                    res = ai_tools.recommend_composite_buildup(desc, unit, project_dir)
                    if "status" not in res:
                        import base64
                        b64_str = base64.b64encode(json.dumps(res).encode('utf-8')).decode('utf-8')
                        self.recipe_tag = f'\n\n<draft_rate_recipe b64="{b64_str}" />'
                    else:
                        self.recipe_tag = ""
                    result = json.dumps(res, indent=2)
                except Exception as e:
                    result = f"Error recommending composite buildup: {str(e)}"
                    self.recipe_tag = ""
                messages.append({
                    "role": "user",
                    "content": f"[System Tool Result]:\n<draft_rate_result>\n{result}\n</draft_rate_result>"
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
                        # Try to produce a useful project summary from active_summary
                        snapshot = self._generate_project_snapshot_fallback(active_summary)
                        if snapshot:
                            return snapshot
                        return "I processed your query but couldn't formulate a complete answer. Please try rephrasing your question, or ask something more specific about the active project."
                    
                    actual_ret = f"> [!THINK]\n> {thinking}\n\n{actual_content}"
                    if self.recipe_tag:
                        actual_ret += self.recipe_tag
                    return actual_ret
                
                # EMPTY RESPONSE GUARD: Handle completely empty LLM output
                if not content or not content.strip():
                    if extra_context and "REAL-TIME SEARCH RESULTS" in extra_context:
                        return (
                            "I found the following results from your project libraries:\n\n"
                            + self._format_proactive_context_as_response(extra_context)
                        )
                    # Try to produce a useful project summary from active_summary
                    snapshot = self._generate_project_snapshot_fallback(active_summary)
                    if snapshot:
                        return snapshot
                    return "I processed your query but couldn't formulate a complete answer. Please try rephrasing your question, or ask something more specific about the active project."
                
                actual_ret = content
                if self.recipe_tag:
                    actual_ret += self.recipe_tag
                return actual_ret

        # If it reaches the iteration limit, return the last generated content
        if not content or not content.strip():
            if extra_context and "REAL-TIME SEARCH RESULTS" in extra_context:
                return (
                    "I found the following results from your project libraries:\n\n"
                    + self._format_proactive_context_as_response(extra_context)
                )
            # Try to produce a useful project summary from active_summary
            snapshot = self._generate_project_snapshot_fallback(active_summary)
            if snapshot:
                return snapshot
            return "I processed your query but couldn't formulate a complete answer. Please try rephrasing your question, or ask something more specific about the active project."
        actual_ret = content
        if self.recipe_tag:
            actual_ret += self.recipe_tag
        return actual_ret
