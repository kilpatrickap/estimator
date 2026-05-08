# Estimator 2026: Analytics & Reporting Roadmap

This document outlines the strategic vision for advanced analytics and reporting within the **Estimator** suite. These features serve as an architectural guide for transforming static PBOQ data into dynamic project intelligence.

---
## 1. Project Performance
*   **Pricing Confidence Index (PCI):** Color-coded confidence scores based on pricing source:
    *   **Verified:** Linked to Library/SOR (High Confidence).
    *   **Market:** Linked to Subcontractor Quotes (Medium Confidence).
    *   **Manual/Estimate:** Manual "Plug" Rates (High Risk).
*   **The "Gap Analysis" Gauge:** A "Pricing Progress" bar showing percent of items quantified vs. priced.
*   **Outlier Detection:** Automated flagging of rates that deviate ±15% from historical benchmarks or previous projects.

## 2. Financial & Executive Dashboards (The "CFO" Hub)
*   **KPI Headline Cards:** Real-time visibility of **Total Bid Value**, **Total Net Cost**, and **Gross Margin (%)**.
*   **Resource Distribution Donut:** Visual breakdown of the project into Materials, Labor, Plant, Subcontractors, and Risk (Prov/PC Sums).
*   **The Pareto "Top 10" Report:** Automated identification of the 20% of items representing 80% of project value.
*   **Bridge Chart (Net-to-Gross):** A waterfall chart showing the path from Base Cost → Overhead → Profit → Risk → Final Bid.
*   **Financial & Profitability Analysis Report:** Deep-dive report showing the item-level and sectional **Gross/Net Margins** for every priced component.

## 3. Operational & Procurement Logistics
*   **Bill of Materials (BOM) Aggregator:** Project-wide totals for major materials (e.g., "Total Concrete: 1,200 m³", "Total Steel: 45 Tonnes").
*   **Labor & Man-Hour Schedule:** Cumulative tradesman hours (Carpenters, Masons, Electricians) required for precise workforce planning.
*   **Logistics Footprint:** Estimating total truckloads and storage square footage required for onsite materials.

## 4. Strategic Bidding & "What-If" Analysis
*   **Markup Sensitivity Sliders:** Interactive "What-If" tool to live-calculate the impact of changing individual markup percentages.
*   **Front-Loading Analysis:** Analysis of early-phase cost vs. late-phase cost to optimize project cash-flow.
*   **Currency Exposure Heatmap:** Real-time risk analysis for bids involving multiple currencies (e.g., GHS vs. USD/EUR).

## 5. Adjudication & Supply Chain Intelligence
*   **Subcontractor Bid Spread:** Analysis of the difference between highest and lowest quotes to detect "Specification Risk."
*   **"Budget vs. Actual" Adjudication:** Comparing winning subcontractor quotes against internal "Target Rates" from Buildups.
*   **Market Heat Report:** Tracking the number of bids per package to identify "Single Source" risk areas.


---
> [!TIP]
> **Implementation Strategy:** Start with the **Headline Cards** in the PBOQ Viewer for immediate feedback, then move to a dedicated **Dashboard Tab** for the more complex visualizations.
