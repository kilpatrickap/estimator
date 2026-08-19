# PyTest/test_pboq_export.py
"""
Unit tests for PBOQ Excel exporter and color sanitization (pboq_export.py).
"""

import pytest
from pboq_export import _sanitize_color, PBOQExcelExporter


def test_sanitize_color_valid_hex():
    assert _sanitize_color("#FFFF00") == "FFFF00"
    assert _sanitize_color("ffff00") == "FFFF00"
    assert _sanitize_color("E3F2FD") == "E3F2FD"


def test_sanitize_color_3_digit_shorthand():
    assert _sanitize_color("#FFF") == "FFFFFF"
    assert _sanitize_color("f00") == "FF0000"
    assert _sanitize_color("#123") == "112233"


def test_sanitize_color_named_colors():
    assert _sanitize_color("yellow") == "FFFF00"
    assert _sanitize_color("red") == "FF0000"
    assert _sanitize_color("transparent") == "FFFFFF"


def test_sanitize_color_invalid_or_none():
    assert _sanitize_color(None, fallback="FFFFFF") == "FFFFFF"
    assert _sanitize_color("", fallback="000000") == "000000"
    assert _sanitize_color("invalid_color_xyz", fallback="FFFFFF") == "FFFFFF"
