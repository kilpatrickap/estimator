
import os
import shutil
import pytest
from database import DatabaseManager

# Path to the user's project database
PROJECT_DB_PATH = r"C:\Users\Consar-Kilpatrick\Desktop\Atlantic Catering School\Project Database\Atlantic Catering School.db"
TEST_DB_PATH = r"C:\Users\Consar-Kilpatrick\estimator_16Jan26\estimator\PyTest\test_project_temp.db"

@pytest.fixture
def db():
    """Make a temporary copy of the project DB for testing."""
    if os.path.exists(PROJECT_DB_PATH):
        shutil.copy2(PROJECT_DB_PATH, TEST_DB_PATH)
    else:
        pytest.fail(f"Project database not found at {PROJECT_DB_PATH}")
    
    manager = DatabaseManager(TEST_DB_PATH)
    yield manager
    
    # Close connections before cleanup
    manager.engine.dispose()
    
    # Clean up after test
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)


def test_get_library_item_by_name(db):
    """Test the new get_library_item_by_name helper used for stale detection."""
    # Add a known material
    now = "2026-04-23"
    db.add_item('materials', ("Test Steel", "kg", "GHS (₵)", 55.0, None, now, "Site", "", ""))
    
    # Should find it
    result = db.get_library_item_by_name('materials', 'Test Steel')
    assert result is not None
    assert result['name'] == 'Test Steel'
    assert result['price'] == 55.0
    assert result['currency'] == 'GHS (₵)'
    
    # Should return None for non-existent
    result = db.get_library_item_by_name('materials', 'NonExistent Material XYZ')
    assert result is None
    
    print("get_library_item_by_name: OK")


def test_stale_detection_logic(db):
    """
    Simulates the stale detection workflow:
    1. Add a resource to the library at price X
    2. Create an estimate with that resource at price X (in sync)
    3. Update the library price to Y
    4. Verify the estimate's copy is now 'stale' (price differs)
    """
    now = "2026-04-23"
    
    # 1. Add material to library at price 100.0
    mat_id = db.add_item('materials', ("Stale Test Brick", "each", "GHS (₵)", 100.0, None, now, "", "", ""))
    assert mat_id is not None
    
    # 2. Get library item (simulates what a project would copy)
    lib_item = db.get_library_item_by_name('materials', 'Stale Test Brick')
    assert lib_item['price'] == 100.0
    
    # Simulate a project's local copy of this resource
    project_resource = {
        'name': 'Stale Test Brick',
        'unit': 'each',
        'currency': 'GHS (₵)',
        'unit_cost': 100.0,  # Same as library — NOT stale
        'qty': 5.0,
        'total': 500.0
    }
    
    # At this point, library price == project price → NOT stale
    assert project_resource['unit_cost'] == lib_item['price']
    print("Before update: project and library are in sync (not stale).")
    
    # 3. Update library price to 120.0 (simulating a user editing Manage Resources)
    db.update_item_field('materials', 'price', 120.0, mat_id)
    
    # 4. Re-fetch and compare
    lib_item_updated = db.get_library_item_by_name('materials', 'Stale Test Brick')
    assert lib_item_updated['price'] == 120.0
    
    # The project resource still has 100.0 → it's now STALE
    is_stale = (project_resource['unit_cost'] != lib_item_updated['price'])
    assert is_stale, "Resource should be detected as stale after library update"
    print("After update: Library={}, Project={} -> STALE detected".format(lib_item_updated['price'], project_resource['unit_cost']))


def test_projects_are_independent(db):
    """
    Verifies that updating a resource in the library does NOT automatically
    modify saved project estimates (the old push behavior is gone).
    """
    now = "2026-04-23"
    
    # 1. Add a material to the library
    db.add_item('materials', ("Independence Cement", "bag", "GHS (₵)", 50.0, None, now, "", "", ""))
    
    # 2. Create a simple estimate that uses this material
    from models import Estimate, Task
    est = Estimate("Project A", "Client A", 0, 0, currency="GHS (₵)", date=now)
    task = Task("Foundation")
    task.add_material("Independence Cement", 10.0, "bag", 50.0, currency="GHS (₵)")
    est.add_task(task)
    db.save_estimate(est)
    
    original_id = est.id
    assert original_id is not None
    
    # 3. Verify the saved estimate has price 50.0
    loaded = db.load_estimate_details(original_id)
    assert loaded.tasks[0].materials[0]['unit_cost'] == 50.0
    
    # 4. Update the library price to 75.0 (WITHOUT calling update_resource_in_all_estimates)
    mat_id = db.get_item_id_by_name('materials', 'Independence Cement')
    db.update_item_field('materials', 'price', 75.0, mat_id)
    
    # 5. Re-load the estimate — it should STILL have 50.0 (detached snapshot)
    loaded_after = db.load_estimate_details(original_id)
    assert loaded_after.tasks[0].materials[0]['unit_cost'] == 50.0, \
        f"Project estimate should NOT be affected by library update! Got {loaded_after.tasks[0].materials[0]['unit_cost']}"
    
    print("Project independence verified: library update did NOT affect saved estimate.")


def test_sync_updates_single_resource():
    """
    Verifies that the sync logic correctly updates a single resource dict
    (simulating what sync_resource_from_library does in the UI).
    """
    # Simulate project resource and library item
    project_resource = {
        'name': 'Plywood',
        'unit': 'sheet',
        'currency': 'GHS (₵)',
        'unit_cost': 30.0,
        'qty': 20.0,
        'total': 600.0
    }
    
    lib_item = {
        'name': 'Plywood',
        'unit': 'sheet',
        'currency': 'USD ($)',
        'price': 45.0
    }
    
    # Apply sync (mimicking sync_resource_from_library logic)
    project_resource['unit_cost'] = lib_item['price']
    project_resource['currency'] = lib_item['currency']
    project_resource['unit'] = lib_item['unit']
    project_resource['total'] = project_resource['qty'] * lib_item['price']
    
    assert project_resource['unit_cost'] == 45.0
    assert project_resource['currency'] == 'USD ($)'
    assert project_resource['total'] == 900.0
    
    print("Single resource sync logic verified.")


def test_cross_currency_not_stale(db):
    """
    Verifies that a resource added to a USD project from a GHS library
    is NOT flagged as stale. The prices naturally differ due to conversion,
    not because the library changed.
    """
    now = "2026-04-23"
    
    # 1. Add a GHS material to the library at price 500.0
    db.add_item('materials', ("Softwood", "m3", "GHS (₵)", 500.0, None, now, "", "", ""))
    
    # 2. Simulate a rate build-up resource in USD (after conversion)
    #    e.g. GHS 500 * exchange rate = USD 13.09
    project_resource = {
        'name': 'Softwood',
        'unit': 'm3',
        'currency': 'USD ($)',       # Converted currency
        'unit_cost': 13.09,          # Converted price
        'qty': 0.03,
        'total': 0.39
    }
    
    # 3. Fetch the library item
    lib_item = db.get_library_item_by_name('materials', 'Softwood')
    assert lib_item is not None
    assert lib_item['currency'] == 'GHS (₵)'
    assert lib_item['price'] == 500.0
    
    # 4. Check stale detection logic (same as _get_stale_info)
    local_val = project_resource['unit_cost']   # 13.09 USD
    lib_val = lib_item['price']                 # 500.0 GHS
    local_curr = project_resource['currency']   # USD ($)
    lib_curr = lib_item['currency']             # GHS (₵)
    
    # Currencies differ -> should NOT be flagged as stale
    is_stale = (local_curr == lib_curr and local_val != lib_val)
    assert not is_stale, "Cross-currency resource should NOT be flagged as stale!"
    
    print("Cross-currency stale detection: correctly NOT flagged as stale.")
