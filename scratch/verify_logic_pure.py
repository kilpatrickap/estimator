def mock_to_float(val):
    if not val: return 0.0
    try: return float(str(val).replace(',', '').strip())
    except: return 0.0

def test_prelim_logic_block():
    print("Meticulous Logic Block Verification...")
    
    # Test Data: 1 normal item, 1 prelim item
    rows = [
        ('S1', 'Steel', '1', '100', '80', 'R1', '', '', '', '', '', '', ''),
        ('S1', 'Site Office', '0', '500', '', '', 'Preliminaries', '', '', '', '', '', '')
    ]
    
    dist = {'Materials': 0.0, 'Labor': 0.0, 'Equipment': 0.0, 'Plant': 0.0, 'Subcontractors': 0.0, 'Risk': 0.0}
    t_bid, t_cost = 0.0, 0.0
    
    for r in rows:
        sheet, desc, q, b, plug, p_code, p_cat, sub, gross, r_code, prov, pc, dw = r
        qty_f, bill_f = mock_to_float(q), mock_to_float(b)
        p_val, s_val, g_val = [mock_to_float(x) for x in [plug, sub, gross]]
        
        # LOGIC UNDER TEST
        is_prelim = (str(p_cat).lower() == "preliminaries") if p_cat else False
        master_net_cost = 0.0 # Assume no master link for this test
        
        if master_net_cost > 0:
            unit_cost = master_net_cost
        else:
            if p_val > 0: unit_cost = p_val
            elif s_val > 0: unit_cost = s_val
            elif g_val > 0: unit_cost = g_val
            else: 
                unit_cost = bill_f if is_prelim and bill_f > 0 and qty_f <= 1 else 0.0
        
        calc_qty = qty_f if qty_f > 0 else (1.0 if is_prelim and bill_f > 0 else 0.0)
        item_cost = unit_cost * calc_qty
        
        if is_prelim:
            dist['Risk'] += item_cost
        else:
            # Categorization logic
            if p_val > 0: dist['Materials'] += item_cost
            elif s_val > 0: dist['Subcontractors'] += item_cost
            elif g_val > 0: dist['Labor'] += item_cost
            
        t_bid += bill_f
        t_cost += item_cost

    print(f"Results -> Bid: {t_bid}, Cost: {t_cost}, Risk: {dist['Risk']}, Mat: {dist['Materials']}")
    
    assert t_bid == 600.0
    assert t_cost == 580.0
    assert dist['Risk'] == 500.0
    assert dist['Materials'] == 80.0
    
    print("\nLOGIC BLOCK VERIFICATION PASSED!")

if __name__ == "__main__":
    test_prelim_logic_block()
