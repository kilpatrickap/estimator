import sys
import os
import urllib.request
import json
import re

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, 'c:/Users/Consar-Kilpatrick/Estimator_Pro_20May26/estimator')

from ai_worker import AICopilotWorker

w = AICopilotWorker('Run a what if scenario for concrete material rates with a +10% adjustment')

class DummySignal:
    def emit(self, *args, **kwargs):
        pass

w.signals.partial_message = DummySignal()

from database import DatabaseManager
costs_db = DatabaseManager("construction_costs.db")
project_dir = costs_db.get_setting('last_project_dir', '')
if project_dir:
    project_dir = project_dir.replace('\\', '/')
    if os.path.basename(project_dir) == "Project Database":
        project_dir = os.path.dirname(project_dir)

import ai_tools
active_summary = ai_tools.query_active_estimate_summary()
outliers_data = ai_tools.get_outlier_items()

model_name = "lfm2.5:8b"

def run_loop_debug(suppress_schema):
    query_lower = w.user_query.lower()
    
    app_dir = 'c:/Users/Consar-Kilpatrick/Estimator_Pro_20May26/estimator'
    available_files = []
    for root, dirs, files in os.walk(app_dir):
        dirs[:] = [d for d in dirs if d not in {'.git', '.idea', '__pycache__', '.pytest_cache', '.vscode', 'PyTest'}]
        for f in files:
            if f.endswith('.db') or f.endswith('.json'):
                rel = os.path.relpath(os.path.join(root, f), app_dir).replace('\\', '/')
                available_files.append(rel)
                
    if project_dir and os.path.exists(project_dir):
        for root, dirs, files in os.walk(project_dir):
            for f in files:
                if f.endswith('.db') or f.endswith('.json'):
                    rel = os.path.relpath(os.path.join(root, f), project_dir).replace('\\', '/')
                    proj_base = os.path.basename(project_dir)
                    path_in_project = f"{proj_base}/{rel}".replace('\\', '/')
                    if path_in_project not in available_files:
                        available_files.append(path_in_project)

    needs_schema = not suppress_schema
    schema_context = w._generate_schema_context(available_files) if needs_schema else ""

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

    extra_context = ""
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
        "5. Always produce a substantive response. Never return only whitespace or thinking tags.\n"
        "5b. NEVER output any chain-of-thought, reasoning, or internal monologue (either in <think> tags or as plain text). Do not explain or debate how you are applying the instructions. Respond directly with the final answer.\n\n"
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
        "   - What-If: 'What if concrete prices increase by 10%?'\n"
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
    messages.append({"role": "user", "content": w.user_query})

    url = "http://localhost:11434/v1/chat/completions"
    headers = {"Content-Type": "application/json"}
    
    try:
        # Iteration 0:
        data0 = {
            "model": model_name,
            "messages": messages,
            "temperature": 0.0,
            "stream": False,
            "options": {"num_ctx": 8192, "num_predict": 2048}
        }
        req0 = urllib.request.Request(url, data=json.dumps(data0).encode("utf-8"), headers=headers, method="POST")
        with urllib.request.urlopen(req0) as r0:
            content0 = json.loads(r0.read().decode("utf-8"))["choices"][0]["message"]["content"]
            print(f"[{suppress_schema}] Iteration 0 raw response:", content0)
            messages.append({"role": "assistant", "content": content0})

        # Execute tool
        tool_res = ai_tools.run_what_if_scenario(project_dir, 'material', 'concrete', '+10%')
        result_str = json.dumps(tool_res, indent=2)
        messages.append({
            "role": "user",
            "content": f"[System Tool Result]:\n<what_if_result>\n{result_str}\n</what_if_result>"
        })

        # Iteration 1:
        data1 = {
            "model": model_name,
            "messages": messages,
            "temperature": 0.2,
            "stream": False,
            "options": {"num_ctx": 8192, "num_predict": 2048}
        }
        req1 = urllib.request.Request(url, data=json.dumps(data1).encode("utf-8"), headers=headers, method="POST")
        with urllib.request.urlopen(req1) as r1:
            res_json = json.loads(r1.read().decode("utf-8"))
            msg = res_json["choices"][0]["message"]
            content1 = msg.get("content", "")
            if not content1:
                content1 = msg.get("reasoning", "") or msg.get("reasoning_content", "")
            print(f"=== SUPPRESS SCHEMA = {suppress_schema} ===")
            print(content1)
            print("=========================================\n")
    except Exception as e:
        print(f"[{suppress_schema}] Exception:", e)

# Run both cases to verify!
run_loop_debug(suppress_schema=False)
run_loop_debug(suppress_schema=True)
