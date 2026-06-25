"""
Unit tests for the HMAC-SHA256 timed license key system.

Tests cover:
  - validate_license_key() — all 4 return states (valid, format, signature, expired)
  - calculate_state() — Green for unexpired timed license
  - calculate_state() — fall-through to trial days when license is expired
  - Key format edge cases
"""
import sys
import os
import hashlib
import hmac
import pytest
from datetime import date, timedelta, datetime
from unittest.mock import patch, MagicMock

# Add project root to system path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from trial_splash import validate_license_key, SECRET_KEY


# ─── Helper: generate a known-good key for a given expiry date ───

def _make_key_for_date(expiry_date: date) -> str:
    """Generate a valid EPRO key for an arbitrary expiry date."""
    expiry_str = expiry_date.strftime("%Y%m%d")
    sig = hmac.new(SECRET_KEY.encode(), expiry_str.encode(), hashlib.sha256).hexdigest()[:8].upper()
    return f"EPRO-{expiry_str}-{sig}"


# ═══════════════════════════════════════════════════════════════════════
# Tests for validate_license_key()
# ═══════════════════════════════════════════════════════════════════════

class TestValidateLicenseKey:
    """Tests the standalone validate_license_key() function."""

    def test_valid_key_not_expired(self):
        """A correctly signed key with a future expiry returns (True, expiry_date)."""
        future_date = date.today() + timedelta(days=30)
        key = _make_key_for_date(future_date)
        valid, result = validate_license_key(key)
        assert valid is True
        assert result == future_date

    def test_valid_key_expiring_today(self):
        """A key expiring today is still valid (days_left >= 0)."""
        today = date.today()
        key = _make_key_for_date(today)
        valid, result = validate_license_key(key)
        assert valid is True
        assert result == today

    def test_expired_key(self):
        """A correctly signed key with a past expiry returns (False, 'expired')."""
        past_date = date.today() - timedelta(days=1)
        key = _make_key_for_date(past_date)
        valid, reason = validate_license_key(key)
        assert valid is False
        assert reason == "expired"

    def test_bad_signature(self):
        """A key with a tampered signature returns (False, 'signature')."""
        future_date = date.today() + timedelta(days=30)
        key = _make_key_for_date(future_date)
        # Corrupt the last character of the signature
        parts = key.split("-")
        parts[2] = parts[2][:-1] + ("A" if parts[2][-1] != "A" else "B")
        bad_key = "-".join(parts)
        valid, reason = validate_license_key(bad_key)
        assert valid is False
        assert reason == "signature"

    def test_wrong_prefix(self):
        """A key with a wrong product prefix returns (False, 'format')."""
        valid, reason = validate_license_key("XPRO-20260724-A3F7C9D1")
        assert valid is False
        assert reason == "format"

    def test_too_few_parts(self):
        """A key with too few dashes returns (False, 'format')."""
        valid, reason = validate_license_key("EPRO-20260724")
        assert valid is False
        assert reason == "format"

    def test_too_many_parts(self):
        """A key with extra dashes returns (False, 'format')."""
        valid, reason = validate_license_key("EPRO-2026-0724-A3F7C9D1")
        assert valid is False
        assert reason == "format"

    def test_short_date(self):
        """A key with a short date field returns (False, 'format')."""
        valid, reason = validate_license_key("EPRO-2026072-A3F7C9D1")
        assert valid is False
        assert reason == "format"

    def test_short_signature(self):
        """A key with a short signature returns (False, 'format')."""
        valid, reason = validate_license_key("EPRO-20260724-A3F7C9")
        assert valid is False
        assert reason == "format"

    def test_empty_string(self):
        """An empty string returns (False, 'format')."""
        valid, reason = validate_license_key("")
        assert valid is False
        assert reason == "format"

    def test_case_insensitive(self):
        """Keys are case-insensitive — lowercase input should still validate."""
        future_date = date.today() + timedelta(days=30)
        key = _make_key_for_date(future_date).lower()
        valid, result = validate_license_key(key)
        assert valid is True
        assert result == future_date

    def test_whitespace_stripped(self):
        """Leading/trailing whitespace should be stripped before validation."""
        future_date = date.today() + timedelta(days=30)
        key = "  " + _make_key_for_date(future_date) + "  "
        valid, result = validate_license_key(key)
        assert valid is True
        assert result == future_date


# ═══════════════════════════════════════════════════════════════════════
# Tests for calculate_state() — timed license paths
# ═══════════════════════════════════════════════════════════════════════

class TestCalculateStateLicense:
    """Tests the timed-license paths in TrialSplashDialog.calculate_state().

    These tests mock DatabaseManager to avoid needing a real DB or QApplication.
    """

    def _make_mock_dialog(self, license_expiry=None, install_days_ago=0,
                          is_premium=False, is_clock_tampered=False,
                          emergency_bypass_date=None):
        """Create a mock TrialSplashDialog with injectable state."""
        mock_dialog = MagicMock()
        mock_dialog.is_premium = is_premium
        mock_dialog.is_clock_tampered = is_clock_tampered
        mock_dialog.install_date = date.today() - timedelta(days=install_days_ago)

        def mock_get_setting(key):
            if key == "license_expiry":
                return license_expiry
            if key == "emergency_bypass_date":
                return emergency_bypass_date
            return None

        mock_dialog.db = MagicMock()
        mock_dialog.db.get_setting = mock_get_setting

        # Bind the real calculate_state method to our mock
        from trial_splash import TrialSplashDialog
        mock_dialog.calculate_state = TrialSplashDialog.calculate_state.__get__(mock_dialog)
        return mock_dialog

    def test_unexpired_license_returns_green(self):
        """An active timed license should return Green with 'Licensed' in desc."""
        future = date.today() + timedelta(days=60)
        dialog = self._make_mock_dialog(
            license_expiry=future.strftime("%Y%m%d"),
            install_days_ago=50  # would be Black zone without license
        )
        stage, prob, desc = dialog.calculate_state()
        assert stage == "Green"
        assert prob == 1.0
        assert "Licensed" in desc

    def test_expired_license_falls_through_to_trial(self):
        """An expired timed license should fall through to trial-day logic."""
        yesterday = date.today() - timedelta(days=1)
        dialog = self._make_mock_dialog(
            license_expiry=yesterday.strftime("%Y%m%d"),
            install_days_ago=35  # Yellow zone
        )
        stage, prob, desc = dialog.calculate_state()
        assert stage == "Yellow"
        assert prob == 0.30
        assert "Yellow Zone" in desc

    def test_expired_license_black_zone(self):
        """An expired license with install 50 days ago should reach Black."""
        yesterday = date.today() - timedelta(days=1)
        dialog = self._make_mock_dialog(
            license_expiry=yesterday.strftime("%Y%m%d"),
            install_days_ago=50  # Black zone
        )
        stage, prob, desc = dialog.calculate_state()
        assert stage == "Black"
        assert prob == 0.01

    def test_permanent_pass_takes_priority_over_license(self):
        """is_premium should take priority over any timed license."""
        dialog = self._make_mock_dialog(
            license_expiry=(date.today() + timedelta(days=30)).strftime("%Y%m%d"),
            is_premium=True
        )
        stage, prob, desc = dialog.calculate_state()
        assert stage == "Green"
        assert "Green Pass" in desc

    def test_license_expiring_today_is_still_green(self):
        """A license expiring today (days_left == 0) should still be Green."""
        today = date.today()
        dialog = self._make_mock_dialog(
            license_expiry=today.strftime("%Y%m%d"),
            install_days_ago=50  # would be Black without license
        )
        stage, prob, desc = dialog.calculate_state()
        assert stage == "Green"
        assert "Licensed" in desc
        assert "0 days left" in desc

    def test_no_license_fresh_install_is_green_trial(self):
        """No license with a fresh install should be Green trial."""
        dialog = self._make_mock_dialog(
            license_expiry=None,
            install_days_ago=5
        )
        stage, prob, desc = dialog.calculate_state()
        assert stage == "Green"
        assert "Trial Pass" in desc
