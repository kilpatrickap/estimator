import os
import json
import re
import urllib.request
import urllib.error
from PyQt6.QtCore import QRunnable, QObject, pyqtSignal
import ai_tools

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

        # B. Construct system and user prompt with rich database context
        context_prompt = (
            f"You are the AI Estimating Copilot for Estimator Pro. You have direct database access.\n"
            f"--- Active Project Context ---\n"
            f"Estimate Summary: {json.dumps(active_summary, indent=2)}\n"
            f"Project File Structure: {json.dumps(workspace_files[:40], indent=2)} (showing first 40 files)\n"
            f"Detected Pricing Outliers: {json.dumps(outliers_data, indent=2)}\n"
            f"---------------------------------\n"
            f"User Query: {self.user_query}\n"
            f"Please answer the user query in a premium, professional manner. Use markdown format, list tables "
            f"for database records, and highlight insights using beautiful warning/tip styled notes."
        )

        url = "http://localhost:11434/v1/chat/completions"
        headers = {"Content-Type": "application/json"}
        data = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": "You are a professional construction estimator and quantity surveyor assistant."},
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
        q_lower = query.lower()

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
            
            # Beautiful nested list representing workspace
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
                return f"# 📊 Project Summary\n\n*No active estimate window is currently open in your workspace.* Please load a project from **File -> Load Project** to view real-time KPIs."

            # Case A: Active window is a Priced BOQ (PBOQ) sheet
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

            # Case B: Standard Rate Build-up Estimate Window
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

        # Historical rates lookup
        if "historical" in q_lower or "search" in q_lower or "lookup" in q_lower:
            search_query = query
            # Strip out common query prefixes to handle multi-word inputs gracefully
            prefixes_to_strip = [
                r"^search\s+historical\s+rates\s+for\s+",
                r"^search\s+historical\s+rates\s+",
                r"^search\s+rates\s+for\s+",
                r"^search\s+for\s+",
                r"^search\s+",
                r"^historical\s+rates\s+for\s+",
                r"^historical\s+rates\s+",
                r"^lookup\s+rates\s+for\s+",
                r"^lookup\s+for\s+",
                r"^lookup\s+",
                r"^find\s+"
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
        md += "- **\"Search historical rates for Concrete\"**: Query the rates database library for pre-calculated pricing structures.\n\n"
        
        md += "> [!NOTE]\n"
        md += "> **Local Offline Reasoning:** The Copilot operates 100% offline. Spin up a local **Ollama** instance with `ollama run deepseek-r1` to unlock high-precision thinking model responses securely on your machine!"
        
        return md
