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

def test_find_installer_asset_none():
    assets = [
        {"name": "source_code.tar.gz", "browser_download_url": "http://example.com/src.tar.gz"}
    ]
    assert _find_installer_asset(assets) is None
