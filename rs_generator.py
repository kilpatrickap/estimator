"""
Resources Schedule (RS) Generator — Core engine for extracting and aggregating
all resources (materials, labour, equipment, plant) across a priced BOQ project.

Walks each priced PBOQ row → loads its linked rate buildup from the rates DB →
extracts individual resources → scales by BOQ quantity → aggregates by
normalised name + unit across the entire project.

Usage:
    from rs_generator import RSGenerator
    gen = RSGenerator(pboq_db_path, project_dir)
    result = gen.generate()          # full project
    result = gen.generate(scope='sheet:Bill 1')  # single sheet
"""

import os
import re
import sqlite3
import json
from dataclasses import dataclass, field
from database import DatabaseManager
from orm_models import DBEstimate


# ─── Data Classes ────────────────────────────────────────────────────────────

@dataclass
class RSResourceEntry:
    """A single aggregated resource row in the Resources Schedule."""
    resource_type: str          # 'material', 'labor', 'equipment', 'plant'
    name: str                   # Display name (original casing)
    unit: str
    total_qty: float = 0.0
    weighted_rate_sum: float = 0.0   # sum(unit_rate * qty) — for weighted avg
    currency: str = ""
    total_cost: float = 0.0
    used_in_codes: set = field(default_factory=set)

    @property
    def unit_rate(self):
        """Weighted-average unit rate across all contributing items."""
        if self.total_qty == 0:
            return 0.0
        return self.weighted_rate_sum / self.total_qty


@dataclass
class RSSkippedRow:
    """A PBOQ row that was skipped because it has no resource breakdown."""
    sheet: str
    description: str
    reason: str          # 'Gross Rate', 'Subcontractor', 'Prov Sum', etc.
    bill_amount: float = 0.0


@dataclass
class RSResult:
    """Complete output of the RS generator."""
    materials: list = field(default_factory=list)        # list[RSResourceEntry]
    labor: list = field(default_factory=list)
    equipment: list = field(default_factory=list)
    plant: list = field(default_factory=list)
    skipped_rows: list = field(default_factory=list)     # list[RSSkippedRow]

    @property
    def summary(self):
        """Returns a dict of totals by resource type."""
        def _total(entries):
            return sum(e.total_cost for e in entries)
        mat_total = _total(self.materials)
        lab_total = _total(self.labor)
        eqp_total = _total(self.equipment)
        plt_total = _total(self.plant)
        grand = mat_total + lab_total + eqp_total + plt_total
        return {
            'materials_total': mat_total,
            'labor_total': lab_total,
            'equipment_total': eqp_total,
            'plant_total': plt_total,
            'grand_total': grand,
            'materials_count': len(self.materials),
            'labor_count': len(self.labor),
            'equipment_count': len(self.equipment),
            'plant_count': len(self.plant),
            'skipped_count': len(self.skipped_rows),
        }


# ─── Normalisation Helpers ───────────────────────────────────────────────────

def _normalise_key(name, unit):
    """Creates a canonical aggregation key from resource name + unit.
    
    Strips whitespace, lowercases, removes punctuation, and compresses spaces.
    """
    if not name:
        name = ""
    if not unit:
        unit = ""
    norm_name = re.sub(r'[^\w\s]', '', name.lower()).strip()
    norm_name = re.sub(r'\s+', ' ', norm_name)
    norm_unit = re.sub(r'[^\w\s]', '', unit.lower()).strip()
    return f"{norm_name}|{norm_unit}"


# ─── Generator ───────────────────────────────────────────────────────────────

class RSGenerator:
    """Core engine that generates a Resources Schedule from a PBOQ database."""

    IMPORTED_RATES_TASK = "imported rates"  # sentinel task name for composite fakes

    def __init__(self, pboq_db_path, project_dir):
        """
        Args:
            pboq_db_path: Full path to the PBOQ .db file (pboq_items table).
            project_dir:  Project root directory (contains 'Project Database', 'PBOQ States', etc.)
        """
        self.pboq_db_path = pboq_db_path
        self.project_dir = project_dir

        # Locate the rates database (project DB first, fallback to global)
        self.rates_db_manager = self._find_rates_db()

    # ── Public API ────────────────────────────────────────────────────────

    def generate(self, scope='all', selected_rowids=None):
        """
        Generates the RS data.

        Args:
            scope: 'all', 'sheet:<sheet_name>', or 'rows'
            selected_rowids: list of rowids when scope='rows'

        Returns:
            RSResult with aggregated resources.
        """
        # 1. Load PBOQ rows and column mappings
        pboq_rows = self._load_pboq_rows(scope, selected_rowids)
        mappings = self._load_mappings()

        # 2. Walk each row, extract resources
        # Accumulators: key → RSResourceEntry
        accum = {}
        skipped = []

        for row_data in pboq_rows:
            self._process_row(row_data, mappings, accum, skipped)

        # 3. Partition accumulators into typed lists
        result = RSResult(skipped_rows=skipped)
        for entry in sorted(accum.values(), key=lambda e: e.name.lower()):
            if entry.resource_type == 'material':
                result.materials.append(entry)
            elif entry.resource_type == 'labor':
                result.labor.append(entry)
            elif entry.resource_type == 'equipment':
                result.equipment.append(entry)
            elif entry.resource_type == 'plant':
                result.plant.append(entry)

        return result

    # ── Private: PBOQ Data Loading ────────────────────────────────────────

    def _find_rates_db(self):
        """Locates the rates database, preferring the project database."""
        # 1. Try Project Database folder
        project_db_dir = os.path.join(self.project_dir, "Project Database")
        if os.path.exists(project_db_dir):
            for f in os.listdir(project_db_dir):
                if f.endswith('.db'):
                    db_path = os.path.join(project_db_dir, f)
                    return DatabaseManager(db_path)

        # 2. Fallback to construction_rates.db in app dir
        app_dir = os.path.dirname(os.path.abspath(__file__))
        rates_path = os.path.join(app_dir, "construction_rates.db")
        if os.path.exists(rates_path):
            return DatabaseManager(rates_path)

        return None

    def _load_mappings(self):
        """Loads column mappings from the PBOQ state JSON file."""
        db_filename = os.path.basename(self.pboq_db_path)
        state_path = os.path.join(
            self.project_dir, "PBOQ States", db_filename + ".json"
        )
        if os.path.exists(state_path):
            try:
                with open(state_path, "r") as f:
                    data = json.load(f)
                    return data.get("mappings", {})
            except Exception:
                pass
        return {}

    def _load_pboq_rows(self, scope, selected_rowids):
        """
        Reads pboq_items and returns a list of dicts with all fields needed.
        
        Each dict has keys: 'rowid', 'sheet', 'qty', 'description', 'unit',
        'plug_code', 'rate_code', 'subbee_code', 'gross_rate', 'plug_rate',
        'subbee_rate', 'prov_sum', 'pc_sum', 'daywork', 'bill_amount',
        'plug_factor', 'plug_exchange_rates'
        """
        from pboq_logic import PBOQLogic

        conn = sqlite3.connect(self.pboq_db_path)
        PBOQLogic.ensure_schema(conn)
        cursor = conn.cursor()

        # Get all column names
        cursor.execute("PRAGMA table_info(pboq_items)")
        all_cols = [info[1] for info in cursor.fetchall()]

        # Build column index lookup
        def idx(name):
            return all_cols.index(name) if name in all_cols else -1

        # Logical columns we need
        logical_cols = [
            "Description", "Unit", "PlugCode", "RateCode", "PlugRate",
            "GrossRate", "SubbeeCode", "SubbeeRate", "ProvSum", "ProvSumCode",
            "PCSum", "PCSumCode", "Daywork", "DayworkCode",
            "PlugFactor", "PlugExchangeRates", "PlugCurrency",
            "SubbeePackage", "SubbeeName"
        ]

        # Physical columns (Column 0..N)
        quoted = [f'"{c}"' for c in all_cols]
        query = f"SELECT rowid, {', '.join(quoted)} FROM pboq_items"

        cursor.execute(query)
        raw_rows = cursor.fetchall()
        conn.close()

        # Build col name → result index map (rowid is index 0)
        col_map = {name: i + 1 for i, name in enumerate(all_cols)}

        # Load column mappings for physical column roles
        mappings = self._load_mappings()

        # Resolve physical column indices (+1 offset for 'Sheet' being col 0 in db_columns)
        # In the pboq_items table, physical columns are: Sheet, Column 0, Column 1, ...
        # The mappings dict maps role → display column index (0-based from Column 0)
        # So mapping role 'qty' → 2 means the qty is in "Column 2" which is all_cols index
        # for "Column 2".
        
        def get_physical(row, role):
            """Gets the value of a physical column by its mapping role."""
            m_idx = mappings.get(role, -1)
            if m_idx < 0:
                return None
            # The mapping index refers to the display column, which corresponds to
            # "Column {m_idx}" in the DB. However, named columns like "Description",
            # "Unit", "Bill Rate", "Bill Amount" may also be mapped.
            # We need to find which DB column name matches this index.
            # Display col 0 → all_cols[1] (skipping 'Sheet')
            db_col_idx = m_idx + 1  # +1 to skip 'Sheet'
            if db_col_idx < len(all_cols):
                col_name = all_cols[db_col_idx]
                result_idx = col_map.get(col_name)
                if result_idx is not None:
                    return row[result_idx]
            return None

        def get_logical(row, col_name):
            """Gets a logical column value by name."""
            result_idx = col_map.get(col_name)
            if result_idx is not None:
                return row[result_idx]
            return None

        # Process rows
        result = []
        for row in raw_rows:
            rowid = row[0]
            sheet = get_logical(row, 'Sheet') or "Sheet 1"

            # Apply scope filter
            if scope.startswith('sheet:'):
                target_sheet = scope[6:]
                if str(sheet) != target_sheet:
                    continue
            elif scope == 'rows' and selected_rowids:
                if rowid not in selected_rowids:
                    continue

            # Get BOQ quantity from physical mapping
            qty_val = get_physical(row, 'qty')
            boq_qty = self._parse_float(qty_val)

            # Get description and unit
            desc = get_logical(row, 'Description') or get_physical(row, 'desc') or ""
            unit = get_logical(row, 'Unit') or get_physical(row, 'unit') or ""

            # Get rate codes (logical columns are source of truth)
            plug_code = self._clean_str(get_logical(row, 'PlugCode'))
            rate_code = self._clean_str(get_logical(row, 'RateCode'))
            subbee_code = self._clean_str(get_logical(row, 'SubbeeCode'))

            # Get other logical values
            gross_rate = self._parse_float(get_logical(row, 'GrossRate'))
            plug_rate = self._parse_float(get_logical(row, 'PlugRate'))
            subbee_rate = self._parse_float(get_logical(row, 'SubbeeRate'))
            prov_sum = self._parse_float(get_logical(row, 'ProvSum'))
            pc_sum = self._parse_float(get_logical(row, 'PCSum'))
            daywork = self._parse_float(get_logical(row, 'Daywork'))

            bill_amount = self._parse_float(get_physical(row, 'bill_amount'))
            plug_factor = self._parse_float(get_logical(row, 'PlugFactor')) or 1.0

            result.append({
                'rowid': rowid,
                'sheet': str(sheet),
                'boq_qty': boq_qty,
                'description': str(desc),
                'unit': str(unit),
                'plug_code': plug_code,
                'rate_code': rate_code,
                'subbee_code': subbee_code,
                'gross_rate': gross_rate,
                'plug_rate': plug_rate,
                'subbee_rate': subbee_rate,
                'prov_sum': prov_sum,
                'pc_sum': pc_sum,
                'daywork': daywork,
                'bill_amount': bill_amount,
                'plug_factor': plug_factor,
            })

        return result

    # ── Private: Row Processing ───────────────────────────────────────────

    def _process_row(self, row_data, mappings, accum, skipped):
        """
        Processes a single PBOQ row: loads its rate buildup and extracts resources.

        Modifies accum and skipped in place.
        """
        boq_qty = row_data['boq_qty']
        if boq_qty <= 0:
            return  # Skip rows with zero or negative quantity

        # Determine which code to use (priority: PlugCode > RateCode)
        code = row_data['plug_code'] or row_data['rate_code']

        if not code:
            # No rate buildup link — check if it's a known unbroken-down type
            reason = self._classify_skipped(row_data)
            if reason:
                skipped.append(RSSkippedRow(
                    sheet=row_data['sheet'],
                    description=row_data['description'],
                    reason=reason,
                    bill_amount=row_data['bill_amount']
                ))
            return

        # Load the rate buildup from the rates DB
        if not self.rates_db_manager:
            return

        estimate = self._load_estimate_by_code(code)
        if not estimate:
            # Code exists in PBOQ but no matching rate in DB
            skipped.append(RSSkippedRow(
                sheet=row_data['sheet'],
                description=row_data['description'],
                reason=f"Rate code '{code}' not found in database",
                bill_amount=row_data['bill_amount']
            ))
            return

        # Extract resources based on rate type
        if estimate.rate_type == 'Composite':
            self._extract_composite(estimate, boq_qty, code, accum)
        else:
            # Simple or Plug rate
            self._extract_simple(estimate, boq_qty, code, accum)

    def _classify_skipped(self, row_data):
        """Determines why a row without a rate code was skipped."""
        if row_data['gross_rate'] and row_data['gross_rate'] > 0:
            return "Gross Rate (no breakdown)"
        if row_data['subbee_code'] or (row_data['subbee_rate'] and row_data['subbee_rate'] > 0):
            return "Subcontractor Rate"
        if row_data['prov_sum'] and row_data['prov_sum'] > 0:
            return "Provisional Sum"
        if row_data['pc_sum'] and row_data['pc_sum'] > 0:
            return "Prime Cost Sum"
        if row_data['daywork'] and row_data['daywork'] > 0:
            return "Daywork"
        if row_data['bill_amount'] and row_data['bill_amount'] > 0:
            return "Unclassified (has bill amount but no rate code)"
        return None  # Truly empty row, don't even add to skipped

    def _load_estimate_by_code(self, rate_code):
        """Loads an Estimate object by its rate_code from the rates DB."""
        try:
            with self.rates_db_manager.Session() as session:
                db_est = session.query(DBEstimate).filter(
                    DBEstimate.rate_code == rate_code
                ).first()
                if not db_est:
                    return None
                est_id = db_est.id
            return self.rates_db_manager.load_estimate_details(est_id)
        except Exception as e:
            print(f"RS Generator: Error loading rate '{rate_code}': {e}")
            return None

    # ── Private: Resource Extraction ──────────────────────────────────────

    def _extract_simple(self, estimate, boq_qty, rate_code, accum):
        """Extracts resources from a Simple/Plug rate buildup."""
        for task in estimate.tasks:
            # Materials
            for item in task.materials:
                resource_qty = item.get('qty', 0) or 0
                unit_cost = item.get('unit_cost', 0) or 0
                currency = item.get('currency') or estimate.currency
                rs_qty = resource_qty * boq_qty
                rs_cost = rs_qty * unit_cost

                self._accumulate(accum, 'material', item.get('name', ''),
                                 item.get('unit', ''), rs_qty, unit_cost,
                                 rs_cost, currency, rate_code)

            # Labor
            for item in task.labor:
                hours = item.get('hours', 0) or 0
                rate = item.get('rate', 0) or 0
                currency = item.get('currency') or estimate.currency
                rs_qty = hours * boq_qty
                rs_cost = rs_qty * rate

                self._accumulate(accum, 'labor', item.get('trade', ''),
                                 item.get('unit', '') or 'hr', rs_qty, rate,
                                 rs_cost, currency, rate_code)

            # Equipment
            for item in task.equipment:
                hours = item.get('hours', 0) or 0
                rate = item.get('rate', 0) or 0
                currency = item.get('currency') or estimate.currency
                rs_qty = hours * boq_qty
                rs_cost = rs_qty * rate

                self._accumulate(accum, 'equipment', item.get('name', ''),
                                 item.get('unit', '') or 'hr', rs_qty, rate,
                                 rs_cost, currency, rate_code)

            # Plant
            for item in task.plant:
                hours = item.get('hours', 0) or 0
                rate = item.get('rate', 0) or 0
                currency = item.get('currency') or estimate.currency
                rs_qty = hours * boq_qty
                rs_cost = rs_qty * rate

                self._accumulate(accum, 'plant', item.get('name', ''),
                                 item.get('unit', '') or 'hr', rs_qty, rate,
                                 rs_cost, currency, rate_code)

    def _extract_composite(self, estimate, boq_qty, rate_code, accum, depth=0):
        """
        Extracts resources from a Composite rate, recursing through sub-rates.
        
        Composite rates contain sub-rates (references to other rate buildups).
        The "Imported Rates" task contains fake material entries — skip it.
        Sub-rates may themselves be composite (nested), requiring recursive traversal.
        
        Max recursion depth is 10 to prevent infinite loops.
        """
        if depth > 10:
            print(f"RS Generator: Max recursion depth reached for rate '{rate_code}'")
            return

        # 1. Extract direct resources from non-imported tasks
        for task in estimate.tasks:
            if task.description and task.description.lower().strip() == self.IMPORTED_RATES_TASK:
                continue  # Skip the synthetic "Imported Rates" task
            
            # Extract resources from this task (same as simple)
            self._extract_task_resources(task, boq_qty, estimate.currency, rate_code, accum)

        # 2. Recurse into sub-rates
        for sub_rate in estimate.sub_rates:
            sub_qty = getattr(sub_rate, 'quantity', 1.0) or 1.0
            sub_multiplier = sub_qty * boq_qty

            if getattr(sub_rate, 'rate_type', 'Simple') == 'Composite':
                # Recursive: sub-rate is itself composite
                self._extract_composite(sub_rate, sub_multiplier, rate_code, accum, depth + 1)
            else:
                # Simple sub-rate: extract its resources with combined multiplier
                for task in sub_rate.tasks:
                    self._extract_task_resources(task, sub_multiplier, 
                                                  sub_rate.currency or estimate.currency,
                                                  rate_code, accum)

    def _extract_task_resources(self, task, multiplier, default_currency, rate_code, accum):
        """Extracts all resources from a single task, applying the given multiplier."""
        # Materials
        for item in task.materials:
            resource_qty = item.get('qty', 0) or 0
            unit_cost = item.get('unit_cost', 0) or 0
            currency = item.get('currency') or default_currency
            rs_qty = resource_qty * multiplier
            rs_cost = rs_qty * unit_cost
            self._accumulate(accum, 'material', item.get('name', ''),
                             item.get('unit', ''), rs_qty, unit_cost,
                             rs_cost, currency, rate_code)

        # Labor
        for item in task.labor:
            hours = item.get('hours', 0) or 0
            rate = item.get('rate', 0) or 0
            currency = item.get('currency') or default_currency
            rs_qty = hours * multiplier
            rs_cost = rs_qty * rate
            self._accumulate(accum, 'labor', item.get('trade', ''),
                             item.get('unit', '') or 'hr', rs_qty, rate,
                             rs_cost, currency, rate_code)

        # Equipment
        for item in task.equipment:
            hours = item.get('hours', 0) or 0
            rate = item.get('rate', 0) or 0
            currency = item.get('currency') or default_currency
            rs_qty = hours * multiplier
            rs_cost = rs_qty * rate
            self._accumulate(accum, 'equipment', item.get('name', ''),
                             item.get('unit', '') or 'hr', rs_qty, rate,
                             rs_cost, currency, rate_code)

        # Plant
        for item in task.plant:
            hours = item.get('hours', 0) or 0
            rate = item.get('rate', 0) or 0
            currency = item.get('currency') or default_currency
            rs_qty = hours * multiplier
            rs_cost = rs_qty * rate
            self._accumulate(accum, 'plant', item.get('name', ''),
                             item.get('unit', '') or 'hr', rs_qty, rate,
                             rs_cost, currency, rate_code)

    # ── Private: Aggregation ──────────────────────────────────────────────

    def _accumulate(self, accum, resource_type, name, unit, qty, unit_rate,
                    cost, currency, rate_code):
        """Aggregates a resource into the accumulator dict by normalised key."""
        if not name or not name.strip():
            return
        
        key = f"{resource_type}|{_normalise_key(name, unit)}"

        if key not in accum:
            accum[key] = RSResourceEntry(
                resource_type=resource_type,
                name=name.strip(),
                unit=unit.strip() if unit else "",
                currency=currency or "",
            )

        entry = accum[key]
        entry.total_qty += qty
        entry.weighted_rate_sum += unit_rate * qty
        entry.total_cost += cost
        if rate_code:
            entry.used_in_codes.add(rate_code)

    # ── Private: Utilities ────────────────────────────────────────────────

    @staticmethod
    def _parse_float(val):
        """Safely parses a value to float, returning 0.0 on failure."""
        if val is None:
            return 0.0
        try:
            cleaned = str(val).replace(',', '').replace('₵', '').replace('$', '').strip()
            if not cleaned:
                return 0.0
            return float(cleaned)
        except (ValueError, TypeError):
            return 0.0

    @staticmethod
    def _clean_str(val):
        """Returns a clean non-empty string or None."""
        if val is None:
            return None
        s = str(val).strip()
        return s if s and s != 'None' else None
