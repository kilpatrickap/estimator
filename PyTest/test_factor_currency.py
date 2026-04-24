"""
Tests for the global factor update feature in Project Settings.

Verifies that when a global factor is applied via bulk_update_estimate_factor,
the resulting grand_total stays in the project currency (USD) and does NOT
revert to the resource's original foreign currency (GHS).

Uses the Atlantic Catering School project as a real-world reference database.
"""

import os
import shutil
import pytest
from database import DatabaseManager
from models import Estimate, Task

# Path to the user's project database
PROJECT_DB_PATH = r"C:\Users\Consar-Kilpatrick\Desktop\Atlantic Catering School\Project Database\Atlantic Catering School.db"
TEST_DB_PATH = r"C:\Users\Consar-Kilpatrick\estimator_16Jan26\estimator\PyTest\test_factor_temp.db"


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
    try:
        if os.path.exists(TEST_DB_PATH):
            os.remove(TEST_DB_PATH)
    except PermissionError:
        pass  # Windows file lock race; harmless


@pytest.fixture
def fresh_db():
    """Create a completely fresh test database for isolated tests."""
    db_path = os.path.join(os.path.dirname(__file__), "test_fresh_temp.db")
    # Ensure clean slate
    if os.path.exists(db_path):
        os.remove(db_path)
    manager = DatabaseManager(db_path)
    yield manager
    manager.engine.dispose()
    try:
        if os.path.exists(db_path):
            os.remove(db_path)
    except PermissionError:
        pass  # Windows file lock race; harmless


class TestFactorWithMixedCurrencies:
    """Tests that global factor updates correctly handle estimates with foreign-currency resources."""

    def test_factor_preserves_project_currency_grand_total(self, db):
        """
        Core regression test: Applying a global factor must produce correct
        grand_totals that are consistent with calculate_totals().
        
        All estimates must scale by exactly the same ratio when the factor changes,
        proving that no estimate has stale/unconverted currency values.
        """
        # 1. Load CONC1A - a rate that previously had the currency reversion bug
        est = db.load_estimate_details(9)  # CONC1A
        assert est is not None, "Estimate CONC1A (id=9) must exist"
        assert est.currency == "USD ($)", "Project currency must be USD"

        # 2. Compute the correct grand_total via the model
        correct_totals = est.calculate_totals()
        correct_grand = correct_totals['grand_total']
        orig_factor = est.adjustment_factor

        # 3. Apply a new factor
        new_factor = 1.1
        db.bulk_update_estimate_factor(new_factor)

        # 4. Reload and verify
        est_after = db.load_estimate_details(9)
        assert est_after.adjustment_factor == new_factor, "Factor should be updated"

        totals_after = est_after.calculate_totals()
        grand_after = totals_after['grand_total']

        # 5. Verify the scaling ratio is correct
        if correct_grand > 0:
            actual_ratio = grand_after / correct_grand
            expected_ratio = new_factor / orig_factor
            assert abs(actual_ratio - expected_ratio) < 0.001, (
                f"Scaling ratio {actual_ratio:.4f} != expected {expected_ratio:.4f}. "
                f"Grand went from {correct_grand:.2f} to {grand_after:.2f}"
            )

        # 6. Verify the math is correct:
        # grand = raw_subtotal_in_usd * factor * (1 + overhead% + profit%)
        raw_subtotal = sum(
            est_after.convert_to_base_currency(item['total'], item.get('currency'))
            for task in est_after.tasks
            for item in task.all_items
        )
        expected_grand = raw_subtotal * new_factor * (
            1 + est_after.overhead_percent / 100 + est_after.profit_margin_percent / 100
        )
        assert abs(grand_after - expected_grand) < 0.01, (
            f"Grand total {grand_after:.6f} != expected {expected_grand:.6f}"
        )

        print(f"✓ Factor {new_factor}: grand_total={grand_after:.2f} USD (correct)")

    def test_factor_update_does_not_double_apply(self, fresh_db):
        """
        Verifies that calling bulk_update_estimate_factor multiple times
        does not double-apply the factor. Each call should produce the same
        result when using the same factor value.
        """
        db = fresh_db
        now = "2026-04-24"

        # Create an estimate with a simple resource
        est = Estimate("Test Rate", "Client", 10.0, 5.0, currency="USD ($)", date=now)
        task = Task("Work Item")
        task.add_labor("Worker", 10.0, 20.0, currency="USD ($)")  # 10hr * $20 = $200
        est.add_task(task)
        est.adjustment_factor = 1.0
        db.save_estimate(est)
        est_id = est.id

        # Apply factor 1.5
        db.bulk_update_estimate_factor(1.5)
        loaded1 = db.load_estimate_details(est_id)
        grand1 = loaded1.calculate_totals()['grand_total']

        # Apply factor 1.5 AGAIN (idempotency check)
        db.bulk_update_estimate_factor(1.5)
        loaded2 = db.load_estimate_details(est_id)
        grand2 = loaded2.calculate_totals()['grand_total']

        assert abs(grand1 - grand2) < 0.01, (
            f"Double-apply detected! First: {grand1:.2f}, Second: {grand2:.2f}"
        )

        # Verify the math: $200 * 1.5 * (1 + 0.10 + 0.05) = $345.00
        expected = 200.0 * 1.5 * 1.15
        assert abs(grand1 - expected) < 0.01, (
            f"Grand total {grand1:.2f} != expected {expected:.2f}"
        )

        print(f"✓ Idempotent factor: grand_total={grand1:.2f} (correct, no double-apply)")

    def test_factor_with_exchange_rate_conversion(self, fresh_db):
        """
        Tests factor application on an estimate with resources in a DIFFERENT currency
        than the project, with exchange rates configured.
        
        This is the exact scenario that triggered the original bug.
        """
        db = fresh_db
        now = "2026-04-24"

        # Project currency is USD, resource is in GHS
        est = Estimate("Mixed Currency Rate", "Client", 10.0, 5.0, currency="USD ($)", date=now)
        task = Task("Foundation Work")
        # Resource priced in GHS: 1000 GHS
        task.add_material("Local Cement", 10.0, "bag", 100.0, currency="GHS (₵)")
        est.add_task(task)

        # Exchange rate: GHS -> USD via division by 10 (i.e., 1 USD = 10 GHS)
        est.exchange_rates["GHS (₵)"] = {'rate': 10.0, 'date': now, 'operator': '/'}
        est.adjustment_factor = 1.0
        db.save_estimate(est)
        est_id = est.id

        # Verify initial grand total (in USD)
        loaded = db.load_estimate_details(est_id)
        totals = loaded.calculate_totals()
        # 10 bags * 100 GHS = 1000 GHS / 10 = 100 USD
        # 100 * 1.0 factor * (1 + 0.10 + 0.05) = 115.00
        expected_initial = 100.0 * 1.0 * 1.15
        assert abs(totals['grand_total'] - expected_initial) < 0.01, (
            f"Initial grand_total {totals['grand_total']:.2f} != {expected_initial:.2f}"
        )

        # Apply a new factor
        db.bulk_update_estimate_factor(0.9)

        # Reload and verify — the grand total must be in USD, not GHS!
        loaded_after = db.load_estimate_details(est_id)
        totals_after = loaded_after.calculate_totals()

        # Expected: 100 USD * 0.9 * 1.15 = 103.50
        expected_after = 100.0 * 0.9 * 1.15
        assert abs(totals_after['grand_total'] - expected_after) < 0.01, (
            f"After factor, grand_total {totals_after['grand_total']:.2f} != {expected_after:.2f}. "
            f"Possible currency reversion to GHS!"
        )

        # Extra guard: grand total should NOT be near the GHS value
        # GHS would be: 1000 * 0.9 * 1.15 = 1035.00
        ghs_wrong_value = 1000.0 * 0.9 * 1.15
        assert abs(totals_after['grand_total'] - ghs_wrong_value) > 100.0, (
            f"Grand total {totals_after['grand_total']:.2f} is suspiciously close to the GHS value "
            f"{ghs_wrong_value:.2f}. Currency conversion was likely skipped!"
        )

        print(f"✓ Mixed currency factor: grand_total={totals_after['grand_total']:.2f} USD (correct)")

    def test_factor_with_multiply_operator(self, fresh_db):
        """
        Tests factor with exchange rate using multiply operator (*).
        Some exchange rates use multiplication (e.g., GHS * 0.0917 = USD).
        """
        db = fresh_db
        now = "2026-04-24"

        est = Estimate("Multiply Op Rate", "Client", 10.0, 5.0, currency="USD ($)", date=now)
        task = Task("Roofing")
        task.add_labor("Roofer", 8.0, 200.0, currency="GHS (₵)")  # 1600 GHS
        est.add_task(task)

        # Exchange rate: GHS * 0.1 = USD
        est.exchange_rates["GHS (₵)"] = {'rate': 0.1, 'date': now, 'operator': '*'}
        est.adjustment_factor = 1.0
        db.save_estimate(est)
        est_id = est.id

        # Apply factor
        db.bulk_update_estimate_factor(1.2)

        loaded = db.load_estimate_details(est_id)
        totals = loaded.calculate_totals()

        # 1600 GHS * 0.1 = 160 USD
        # 160 * 1.2 * 1.15 = 220.80
        expected = 160.0 * 1.2 * 1.15
        assert abs(totals['grand_total'] - expected) < 0.01, (
            f"Grand total {totals['grand_total']:.2f} != {expected:.2f}"
        )

        print(f"✓ Multiply operator: grand_total={totals['grand_total']:.2f} USD (correct)")


class TestFactorWithRealProjectData:
    """Tests using the real Atlantic Catering School project database."""

    def test_all_estimates_stay_in_project_currency(self, db):
        """
        Applies a factor change and verifies ALL estimates in the project
        maintain their grand_total in the correct project currency range.
        """
        # Get all estimate IDs
        rates = db.get_rates_data()
        assert len(rates) > 0, "Project must have estimates"

        # Compute correct totals BEFORE factor change (via model)
        pre_totals = {}
        for r in rates:
            est = db.load_estimate_details(r['id'])
            if est:
                pre_totals[r['id']] = est.calculate_totals()['grand_total']

        # Apply a different factor
        db.bulk_update_estimate_factor(1.1)

        # Verify each estimate
        for r in rates:
            est = db.load_estimate_details(r['id'])
            if not est or not est.tasks:
                continue  # Skip empty estimates

            totals = est.calculate_totals()
            grand = totals['grand_total']

            # The DB-stored grand_total should match calculate_totals()
            import sqlite3
            conn = sqlite3.connect(TEST_DB_PATH)
            c = conn.cursor()
            c.execute('SELECT grand_total FROM estimates WHERE id=?', (r['id'],))
            db_grand = c.fetchone()[0]
            conn.close()

            assert abs(grand - db_grand) < 0.01, (
                f"Estimate {r['rate_code']}: model grand_total={grand:.2f} != "
                f"DB grand_total={db_grand:.2f}. Stale net_total not recalculated!"
            )

        print(f"✓ All {len(rates)} estimates verified after factor update")

    def test_factor_roundtrip_consistency(self, db):
        """
        Applies factor 0.8, then 1.0 (reset), and verifies the grand_totals
        match the original calculate_totals() result.
        """
        # Get an estimate with resources
        est_orig = db.load_estimate_details(9)  # CONC1A
        if not est_orig:
            pytest.skip("Estimate 9 not found")

        # Store original factor
        orig_factor = est_orig.adjustment_factor

        # Apply factor 0.8
        db.bulk_update_estimate_factor(0.8)

        # Reset back to original
        db.bulk_update_estimate_factor(orig_factor)

        # Verify it matches original
        est_reset = db.load_estimate_details(9)
        grand_reset = est_reset.calculate_totals()['grand_total']

        # Recompute expected from scratch
        est_orig.adjustment_factor = orig_factor
        grand_expected = est_orig.calculate_totals()['grand_total']

        assert abs(grand_reset - grand_expected) < 0.01, (
            f"After roundtrip, grand_total={grand_reset:.2f} != expected {grand_expected:.2f}"
        )

        print(f"✓ Factor roundtrip: {orig_factor} -> 0.8 -> {orig_factor}, grand={grand_reset:.2f}")


class TestBulkMarginUpdate:
    """Tests that bulk_update_estimate_margins also correctly handles mixed currencies."""

    def test_margins_preserve_currency_conversion(self, fresh_db):
        """
        Verifies that updating margins does not lose currency conversion accuracy.
        """
        db = fresh_db
        now = "2026-04-24"

        est = Estimate("Margin Test Rate", "Client", 10.0, 5.0, currency="USD ($)", date=now)
        task = Task("Plumbing")
        task.add_material("Copper Pipe", 50.0, "m", 20.0, currency="GHS (₵)")  # 1000 GHS
        est.add_task(task)
        est.exchange_rates["GHS (₵)"] = {'rate': 10.0, 'date': now, 'operator': '/'}
        est.adjustment_factor = 1.0
        db.save_estimate(est)
        est_id = est.id

        # Change margins
        db.bulk_update_estimate_margins(15.0, 8.0)

        loaded = db.load_estimate_details(est_id)
        totals = loaded.calculate_totals()

        # 1000 GHS / 10 = 100 USD
        # 100 * 1.0 * (1 + 0.15 + 0.08) = 123.00
        expected = 100.0 * 1.0 * (1 + 0.15 + 0.08)
        assert abs(totals['grand_total'] - expected) < 0.01, (
            f"Grand total {totals['grand_total']:.2f} != {expected:.2f}. "
            f"Margin update may have used stale net_total."
        )

        print(f"✓ Margin update with currency conversion: grand={totals['grand_total']:.2f} USD")
