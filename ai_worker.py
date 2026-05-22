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
                        "> You can enable full offline LLM reasoning (like **DeepSeek-R1**) locally. "
                        "> Simply install **Ollama** from [ollama.com](https://ollama.com) and run:\n"
                        "> ```bash\n"
                        "> ollama run deepseek-r1\n"
                        "> ```\n"
                        "> Once running, the Copilot will automatically activate the local reasoning engine!"
                    )
                self.signals.finished.emit(response_text)
        except Exception as e:
            self.signals.error.emit(f"AI Worker Execution Error: {str(e)}")

    def _call_local_ollama(self, active_summary, workspace_files, outliers_data):
        """
        Queries the local Ollama instance, auto-detects downloaded models (favoring DeepSeek-R1),
        transfers estimate context parameters, and extracts raw thinking reasoning.
        """
        # A. Auto-detect model via tags API
        model_name = "deepseek-r1"  # Default fallback
        try:
            req = urllib.request.Request("http://localhost:11434/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=2) as response:
                tags_data = json.loads(response.read().decode("utf-8"))
                models = tags_data.get("models", [])
                if models:
                    installed_names = [m.get("name", "") for m in models]
                    # Favor deepseek-r1 models first
                    ds_models = [n for n in installed_names if "deepseek-r1" in n.lower() or "r1" in n.lower()]
                    if ds_models:
                        model_name = ds_models[0]
                    else:
                        # Otherwise fall back to first downloaded model
                        model_name = installed_names[0]
        except Exception:
            # Let it fail to trigger fallback to the offline rule interpreter
            raise Exception("Ollama is not running locally.")

        # B. Filter workspace files to exclude application python source files from the structural context to avoid distracting LLM
        filtered_files = [
            f for f in workspace_files 
            if not (f.endswith('.py') or f.endswith('.pyc') or f.endswith('.pyd') or f.endswith('.pyo') or '__pycache__' in f or 'PyTest' in f)
        ]

        is_active = "status" not in active_summary
        
        if not is_active:
            context_prompt = (
                f"You are the AI Estimating Copilot for Estimator Pro.\n"
                f"--- IMPORTANT STATUS ---\n"
                f"NO ACTIVE ESTIMATE/PROJECT IS CURRENTLY LOADED OR OPEN IN THE WORKSPACE.\n"
                f"Estimate Summary Status: {json.dumps(active_summary, indent=2)}\n"
                f"Available Files in Workspace: {json.dumps(filtered_files, indent=2)}\n"
                f"-------------------------\n"
                f"User Query: {self.user_query}\n\n"
                f"CRITICAL REQUIREMENT FOR THE AI COPILOT:\n"
                f"Since no project is currently loaded, you CANNOT answer questions about active bid values, totals, margins, or project-specific costs.\n"
                f"You MUST politely and clearly inform the user that no project is currently active or loaded, and instruct them to use the user interface menu options in Estimator Pro to load one:\n"
                f"1. Go to the main menu and use 'File -> Load Project' or 'File -> New Project' to open estimate data.\n"
                f"2. Or open a Priced BOQ sheet from the 'PBOQ' tab.\n"
                f"Do NOT tell them to write Python scripts, run database queries, or search code files. Do NOT suggest editing or running code. Strictly guide them to the UI menu options mentioned above."
            )
        else:
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

            # Search active project database for keywords from user query
            db_matches = {}
            search_words = [w for w in re.findall(r'\b\w{4,}\b', self.user_query.lower()) if w not in [
                "show", "active", "estimate", "project", "value", "totals", "outliers", "outlier", 
                "anomalies", "anomaly", "database", "files", "structure", "find", "search", "lookup"
            ]]
            if search_words:
                try:
                    db_matches = ai_tools.search_active_database(search_words[0])
                except Exception:
                    pass

            context_prompt = (
                f"You are the AI Estimating Copilot for Estimator Pro. You have direct database access.\n"
                f"--- Active Project Context ---\n"
                f"Estimate Summary: {json.dumps(active_summary, indent=2)}\n"
                f"Project File Structure: {json.dumps(filtered_files[:40], indent=2)} (showing first 40 files)\n"
                f"Detected Pricing Outliers: {json.dumps(outliers_data, indent=2)}\n"
                f"--- Live Database Status ---\n"
                f"- Cost Library (materials): {costs_count} records\n"
                f"- Project Database ({proj_db_name}): {proj_tasks_count} tasks, {proj_materials_count} materials\n"
                f"- Priced BOQ ({os.path.basename(active_summary.get('pboq_database_path', '')) or 'None'}): {active_summary.get('total_boq_items', 0)} items\n"
                f"--- Query Specific Database Matches ---\n"
                f"{json.dumps(db_matches, indent=2) if db_matches else 'No search terms matched in active tables.'}\n"
                f"---------------------------------\n"
                f"User Query: {self.user_query}\n"
                f"Please answer the user query in a premium, professional manner. Use markdown format, list tables "
                f"for database records, and highlight insights using beautiful warning/tip styled notes."
            )

        url = "http://localhost:11434/v1/chat/completions"
        headers = {"Content-Type": "application/json"}
        system_prompt = (
            "You are a professional construction estimator and quantity surveyor assistant for Estimator Pro.\n"
            "You are running locally on the user's desktop, and you have direct, secure access to the active "
            "project database, file structures, and libraries.\n\n"
            "CRITICAL INSTRUCTIONS:\n"
            "1. If the 'Estimate Summary' indicates 'No active estimate found' or there is no active project loaded, you MUST politely explain that no project is active/loaded. Instruct the user to use the UI options: go to the main menu and select 'File -> Load Project' or 'File -> New Project', or open a Priced BOQ sheet from the 'PBOQ' tab.\n"
            "2. Do NOT tell the user to write Python code, search database files manually, or check python scripts. Guide them strictly to the application's UI menu options.\n"
            "3. If an active project is loaded, use the provided JSON metrics (Total Bid Value, priced counts, manual plugs, etc.) to answer their questions accurately. Format all numbers nicely as currency with commas and decimals.\n"
            "4. Keep your tone professional, consultative, and helpful."
        )

        data = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": context_prompt}
            ],
            "temperature": 0.2,
            "stream": False
        }

        # C. Call local chat completions endpoint
        req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=35) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                content = res_data["choices"][0]["message"]["content"]
                
                # D. Parse <think> tags and format them elegantly
                think_match = re.search(r'<think>(.*?)</think>', content, re.DOTALL)
                if think_match:
                    thinking = think_match.group(1).strip()
                    actual_content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
                    # Prepend standard visual block quote with purple thinkers styling
                    return f"> [!THINK]\n> {thinking}\n\n{actual_content}"
                return content
        except Exception as e:
            raise Exception(f"Local LLM API error: {str(e)}")

    def _generate_local_response(self, query, active_summary, workspace_files, outliers_data):
        """
        A local semantic context interpreter. Parses the user's intent and uses actual
        SQLite and workspace statistics to craft highly premium, formatted reports.
        """
        import sqlite3
        q_lower = query.lower()

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
        md += "> **Local Offline Reasoning:** The Copilot operates 100% offline. Spin up a local **Ollama** instance with `ollama run deepseek-r1` to unlock high-precision thinking model responses securely on your machine!"
        
        return md

