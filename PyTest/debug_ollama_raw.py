import urllib.request
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

model_name = "lfm2.5:8b"
url = "http://localhost:11434/v1/chat/completions"
headers = {"Content-Type": "application/json"}

# Construct messages for suppress_schema=True
system_prompt = (
    "You are the AI Estimating Copilot for Estimator Pro (local 'lfm2.5:8b' model). "
    "You are a world-class Quantity Surveyor and Construction Estimating Expert. "
    "You operate strictly within construction estimating, costing, BOQ, materials, labor, plant/equipment rates, and markups.\n\n"
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
    "   - What-If: 'What if concrete prices increase by 10%?'\n"
    "   - Reports: 'Generate an executive summary report'\n"
    "   - Subcontractors: 'Show subcontractor quotes', 'Compare sub quotes'\n\n"
    "### HANDLING WHAT-IF SCENARIOS\n"
    "8. If the user asks a what-if question (e.g., 'What if concrete prices increase by 10%?', 'what if labor rates decrease by 5%?', or any scenario query):\n"
    "   a. You MUST output a single `<what_if>` tool call.\n"
    "   b. Identify the resource type ('material', 'labor', 'equipment', 'plant'), name (e.g., 'concrete', 'steel', 'mason'), and adjustment (e.g., '+10%', '-5%').\n"
    "   c. Example: `<what_if resource=\"material\" name=\"concrete\" adjustment=\"+10%\" />`\n"
    "   d. Do NOT write any conversational text before outputting the tag. Just output the tag and STOP.\n\n"
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
    "--- ACTIVE LOADED PROJECT ---\n"
    "Project Name: Atlantic Catering School\n"
    "Total Boq Items: 58\n"
    "Plugged Items: 1\n"
    "Priced Items: 58\n"
    "Outstanding Items: 0\n"
    "Subtotal: USD 692,198.64\n"
    "Overhead Amount: USD 69,219.86\n"
    "Profit Amount: USD 69,219.86\n"
    "Grand Total: USD 830,638.37\n"
    "Currency: USD ($)\n"
    "Overhead Percent: 10.00%\n"
    "Profit Margin Percent: 10.00%\n"
    "Factor: USD 1.00\n"
    "-----------------------------\n\n"
    "TOOLS (output tag then STOP, system executes and returns result):\n"
    "- <query_db db=\"DBNAME\">SQL</query_db>  Query SQLite database\n"
    "- <read_json file=\"NAME\"></read_json>  Read JSON file\n"
    "- <get_knowledge_graph />  WBS hierarchy, recipe chains, QS warnings\n"
    "- <ingest_project_domains />  Project settings, SOR, resources, analytics\n"
    "- <generate_report type=\"executive_summary\" />  Generate PDF report\n"
    "- <what_if resource=\"TYPE\" name=\"NAME\" adjustment=\"±N%\" />  What-if scenario\n"
    "- <draft_rate description=\"DESC\" unit=\"UNIT\" />  Recommend rate buildup\n"
)

messages = [
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": "Run a what if scenario for concrete material rates with a +10% adjustment"},
    {"role": "assistant", "content": '<what_if resource="material" name="concrete" adjustment="+10%" />'},
    {"role": "user", "content": (
        "[System Tool Result]:\n<what_if_result>\n{\n  \"matched_items\": [\n"
        "    {\n      \"name\": \"CONC1A: Plain concrete\",\n      \"type\": \"material\",\n"
        "      \"quantity\": 1.0,\n      \"before_price\": 155.93,\n      \"after_price\": 171.52,\n"
        "      \"task\": \"Imported Rates\"\n    }\n  ],\n  \"before\": {\n"
        "    \"net_total\": 2479.84,\n    \"overhead\": 247.98,\n    \"profit\": 272.78,\n"
        "    \"grand_total\": 3000.60\n  },\n  \"after\": {\n    \"net_total\": 2511.92,\n"
        "    \"overhead\": 251.19,\n    \"profit\": 276.31,\n    \"grand_total\": 3039.43\n"
        "  },\n  \"delta\": {\n    \"net\": 32.08,\n    \"grand\": 38.82,\n"
        "    \"percent\": 1.29\n  }\n}\n</what_if_result>"
    )}
]

data = {
    "model": model_name,
    "messages": messages,
    "temperature": 0.2,
    "stream": False,
    "options": {"num_ctx": 8192, "num_predict": 2048}
}

req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), headers=headers, method="POST")
try:
    with urllib.request.urlopen(req) as response:
        res_data = json.loads(response.read().decode("utf-8"))
        print("Raw response data:")
        print(json.dumps(res_data, indent=2))
except Exception as e:
    print("Error:", e)
