# PyTest/test_updater.py
import pytest
from updater import _parse_version, _is_newer, _find_installer_asset

def test_parse_version():
    assert _parse_version("1.0.0") == (1, 0, 0)
    assert _parse_version("v1.2.3") == (1, 2, 3)
    assert _parse_version("V2.10.5") == (2, 10, 5)
    assert _parse_version("invalid") == (0, 0, 0)

def test_is_newer():
    assert _is_newer("1.0.1", "1.0.0") is True
    assert _is_newer("v1.1.0", "1.0.9") is True
    assert _is_newer("2.0.0", "1.99.99") is True
    assert _is_newer("1.0.0", "1.0.0") is False
    assert _is_newer("v1.0.0", "1.0.0") is False
    assert _is_newer("0.9.9", "1.0.0") is False

def test_find_installer_asset():
    assets = [
        {"name": "source_code.tar.gz", "browser_download_url": "http://example.com/src.tar.gz"},
        {"name": "EstimatorPro_Setup.exe", "browser_download_url": "http://example.com/setup.exe", "size": 52428800},
        {"name": "readme.txt", "browser_download_url": "http://example.com/readme.txt"}
    ]
    installer = _find_installer_asset(assets)
    assert installer is not None
    assert installer["name"] == "EstimatorPro_Setup.exe"
    assert installer["browser_download_url"] == "http://example.com/setup.exe"

def test_find_installer_asset_prioritizes_setup():
    # If both raw binary and setup installer exist, setup should be selected first
    assets = [
        {"name": "Estimator_Pro.exe", "browser_download_url": "http://example.com/Estimator_Pro.exe", "size": 50000000},
        {"name": "EstimatorPro_Setup.exe", "browser_download_url": "http://example.com/EstimatorPro_Setup.exe", "size": 52428800},
    ]
    installer = _find_installer_asset(assets)
    assert installer is not None
    assert installer["name"] == "EstimatorPro_Setup.exe"

def test_find_installer_asset_none():
    assets = [
        {"name": "source_code.tar.gz", "browser_download_url": "http://example.com/src.tar.gz"}
    ]
    assert _find_installer_asset(assets) is None

def test_update_checker_404_emits_up_to_date(qapp, monkeypatch):
    from unittest.mock import MagicMock
    import urllib.request
    from urllib.error import HTTPError
    from updater import UpdateChecker

    def mock_urlopen(*args, **kwargs):
        raise HTTPError("https://api.github.com/...", 404, "Not Found", {}, None)

    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

    checker = UpdateChecker()
    up_to_date_called = []
    failed_called = []

    checker.up_to_date.connect(lambda: up_to_date_called.append(True))
    checker.check_failed.connect(lambda err: failed_called.append(err))

    checker.run()

    assert len(up_to_date_called) == 1
    assert len(failed_called) == 0

