# license_keygen.py
# ═══════════════════════════════════════════════════════════════════════
# PRIVATE — Never include in the distributed app package.
# This script generates valid timed HMAC-SHA256 license keys for
# Estimator Pro.  Keep it secure — anyone with this file can generate
# unlimited valid keys.
# ═══════════════════════════════════════════════════════════════════════
import sys
import hmac
import hashlib
from datetime import date, timedelta

from PyQt6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QLineEdit, QFrame, QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor

SECRET = "EstimatorProKeySecret2026"  # Must match SECRET_KEY in trial_splash.py


def make_key(days: int = 30) -> str:
    """Generate a timed HMAC-SHA256 license key valid for `days` days from today, with a unique serial."""
    import random
    import string
    expiry = (date.today() + timedelta(days=days)).strftime("%Y%m%d")
    serial = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    message = f"{serial}:{expiry}"
    sig = hmac.new(SECRET.encode(), message.encode(), hashlib.sha256).hexdigest()[:8].upper()
    return f"EPRO-{serial}-{expiry}-{sig}"


class KeygenDialog(QDialog):
    """A dark-themed GUI for generating Estimator Pro license keys."""

    DURATIONS = {
        "30 days": 30,
        "90 days": 90,
        "180 days": 180,
        "365 days (1 year)": 365,
    }

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Estimator Pro — Key Generator")
        self.resize(480, 340)
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e24;
                color: #e4e4e7;
                font-family: 'Segoe UI', sans-serif;
            }
            QLabel {
                color: #e4e4e7;
            }
            QPushButton {
                font-weight: bold;
                padding: 10px 15px;
                border-radius: 6px;
                border: none;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        # ── Title ──
        title = QLabel("🔑 Generate License Key")
        title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # ── Description ──
        desc = QLabel(
            "Generate a timed HMAC-SHA256 license key for a customer.\n\n"
            "  🔒  Keys are offline-verifiable — no server required\n"
            "  ⏱️  Each key encodes an expiry date and a signature"
        )
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignmentFlag.AlignLeft)
        desc.setStyleSheet("color: #a1a1aa; font-size: 10pt; line-height: 1.6;")
        layout.addWidget(desc)

        # ── Duration selector ──
        dur_label = QLabel("Select license duration:")
        dur_label.setStyleSheet("color: #d1d5db; font-size: 9pt; margin-top: 6px;")
        layout.addWidget(dur_label)

        self.duration_combo = QComboBox()
        self.duration_combo.addItems(self.DURATIONS.keys())
        self.duration_combo.setStyleSheet("""
            QComboBox {
                background-color: #27272a;
                color: #e4e4e7;
                border: 1px solid #3f3f46;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 11pt;
            }
            QComboBox:focus {
                border: 1px solid #10b981;
            }
            QComboBox QAbstractItemView {
                background-color: #18181b;
                color: #e4e4e7;
                border: 1px solid #3f3f46;
                selection-background-color: #3f3f46;
                selection-color: #ffffff;
            }
        """)
        layout.addWidget(self.duration_combo)

        # ── Generated key output ──
        key_label = QLabel("Generated key:")
        key_label.setStyleSheet("color: #d1d5db; font-size: 9pt; margin-top: 4px;")
        layout.addWidget(key_label)

        self.key_output = QLineEdit()
        self.key_output.setReadOnly(True)
        self.key_output.setPlaceholderText("Click Generate to create a key...")
        self.key_output.setStyleSheet("""
            QLineEdit {
                background-color: #27272a;
                color: #10b981;
                border: 1px solid #3f3f46;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 12pt;
                font-family: 'Consolas', 'Courier New', monospace;
                letter-spacing: 1px;
            }
        """)
        layout.addWidget(self.key_output)

        # ── Status label ──
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: #a1a1aa; font-size: 9pt; min-height: 20px;")
        layout.addWidget(self.status_label)

        layout.addStretch()

        # ── Buttons ──
        btn_layout = QHBoxLayout()

        self.copy_btn = QPushButton("📋 Copy to Clipboard")
        self.copy_btn.setStyleSheet("""
            background-color: #3f3f46;
            color: #e4e4e7;
        """)
        self.copy_btn.clicked.connect(self.copy_key)
        self.copy_btn.setEnabled(False)

        self.gen_btn = QPushButton("🔑 Generate")
        self.gen_btn.setStyleSheet("""
            background-color: #10b981;
            color: #000000;
            font-weight: bold;
        """)
        self.gen_btn.clicked.connect(self.generate_key)

        btn_layout.addWidget(self.copy_btn)
        btn_layout.addWidget(self.gen_btn)
        layout.addLayout(btn_layout)

    def generate_key(self):
        """Generate a key for the selected duration and display it."""
        label = self.duration_combo.currentText()
        days = self.DURATIONS[label]
        key = make_key(days)
        expiry = (date.today() + timedelta(days=days)).strftime("%d %b %Y")

        self.key_output.setText(key)
        self.copy_btn.setEnabled(True)
        self.status_label.setText(f"✅ Key generated — valid until {expiry}  ({days} days)")
        self.status_label.setStyleSheet("color: #10b981; font-size: 9pt; min-height: 20px;")

    def copy_key(self):
        """Copy the generated key to the system clipboard."""
        key = self.key_output.text()
        if key:
            QApplication.clipboard().setText(key)
            self.status_label.setText("📋 Key copied to clipboard!")
            self.status_label.setStyleSheet("color: #60a5fa; font-size: 9pt; min-height: 20px;")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    dialog = KeygenDialog()
    dialog.show()
    sys.exit(app.exec())
