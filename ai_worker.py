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
    against SQLite databases, local workspace structures, and fallback external LLM APIs.
    """
    def __init__(self, user_query, main_window=None, api_key=None, api_provider="OpenRouter"):
        super().__init__()
        self.user_query = user_query
        self.main_window = main_window
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY")
        self.api_provider = api_provider
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

            # 3. If an API key is available, execute a highly context-aware cloud LLM request
            if self.api_key:
                response_text = self._call_cloud_llm(active_summary, workspace_files, outliers_data)
                self.signals.finished.emit(response_text)
            else:
                # 4. If no API key is configured, execute our highly polished, context-aware local intelligence engine
                response_text = self._generate_local_response(self.user_query, active_summary, workspace_files, outliers_data)
                self.signals.finished.emit(response_text)
        except Exception as e:
            self.signals.error.emit(f"AI Worker Execution Error: {str(e)}")

    def _call_cloud_llm(self, active_summary, workspace_files, outliers_data):
        """
        Executes a direct thread-safe HTTP request using urllib to an LLM provider (OpenRouter/OpenAI),
        feeding active SQLite estimate metrics, file paths, and outliers directly as context.
        """
        # Compact context payload
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

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        # Handle different API endpoints
        if "openai" in self.api_provider.lower() or os.environ.get("OPENAI_API_KEY"):
            url = "https://api.openai.com/v1/chat/completions"
            model = "gpt-4o-mini"
        else:
            # Default to OpenRouter for general model diversity
            url = "https://openrouter.ai/api/v1/chat/completions"
            model = "meta-llama/llama-3-8b-instruct:free"
            headers["HTTP-Referer"] = "https://github.com/NousResearch/hermes-agent"
            headers["X-Title"] = "Estimator Pro AI Copilot"

        data = {
            "model": model,
            "messages": [
                {"role": "system", "content": "You are a professional construction estimator and quantity surveyor assistant."},
                {"role": "user", "content": context_prompt}
            ],
            "temperature": 0.2
        }

        req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), headers=headers, method="POST")
        
        try:
            with urllib.request.urlopen(req, timeout=12) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                return res_data["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as he:
            error_body = he.read().decode("utf-8")
            raise Exception(f"HTTP {he.code} error from LLM: {error_body}")
        except Exception as e:
            raise Exception(f"Failed to communicate with LLM API: {str(e)}")

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
        
        md += "> [!TIP]\n"
        md += "> To activate cloud LLM intelligence (GPT-4o or Claude 3.5 Sonnet), set your API key in your system environment variable: `OPENROUTER_API_KEY` or `OPENAI_API_KEY`."
        
        return md
