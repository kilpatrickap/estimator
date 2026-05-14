import os
import json
import sqlite3
import pytest
from unittest.mock import MagicMock

# We'll test the logic by creating a dummy class that mimics the relevant parts of ProjectPerformanceAnalytic
class DummyAnalytic:
    def __init__(self, project_dir):
        self.project_dir = project_dir
        self.pboq_folder = os.path.join(self.project_dir, "Priced BOQs")
        self.overhead_rate = 0.0
        self.profit_rate = 0.0

    def _to_float(self, val):
        if not val: return 0.0
        if isinstance(val, (int, float)): return float(val)
        try: return float(str(val).replace(',', '').replace(' ', '').replace('₵','').replace('$','').strip())
        except: return 0.0

    def _get_net_rate(self, code):
        return 0.0

    def test_logic(self, db_rows, state_data):
        # This mirrors the logic in refresh_data
        priced_items = 0
        total_items = 0
        total_cost = 0.0
        dummy_val = state_data.get('dummy_rate', 0.1)

        for r in db_rows:
            sheet, desc, q, br, ba, gross, plug, sub, prov, pc, dw, flag, rcode, pcode = r
            desc_low = (desc or "").lower()
            if not str(desc).strip() or "collection" in desc_low or "summary" in desc_low:
                continue
                
            qty_f = self._to_float(q)
            bill_rate_f = self._to_float(br)
            bill_amt_f = self._to_float(ba)
            
            if qty_f == 0 and bill_amt_f == 0:
                continue
            
            g_val = self._to_float(gross)
            p_val = self._to_float(plug)
            s_val = self._to_float(sub)
            pr_val = self._to_float(prov)
            pc_val = self._to_float(pc)
            d_val = self._to_float(dw)
            
            # --- THE LOGIC UNDER TEST ---
            is_row_priced = (g_val > 0 or p_val > 0 or s_val > 0 or pr_val > 0 or pc_val > 0 or d_val > 0)
            if not is_row_priced:
                if bill_rate_f > 0 and abs(bill_rate_f - dummy_val) > 0.0001:
                    is_row_priced = True
                    
            is_priced = is_row_priced
            
            unit_cost = bill_rate_f # Simplification for test
            calc_qty = qty_f
            item_net_cost = round(unit_cost * calc_qty, 2) if is_priced else 0.0
            # ----------------------------

            total_items += 1
            if is_priced:
                priced_items += 1
                total_cost += item_net_cost
        
        return priced_items, total_items, total_cost

def test_cost_zeroing_for_dummies():
    analytic = DummyAnalytic("/tmp/project")
    
    # Case: Items have dummy rate 0.10. Total cost should be 0.
    db_rows = [
        ("Sheet1", "Item 1", "10", "0.10", "1.00", "0", "0", "0", "0", "0", "0", "0", "", ""),
        ("Sheet1", "Item 2", "20", "0.10", "2.00", "0", "0", "0", "0", "0", "0", "0", "", ""),
    ]
    state_data = {"dummy_rate": 0.1}
    
    priced, total, cost = analytic.test_logic(db_rows, state_data)
    assert total == 2
    assert priced == 0
    assert cost == 0.0  # Financial summary should be 0

def test_cost_inclusion_for_priced():
    analytic = DummyAnalytic("/tmp/project")
    
    # Case: One dummy, one priced. Total cost should only include priced.
    db_rows = [
        ("Sheet1", "Item 1", "10", "0.10", "1.00", "0", "0", "0", "0", "0", "0", "0", "", ""),
        ("Sheet1", "Item 2", "10", "10.00", "100.00", "0", "0", "0", "0", "0", "0", "0", "", ""),
    ]
    state_data = {"dummy_rate": 0.1}
    
    priced, total, cost = analytic.test_logic(db_rows, state_data)
    assert total == 2
    assert priced == 1
    assert cost == 100.0  # Only the priced item contributes
