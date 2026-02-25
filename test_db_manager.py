from database import DatabaseManager

def test_db_manager():
    db = DatabaseManager()
    
    # Test read settings
    curr = db.get_setting('currency', 'fallback')
    print(f"Currency setting: {curr}")

    # Test read library
    mats = db.get_items('materials')
    print(f"Materials count: {len(mats)}")
    if mats:
        print(f"First mat: {mats[0]['name']} at {mats[0]['price']}")

    # Test reading estimates
    ests = db.get_saved_estimates_summary()
    print(f"Estimates count: {len(ests)}")
    if ests:
        est = db.load_estimate_details(ests[0]['id'])
        print(f"Loaded estimate: {est.project_name}, Total: {est.calculate_totals()['grand_total']}")

if __name__ == '__main__':
    test_db_manager()
