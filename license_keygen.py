# license_keygen.py
# ═══════════════════════════════════════════════════════════════════════
# PRIVATE — Never include in the distributed app package.
# This script generates valid timed HMAC-SHA256 license keys for
# Estimator Pro.  Keep it secure — anyone with this file can generate
# unlimited valid keys.
# ═══════════════════════════════════════════════════════════════════════
import hmac
import hashlib
from datetime import date, timedelta

SECRET = "EstimatorProKeySecret2026"  # Must match SECRET_KEY in trial_splash.py


def make_key(days: int = 30) -> str:
    """Generate a timed HMAC-SHA256 license key valid for `days` days from today."""
    expiry = (date.today() + timedelta(days=days)).strftime("%Y%m%d")
    sig = hmac.new(SECRET.encode(), expiry.encode(), hashlib.sha256).hexdigest()[:8].upper()
    return f"EPRO-{expiry}-{sig}"


if __name__ == "__main__":
    print("═" * 48)
    print("  Estimator Pro — License Key Generator")
    print("═" * 48)
    print()
    print(f"  30-day  key:  {make_key(30)}")
    print(f"  90-day  key:  {make_key(90)}")
    print(f"  365-day key:  {make_key(365)}")
    print()
    print("═" * 48)
