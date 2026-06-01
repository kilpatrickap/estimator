# 🧠 Making the AI Copilot Smarter — Brainstorm

After a deep audit of the current Copilot architecture ([ai_worker.py](file:///c:/Users/Consar-Kilpatrick/Estimator_Pro_20May26/estimator/ai_worker.py), [ai_tools.py](file:///c:/Users/Consar-Kilpatrick/Estimator_Pro_20May26/estimator/ai_tools.py), [ai_copilot_dock.py](file:///c:/Users/Consar-Kilpatrick/Estimator_Pro_20May26/estimator/ai_copilot_dock.py)), here's what the Copilot can already do, and **8 concrete upgrades** to make it significantly smarter.

---

## 📊 Current State — What It Can Do Today

| Capability | Status |
| :--- | :--- |
| Query active project KPIs (subtotal, grand total, margins) | ✅ |
| Search historical rates across all project databases | ✅ |
| Detect price outliers (±15% deviation from cost library) | ✅ |
| Scan manual plug rates and flagged items | ✅ |
| Decompose composite rate buildups (recipe coupling) | ✅ |
| Parse WBS hierarchy and dependency warnings | ✅ |
| Ingest all 5 project domains (settings, resources, SOR, PBOQ, analytics) | ✅ |
| Proactive context injection (search results pre-fetched before LLM call) | ✅ |
| Agentic tool loop (LLM calls `<query_db>`, gets result, continues reasoning) | ✅ |
| Self-correcting SQL (retries with column hints on error) | ✅ |
| Typo-resilient file resolution (`constructioncosts.db` → `construction_costs.db`) | ✅ |
| Empty response guard (falls back to pre-fetched data) | ✅ |

> [!NOTE]
> The Copilot is already quite capable at **data retrieval and presentation**. The gap is in **contextual intelligence**, **proactive guidance**, and **taking action** on behalf of the user.

---

## 🚀 Proposed Intelligence Upgrades

### Tier 1: Context Intelligence (Making it understand more)

---

#### 💡 Idea 1: Conversation Memory & Multi-Turn Context

**Problem:** Every message is currently stateless — the Copilot forgets everything after each query. If a user asks *"Show me concrete rates"* and then follows up with *"Compare them to last year's project"*, the Copilot has no idea what "them" refers to.

**Approach:**
- Maintain a sliding window of the last N conversation turns (e.g., 5–8 messages) in `AICopilotDock`
- Inject the conversation history into the LLM's `messages[]` array as alternating `user` / `assistant` turns
- Persist history per session (cleared on "Clear Chat" or app restart)
- The `ai_worker.py` constructor already accepts `user_query` — extend it to accept `conversation_history: list[dict]`

**Impact:** Enables follow-up questions, corrections, and progressive refinement — the single biggest quality-of-life improvement.

**Effort:** 🟢 Small (2-3 hours)

**Files:** [ai_copilot_dock.py](file:///c:/Users/Consar-Kilpatrick/Estimator_Pro_20May26/estimator/ai_copilot_dock.py), [ai_worker.py](file:///c:/Users/Consar-Kilpatrick/Estimator_Pro_20May26/estimator/ai_worker.py)

---

#### 💡 Idea 2: Screen-Aware Context ("What Am I Looking At?")

**Problem:** The Copilot knows which *project* is loaded, but doesn't know which *specific screen, row, or item* the user is actively working on. If the user is editing a rate buildup for "Reinforced Concrete Slab 200mm" and asks *"Is this rate competitive?"*, the Copilot should automatically know which rate they're referring to.

**Approach:**
- Extend `_get_active_estimate_window()` in [main_window.py](file:///c:/Users/Consar-Kilpatrick/Estimator_Pro_20May26/estimator/main_window.py) to expose richer context: currently selected row in PBOQ, currently open rate buildup, currently visible analytics tab
- In the PBOQ Viewer, emit a signal with the selected row's data (`description`, `rate_code`, `qty`, `bill_rate`) whenever the selection changes
- In the Rate Buildup Dialog, expose the current estimate's full task tree
- Inject this "focus context" into the system prompt as a `--- CURRENTLY FOCUSED ITEM ---` block

**Impact:** Transforms the Copilot from a "project-level" assistant to an "item-level" assistant that understands exactly what the user is working on right now.

**Effort:** 🟡 Medium (4-6 hours)

**Files:** [main_window.py](file:///c:/Users/Consar-Kilpatrick/Estimator_Pro_20May26/estimator/main_window.py), [pboq_viewer.py](file:///c:/Users/Consar-Kilpatrick/Estimator_Pro_20May26/estimator/pboq_viewer.py), [rate_buildup_dialog.py](file:///c:/Users/Consar-Kilpatrick/Estimator_Pro_20May26/estimator/rate_buildup_dialog.py), [ai_worker.py](file:///c:/Users/Consar-Kilpatrick/Estimator_Pro_20May26/estimator/ai_worker.py)

---

### Tier 2: Proactive Intelligence (Making it think ahead)

---

#### 💡 Idea 3: Smart Suggestions Bar ("You Might Want To Ask...")

**Problem:** Users often don't know what to ask the Copilot. They see the chat box but aren't sure what's possible. The Copilot is reactive — it waits to be asked.

**Approach:**
- Add a row of 2-3 clickable "suggestion chips" above the input box in [ai_copilot_dock.py](file:///c:/Users/Consar-Kilpatrick/Estimator_Pro_20May26/estimator/ai_copilot_dock.py)
- Suggestions are contextually generated based on the current state:
  - If PBOQ is open with unpriced items → *"Price all outstanding items"*
  - If outliers detected → *"Show pricing anomalies"*
  - If rate buildup is open → *"Explain this rate breakdown"*
  - If analytics dashboard is open → *"Summarize cash flow projections"*
- Clicking a chip auto-fills and sends the query

**Impact:** Dramatically increases discoverability and engagement. Users learn what the Copilot can do through the suggestions themselves.

**Effort:** 🟡 Medium (3-4 hours)

**Files:** [ai_copilot_dock.py](file:///c:/Users/Consar-Kilpatrick/Estimator_Pro_20May26/estimator/ai_copilot_dock.py), [ai_tools.py](file:///c:/Users/Consar-Kilpatrick/Estimator_Pro_20May26/estimator/ai_tools.py)

---

#### 💡 Idea 4: What-If Analysis Engine

**Problem:** A core part of estimating is sensitivity analysis — *"What happens to my grand total if concrete prices increase by 12%?"* or *"What if we use a cheaper labor trade for plastering?"*. Currently, the Copilot can present data but cannot model scenarios.

**Approach:**
- Add a new tool function `run_what_if_scenario(resource_type, resource_name, adjustment_percent)` to [ai_tools.py](file:///c:/Users/Consar-Kilpatrick/Estimator_Pro_20May26/estimator/ai_tools.py)
- The function clones the current project's pricing data in memory, applies the adjustment, and recalculates cascading totals (task → estimate → BOQ sheet → grand total)
- Expose it to the LLM as a `<what_if>` tool tag so the model can invoke it when it detects sensitivity/scenario language
- Return a before/after comparison table

**Impact:** Turns the Copilot into a strategic bidding advisor. Users can explore trade-offs conversationally instead of manually editing rates.

**Effort:** 🔴 Large (6-8 hours)

**Files:** [ai_tools.py](file:///c:/Users/Consar-Kilpatrick/Estimator_Pro_20May26/estimator/ai_tools.py), [ai_worker.py](file:///c:/Users/Consar-Kilpatrick/Estimator_Pro_20May26/estimator/ai_worker.py)

---

#### 💡 Idea 5: Proactive Warnings on Context Change

**Problem:** The Copilot passively waits for queries. It never *volunteers* information. When a user opens a new PBOQ sheet that has 15 unpriced items and 3 outliers, it should immediately flag this.

**Approach:**
- Use the existing `context_timer` in [ai_copilot_dock.py](file:///c:/Users/Consar-Kilpatrick/Estimator_Pro_20May26/estimator/ai_copilot_dock.py) (already polling every 2.5s) to detect meaningful state changes
- Track `last_known_state` (project name, active window type, item counts)
- When significant changes are detected (new project loaded, new PBOQ sheet opened, high outlier count), auto-inject a brief "notification bubble" into the chat:
  > *"📋 I noticed you opened **'Bill 1 - Substructure'** with **58 items** (12 unpriced, 3 flagged outliers). Would you like me to analyze the pricing gaps?"*
- This is NOT an LLM call — it's a templated notification based on the context data

**Impact:** Makes the Copilot feel alive and aware, like a real estimating colleague who notices when you switch tasks.

**Effort:** 🟡 Medium (3-4 hours)

**Files:** [ai_copilot_dock.py](file:///c:/Users/Consar-Kilpatrick/Estimator_Pro_20May26/estimator/ai_copilot_dock.py), [ai_tools.py](file:///c:/Users/Consar-Kilpatrick/Estimator_Pro_20May26/estimator/ai_tools.py)

---

### Tier 3: Agentic Actions (Making it do things)

---

#### 💡 Idea 6: One-Click Auto-Pricing (Draft Composite Rate)

**Problem:** This is already envisioned in the [AI_roadmap.md](file:///c:/Users/Consar-Kilpatrick/Estimator_Pro_20May26/estimator/AI_roadmap.md) (Phase 3.1) but not implemented. When the Copilot identifies an unpriced BOQ item, it should draft a composite rate breakdown and offer to apply it.

**Approach:**
- Add `recommend_composite_buildup(item_description, unit, qty)` to [ai_tools.py](file:///c:/Users/Consar-Kilpatrick/Estimator_Pro_20May26/estimator/ai_tools.py) — it searches historical rates for the best match and constructs a draft recipe
- In the chat response, render an **"Apply Draft Rate"** button (a clickable HTML element or a dedicated `QPushButton` injected into the `MessageBubble`)
- When clicked, the button calls back into [pboq_viewer.py](file:///c:/Users/Consar-Kilpatrick/Estimator_Pro_20May26/estimator/pboq_viewer.py) to write the rate into the active project database
- Requires a confirmation dialog before writing to prevent accidental changes

**Impact:** The biggest productivity multiplier — goes from "the Copilot tells me things" to "the Copilot does things for me."

**Effort:** 🔴 Large (8-12 hours)

**Files:** [ai_tools.py](file:///c:/Users/Consar-Kilpatrick/Estimator_Pro_20May26/estimator/ai_tools.py), [ai_copilot_dock.py](file:///c:/Users/Consar-Kilpatrick/Estimator_Pro_20May26/estimator/ai_copilot_dock.py), [pboq_viewer.py](file:///c:/Users/Consar-Kilpatrick/Estimator_Pro_20May26/estimator/pboq_viewer.py), [ai_worker.py](file:///c:/Users/Consar-Kilpatrick/Estimator_Pro_20May26/estimator/ai_worker.py)

---

#### 💡 Idea 7: AI-Triggered Report Generation

**Problem:** The user currently has to navigate to the Analytics Dashboard and manually trigger PDF export. The Copilot should be able to do this on command: *"Compile an executive tender summary PDF."*

**Approach:**
- Expose a `generate_report(report_type)` tool function in [ai_tools.py](file:///c:/Users/Consar-Kilpatrick/Estimator_Pro_20May26/estimator/ai_tools.py) that wraps [report_generator.py](file:///c:/Users/Consar-Kilpatrick/Estimator_Pro_20May26/estimator/report_generator.py)
- Register it as a `<generate_report>` tag in the agentic loop in [ai_worker.py](file:///c:/Users/Consar-Kilpatrick/Estimator_Pro_20May26/estimator/ai_worker.py)
- Run the PDF compilation in the existing `QThreadPool` to keep the GUI responsive
- Return the output file path and render a clickable "Open Report" link in the chat bubble

**Impact:** Saves the user from navigating through multiple dialogs for a common end-of-project task.

**Effort:** 🟡 Medium (4-5 hours)

**Files:** [ai_tools.py](file:///c:/Users/Consar-Kilpatrick/Estimator_Pro_20May26/estimator/ai_tools.py), [ai_worker.py](file:///c:/Users/Consar-Kilpatrick/Estimator_Pro_20May26/estimator/ai_worker.py), [report_generator.py](file:///c:/Users/Consar-Kilpatrick/Estimator_Pro_20May26/estimator/report_generator.py)

---

#### 💡 Idea 8: Subcontractor Quote Intelligence

**Problem:** The app has a sophisticated [subcontractor_adjudicator.py](file:///c:/Users/Consar-Kilpatrick/Estimator_Pro_20May26/estimator/subcontractor_adjudicator.py) module, but the Copilot has no awareness of received subcontractor quotes. An estimator frequently needs to compare sub quotes against their own rate buildups.

**Approach:**
- Add a `get_subcontractor_quotes(project_dir)` function to [ai_tools.py](file:///c:/Users/Consar-Kilpatrick/Estimator_Pro_20May26/estimator/ai_tools.py) that scans the `Received RFQs/` folder for `.db` files and extracts quote summaries
- Inject sub quote data into the proactive context when the user mentions "sub", "subcontractor", "quote", or "rfq"
- Enable comparative queries: *"Compare the plumbing sub quotes against my own rate buildup"*

**Impact:** Closes the gap between the Copilot and the subcontractor adjudication workflow, which is a daily task for estimators.

**Effort:** 🟡 Medium (4-5 hours)

**Files:** [ai_tools.py](file:///c:/Users/Consar-Kilpatrick/Estimator_Pro_20May26/estimator/ai_tools.py), [ai_worker.py](file:///c:/Users/Consar-Kilpatrick/Estimator_Pro_20May26/estimator/ai_worker.py)

---

## 📋 Prioritized Implementation Order

I'd recommend this sequence based on **impact-to-effort ratio**:

| Priority | Idea | Effort | Impact |
| :---: | :--- | :---: | :---: |
| **1** | 💡 Conversation Memory (multi-turn) | 🟢 Small | 🔥🔥🔥 |
| **2** | 💡 Smart Suggestions Bar | 🟡 Medium | 🔥🔥🔥 |
| **3** | 💡 Proactive Warnings on Context Change | 🟡 Medium | 🔥🔥 |
| **4** | 💡 Screen-Aware Context | 🟡 Medium | 🔥🔥🔥 |
| **5** | 💡 AI-Triggered Report Generation | 🟡 Medium | 🔥🔥 |
| **6** | 💡 Subcontractor Quote Intelligence | 🟡 Medium | 🔥🔥 |
| **7** | 💡 What-If Analysis Engine | 🔴 Large | 🔥🔥🔥 |
| **8** | 💡 One-Click Auto-Pricing | 🔴 Large | 🔥🔥🔥🔥 |

> [!IMPORTANT]
> **Idea 1 (Conversation Memory) should be done first** — it's the lowest effort and highest impact. Every other feature becomes more useful when the Copilot can maintain context across turns.

---

## 🎯 Open Questions

1. **Which ideas resonate most with you?** I can start implementing immediately after we align.
2. **For Idea 6 (Auto-Pricing):** Should the Copilot be allowed to write directly to the project database, or should it always go through a confirmation dialog?
3. **For Idea 4 (What-If):** Should scenario results be ephemeral (chat-only), or should users be able to save scenarios for comparison?
4. **Local LLM model:** Are you planning to stay on `lfm2:24b`, or is there a possibility of switching to a more capable model (e.g., Qwen 3 30B, Llama 4 Scout) that would handle multi-turn and tool-calling more reliably?
