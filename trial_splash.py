# trial_splash.py
import sys
import os
import random
import hashlib
from datetime import datetime, timedelta, date

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QProgressBar, QComboBox, QFrame, QGraphicsDropShadowEffect, QMessageBox,
    QLineEdit, QInputDialog
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QLinearGradient, QPalette, QShortcut, QKeySequence

from database import DatabaseManager

SECRET_SALT = "EstimatorProPremiumAccess2026"

def generate_license_signature():
    """Generates the secure SHA-256 license signature for Paid status."""
    return hashlib.sha256(f"PAID_LICENSE_AUTHORIZED_{SECRET_SALT}".encode('utf-8')).hexdigest()

def is_license_valid(sig):
    """Checks if the stored license signature matches the expected signature."""
    if not sig:
        return False
    return sig == generate_license_signature()


class CheckoutDialog(QDialog):
    """A beautiful simulated checkout window for activating the Green Pass."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Upgrade to Green Pass")
        self.resize(440, 280)
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

        title = QLabel("⭐ Upgrade to Permanent Green Pass")
        title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        desc = QLabel(
            "Your Trial Pass is expiring. Upgrading gives you:\n\n"
            "  ✅  Guaranteed instant launch — every single time\n"
            "  ✅  No probabilistic gating, ever again\n"
            "  ✅  Full access to all Estimator Pro features\n\n"
            "This will activate a secure cryptographic license on this machine."
        )
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignmentFlag.AlignLeft)
        desc.setStyleSheet("color: #a1a1aa; font-size: 10pt; line-height: 1.6;")
        layout.addWidget(desc)

        layout.addStretch()

        btn_layout = QHBoxLayout()
        self.cancel_btn = QPushButton("Not Now")
        self.cancel_btn.setStyleSheet("""
            background-color: #3f3f46;
            color: #e4e4e7;
        """)
        self.cancel_btn.clicked.connect(self.reject)

        self.pay_btn = QPushButton("✅ Activate Green Pass (Simulation)")
        self.pay_btn.setStyleSheet("""
            background-color: #10b981;
            color: #000000;
            font-weight: bold;
        """)
        self.pay_btn.clicked.connect(self.process_purchase)

        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.pay_btn)
        layout.addLayout(btn_layout)

    def process_purchase(self):
        try:
            db = DatabaseManager()
            sig = generate_license_signature()
            db.set_setting("license_status", sig)
            QMessageBox.information(
                self, "Green Pass Activated!",
                "🎉 Welcome to the full Estimator Pro experience!\n\n"
                "Your permanent Green Pass is now active.\n"
                "Guaranteed instant access — every time you launch."
            )
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to activate license: {e}")
            self.reject()


class TrialSplashDialog(QDialog):
    """The main gating splash screen with probabilistic loading and developer controls."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.db = DatabaseManager()
        self.roll_performed = False
        self.roll_success = False
        self.near_miss_phase = False  # For near-miss animation in Yellow/Red
        self.near_miss_val = 0

        # Override state for developer toolbar
        self.state_override = "Auto"

        # Initialise installation data
        self.init_trial_data()

        # Load & increment session attempt counter
        self._load_attempt_counter()

        # Window settings for borderless translucent view
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Set up layouts
        self.setup_ui()
        self.apply_theme()
        self.update_window_size()

        # Loading animation timer
        self.progress_val = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_progress)
        self.timer.start(100)  # Tick every 100ms (loads over exactly 10 seconds)

    def init_trial_data(self):
        """Initialise or migrate install_date, license_status, and last_run_date settings."""
        # 1. License status
        self.license_sig = self.db.get_setting("license_status")
        self.is_premium = is_license_valid(self.license_sig)

        # 2. Install date
        install_date_str = self.db.get_setting("install_date")
        if not install_date_str:
            install_date_str = date.today().strftime("%Y-%m-%d")
            self.db.set_setting("install_date", install_date_str)

        try:
            self.install_date = datetime.strptime(install_date_str, "%Y-%m-%d").date()
        except Exception:
            self.install_date = date.today()
            self.db.set_setting("install_date", self.install_date.strftime("%Y-%m-%d"))

        # 3. Last run date (Clock Tamper Protection)
        last_run_str = self.db.get_setting("last_run_date")
        if last_run_str:
            try:
                self.last_run_date = datetime.strptime(last_run_str, "%Y-%m-%d").date()
            except Exception:
                self.last_run_date = date.today()
        else:
            self.last_run_date = date.today()
            self.db.set_setting("last_run_date", date.today().strftime("%Y-%m-%d"))

        # Clock-tampering check (if time went backward by > 24 hours)
        self.is_clock_tampered = False
        if date.today() < (self.last_run_date - timedelta(days=1)):
            self.is_clock_tampered = True

        # Update last run date (if clock isn't backdated or if it's progressing normally)
        if not self.is_clock_tampered:
            self.db.set_setting("last_run_date", date.today().strftime("%Y-%m-%d"))

    def _load_attempt_counter(self):
        """Loads and increments the launch attempt counter from the DB for Yellow/Red/Black lanes."""
        try:
            val = self.db.get_setting("trial_attempt_count")
            self.attempt_count = int(val) + 1 if val and val.isdigit() else 1
            self.db.set_setting("trial_attempt_count", str(self.attempt_count))
        except Exception:
            self.attempt_count = 1

    def calculate_state(self):
        """Calculates the active trial stage and its associated probability."""
        if self.is_premium:
            return "Green", 1.0, "Permanent Green Pass — Full Access"

        if self.is_clock_tampered:
            return "Black", 0.01, "Trial Pass Restricted — System clock rollback detected"

        # Calculate days since install
        days = (date.today() - self.install_date).days

        # Check for emergency bypass date
        emergency_date_str = self.db.get_setting("emergency_bypass_date")
        if emergency_date_str:
            try:
                bypass_date = datetime.strptime(emergency_date_str, "%Y-%m-%d").date()
                if date.today() <= bypass_date:
                    return "Green", 1.0, f"Emergency Pass Active — Expires {bypass_date.strftime('%d %b %Y')}"
            except Exception:
                pass

        days_remaining = max(0, 30 - days)
        if days <= 30:
            return "Green", 1.0, f"Trial Pass — Day {max(1, days)} of 30  ({days_remaining} day{'s' if days_remaining != 1 else ''} remaining)"
        elif days <= 40:
            return "Yellow", 0.30, f"Trial Pass — Yellow Zone  (Day {days} — launch is no longer guaranteed)"
        elif days <= 45:
            return "Red", 0.10, f"Trial Pass — Red Zone  (Day {days} — only 1-in-10 launches succeed)"
        else:
            return "Black", 0.01, "Trial Pass — Expired  (launches are now extremely rare)"

    def get_current_stage(self):
        """Resolves the stage, taking developer overrides into account."""
        if self.state_override == "Force Green":
            return "Green", 1.0, "[DEV] Trial Pass — Green Zone forced"
        elif self.state_override == "Force Yellow":
            return "Yellow", 0.30, "[DEV] Trial Pass — Yellow Zone forced (30% launch rate)"
        elif self.state_override == "Force Red":
            return "Red", 0.10, "[DEV] Trial Pass — Red Zone forced (10% launch rate)"
        elif self.state_override == "Force Black":
            return "Black", 0.01, "[DEV] Trial Pass — Black Zone forced (1% launch rate)"

        return self.calculate_state()

    def setup_ui(self):
        # Create a container frame with a rounded card style
        self.card = QFrame(self)
        self.card.setObjectName("SplashCard")
        
        # Shadow effect
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 150))
        shadow.setOffset(0, 5)
        self.card.setGraphicsEffect(shadow)

        # Main layouts
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(25, 25, 25, 25)
        card_layout.setSpacing(15)

        # Header Info
        header_layout = QHBoxLayout()
        self.title_lbl = QLabel("ESTIMATOR PRO")
        self.title_lbl.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        self.title_lbl.setStyleSheet("color: white; letter-spacing: 2px;")
        
        self.status_pill = QLabel("TRIAL ACTIVE")
        self.status_pill.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        self.status_pill.setStyleSheet("""
            background-color: rgba(255, 255, 255, 0.15);
            color: #d1d5db;
            border-radius: 4px;
            padding: 3px 8px;
        """)
        
        header_layout.addWidget(self.title_lbl)
        header_layout.addStretch()
        header_layout.addWidget(self.status_pill)
        card_layout.addLayout(header_layout)

        # Main Status Graphic & Messages
        self.info_lbl = QLabel("Initializing Estimator Pro...")
        self.info_lbl.setFont(QFont("Segoe UI", 10))
        self.info_lbl.setStyleSheet("color: #e4e4e7;")
        self.info_lbl.setWordWrap(True)
        card_layout.addWidget(self.info_lbl)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setTextVisible(False)
        card_layout.addWidget(self.progress_bar)

        # Interaction buttons container (hidden during loading, shown on failure)
        self.btn_widget = QFrame()
        btn_layout = QVBoxLayout(self.btn_widget)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(8)

        # Attempt counter label (shown in Yellow/Red/Black on failure)
        self.attempt_lbl = QLabel("")
        self.attempt_lbl.setFont(QFont("Segoe UI", 8))
        self.attempt_lbl.setStyleSheet("color: #71717a; margin-bottom: 2px;")
        self.attempt_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        btn_layout.addWidget(self.attempt_lbl)

        self.retry_btn = QPushButton("🔄 Try Again")
        self.retry_btn.clicked.connect(self.restart_app)
        btn_layout.addWidget(self.retry_btn)

        self.emergency_btn = QPushButton("🆘 Activate 24-Hour Emergency Pass")
        self.emergency_btn.clicked.connect(self.request_emergency_extension)
        btn_layout.addWidget(self.emergency_btn)

        self.buy_btn = QPushButton("⭐ Upgrade — Get Guaranteed Access")
        self.buy_btn.clicked.connect(self.open_upgrade)
        btn_layout.addWidget(self.buy_btn)

        card_layout.addWidget(self.btn_widget)
        self.btn_widget.hide()  # Hidden initially

        card_layout.addStretch()

        # Hidden shortcut to toggle Developer Override Section
        self.dev_shortcut = QShortcut(QKeySequence("Ctrl+Shift+Alt+D"), self)
        self.dev_shortcut.activated.connect(self.toggle_dev_panel)

        self.dev_panel = QFrame()
        dev_layout = QVBoxLayout(self.dev_panel)
        dev_layout.setContentsMargins(10, 5, 10, 5)
        dev_layout.setSpacing(6)
        self.dev_panel.setStyleSheet("""
            QFrame {
                background-color: rgba(0, 0, 0, 0.2);
                border-radius: 6px;
            }
            QLabel {
                color: #a1a1aa;
                font-size: 8pt;
            }
            QPushButton {
                background-color: #3f3f46;
                color: #e4e4e7;
                font-size: 8pt;
                padding: 4px;
            }
            QComboBox {
                background-color: #27272a;
                color: #e4e4e7;
                border: 1px solid #3f3f46;
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 8pt;
            }
            QComboBox QAbstractItemView {
                background-color: #18181b;
                color: #e4e4e7;
                border: 1px solid #3f3f46;
                selection-background-color: #3f3f46;
                selection-color: #ffffff;
            }
        """)

        # Override dropdown
        override_layout = QHBoxLayout()
        override_lbl = QLabel("Simulate Stage:")
        self.override_combo = QComboBox()
        self.override_combo.addItems(["Auto", "Force Green", "Force Yellow", "Force Red", "Force Black"])
        self.override_combo.currentTextChanged.connect(self.on_override_changed)
        override_layout.addWidget(override_lbl)
        override_layout.addWidget(self.override_combo)
        dev_layout.addLayout(override_layout)

        # Quick date buttons
        date_btn_layout = QHBoxLayout()
        self.btn_day35 = QPushButton("Day -35 (Yellow)")
        self.btn_day35.clicked.connect(lambda: self.sim_install_date(-35))
        self.btn_day42 = QPushButton("Day -42 (Red)")
        self.btn_day42.clicked.connect(lambda: self.sim_install_date(-42))
        self.btn_day50 = QPushButton("Day -50 (Black)")
        self.btn_day50.clicked.connect(lambda: self.sim_install_date(-50))
        date_btn_layout.addWidget(self.btn_day35)
        date_btn_layout.addWidget(self.btn_day42)
        date_btn_layout.addWidget(self.btn_day50)
        dev_layout.addLayout(date_btn_layout)

        # Reset button
        self.reset_btn = QPushButton("Reset Trial Settings")
        self.reset_btn.clicked.connect(self.reset_trial_settings)
        dev_layout.addWidget(self.reset_btn)

        card_layout.addWidget(self.dev_panel)
        self.dev_panel.hide() # Collapsed initially

        # Outer dialog layout to center card
        dialog_layout = QVBoxLayout(self)
        dialog_layout.setContentsMargins(0, 0, 0, 0)
        dialog_layout.addWidget(self.card)

    def apply_theme(self):
        """Applies stylesheet gradients, typography, and button layout based on active stage."""
        stage, prob, desc = self.get_current_stage()

        # Update pill with honest Trial Pass framing
        pill_labels = {
            "Green": "✅ TRIAL PASS",
            "Yellow": "🟡 YELLOW ZONE",
            "Red": "🔴 RED ZONE",
            "Black": "⬛ TRIAL EXPIRED",
        }
        self.status_pill.setText(pill_labels.get(stage, f"{stage.upper()} ZONE"))

        # CURATED GRADIENTS matching the status codes
        if stage == "Green":
            gradient = "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0a1f18, stop:1 #111827)"
            accent = "#10b981" # Emerald
            pill_style = "background-color: rgba(16, 185, 129, 0.2); color: #10b981; border: 1px solid #10b981;"
        elif stage == "Yellow":
            gradient = "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #2b1f02, stop:1 #111827)"
            accent = "#f59e0b" # Amber
            pill_style = "background-color: rgba(245, 158, 11, 0.2); color: #f59e0b; border: 1px solid #f59e0b;"
        elif stage == "Red":
            gradient = "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #3b0712, stop:1 #111827)"
            accent = "#f43f5e" # Crimson Rose
            pill_style = "background-color: rgba(244, 63, 94, 0.2); color: #f43f5e; border: 1px solid #f43f5e;"
        else: # Black
            gradient = "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #18181b, stop:1 #09090b)"
            accent = "#a21caf" # Dark violet/fuchsia highlight
            pill_style = "background-color: rgba(24, 24, 27, 0.8); color: #a1a1aa; border: 1px solid #3f3f46;"

        # Apply Card style
        self.card.setStyleSheet(f"""
            QFrame#SplashCard {{
                background: {gradient};
                border: 2px solid {accent};
                border-radius: 12px;
            }}
        """)
        self.status_pill.setStyleSheet(pill_style)

        # Style Progress Bar
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: rgba(255, 255, 255, 0.1);
                border: none;
                border-radius: 3px;
            }}
            QProgressBar::chunk {{
                background-color: {accent};
                border-radius: 3px;
            }}
        """)

        # Style Gating failure CTAs
        text_color = "#000000" if stage == "Yellow" else "#ffffff"
        self.buy_btn.setStyleSheet(f"""
            background-color: {accent};
            color: {text_color};
            font-weight: bold;
            padding: 10px;
            border-radius: 6px;
            border: none;
            font-size: 10pt;
        """)

        self.retry_btn.setStyleSheet("""
            background-color: #27272a;
            color: #e4e4e7;
            padding: 8px;
            border-radius: 6px;
            border: 1px solid #3f3f46;
        """)

        # Emergency Pass button: only visible in Black zone
        if stage == "Black":
            self.emergency_btn.show()
            emergency_used = self.db.get_setting("emergency_bypass_date") is not None
            if emergency_used:
                self.emergency_btn.setText("🆘 Emergency Pass (Already Used — Cannot Renew)")
                self.emergency_btn.setEnabled(False)
                self.emergency_btn.setStyleSheet("""
                    background-color: #18181b;
                    color: #52525b;
                    padding: 8px;
                    border-radius: 6px;
                    border: 1px solid #27272a;
                """)
            else:
                self.emergency_btn.setText("🆘 Activate 24-Hour Emergency Pass (One-Time)")
                self.emergency_btn.setEnabled(True)
                self.emergency_btn.setStyleSheet("""
                    background-color: #451a03;
                    color: #fdba74;
                    padding: 8px;
                    border-radius: 6px;
                    border: 1px solid #78350f;
                """)
        else:
            self.emergency_btn.hide()

    def update_progress(self):
        """Simulates progress bar animation and runs probability check at 100%."""
        if self.near_miss_phase:
            # Near-miss animation: quickly fill to near-miss value then drain
            self.near_miss_val -= 3
            self.progress_bar.setValue(max(0, self.near_miss_val))
            if self.near_miss_val <= 0:
                self.near_miss_phase = False
                self.timer.stop()
                self._show_failure_state()
            return

        if self.progress_val < 100:
            self.progress_val += 1
            self.progress_bar.setValue(self.progress_val)
            stage, prob, desc = self.get_current_stage()
            # Stage-specific loading copy
            loading_msgs = {
                "Green": [
                    "Loading cost rate databases...",
                    "Preparing your workspace...",
                    "Applying your Trial Pass...",
                ],
                "Yellow": [
                    "Checking Trial Pass status...",
                    "Trial Pass — Yellow Zone active...",
                    "Probabilistic launch in progress...",
                ],
                "Red": [
                    "Checking Trial Pass status...",
                    "Trial Pass — Red Zone critical...",
                    "Launch is now rare — attempting...",
                ],
                "Black": [
                    "Trial Pass expired...",
                    "Searching for an available launch slot...",
                    "Almost never succeeds at this stage...",
                ],
            }
            msgs = loading_msgs.get(stage, ["Loading..."])
            msg_idx = min(int(self.progress_val / 34), len(msgs) - 1)
            self.info_lbl.setText(f"{desc}\n{msgs[msg_idx]}")
        else:
            self.timer.stop()
            self.perform_roll()

    def perform_roll(self):
        """Performs the probabilistic launch roll with near-miss animation for Yellow/Red."""
        self.roll_performed = True
        stage, prob, desc = self.get_current_stage()

        roll = random.random()
        self.roll_success = roll < prob

        if self.roll_success:
            # Reset attempt counter on success
            self.db.set_setting("trial_attempt_count", "0")
            self.info_lbl.setText(
                f"✅ Launch successful!\nWelcome back to Estimator Pro.  ({stage} Pass)"
            )
            QTimer.singleShot(900, self.accept)
        else:
            # Near-miss: in Yellow/Red, ~40% of failures show a near-miss animation
            if stage in ("Yellow", "Red") and random.random() < 0.40:
                near_miss_peak = random.randint(72, 91)
                self.progress_bar.setValue(near_miss_peak)
                self.info_lbl.setText(
                    f"⏳ {int(near_miss_peak)}% loaded... launch slot lost.\n"
                    f"Trial Pass — {stage} Zone  (launch was not guaranteed)"
                )
                self.near_miss_phase = True
                self.near_miss_val = near_miss_peak
                self.timer.start(40)  # Drain animation
            else:
                self._show_failure_state()

    def _show_failure_state(self):
        """Displays the stage-appropriate failure message and CTA buttons."""
        stage, prob, desc = self.get_current_stage()

        failure_msgs = {
            "Yellow": (
                "🟡 Launch attempt did not succeed this time.\n"
                "Your Trial Pass is in the Yellow Zone — launches are no longer guaranteed.\n"
                "Upgrade for instant, guaranteed access every time."
            ),
            "Red": (
                "🔴 Launch failed — Red Zone active.\n"
                "Trial launches are now rare at this stage. Every day you wait is a bid you can't price.\n"
                "Secure your access now before your next urgent deadline."
            ),
            "Black": (
                "⬛ Trial Pass Expired.\n"
                "Launches are almost never successful at this stage. Are you in the middle of an urgent bid?\n"
                "Use your one-time Emergency Pass, or upgrade for permanent access."
            ),
        }
        self.info_lbl.setText(
            failure_msgs.get(stage,
                f"⚠️ Trial Pass — {stage} Zone.\nThis launch was not successful. Try again or upgrade."
            )
        )

        # Update attempt counter label
        if stage in ("Yellow", "Red", "Black") and self.attempt_count > 1:
            self.attempt_lbl.setText(
                f"You've attempted {self.attempt_count} launch{'es' if self.attempt_count != 1 else ''} this trial. "
                f"Upgrade once — launch forever."
            )
            self.attempt_lbl.show()
        else:
            self.attempt_lbl.hide()

        self.btn_widget.show()
        self.update_window_size()

    def restart_app(self):
        """Quits the current app session so the user can relaunch and roll again."""
        self.reject()

    def request_emergency_extension(self):
        """Grants a one-time 24-hour emergency launch pass."""
        reply = QMessageBox.question(
            self, "Activate Emergency Pass",
            "This is a one-time Emergency Pass for urgent, time-critical bids.\n\n"
            "It will restore full launch access for 24 hours and cannot be renewed.\n\n"
            "Activate your Emergency Pass now?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                bypass_expire = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
                self.db.set_setting("emergency_bypass_date", bypass_expire)
                QMessageBox.information(
                    self, "Emergency Pass Active",
                    f"✅ Emergency Pass Activated!\n\n"
                    f"You have full access until {bypass_expire}.\n\n"
                    f"Remember: this pass is one-time only and cannot be extended.\n"
                    f"Upgrade to a permanent Green Pass to never face this again."
                )
                self.accept()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to activate Emergency Pass: {e}")

    def open_upgrade(self):
        """Opens simulated checkout flow."""
        chk = CheckoutDialog(self)
        if chk.exec() == QDialog.DialogCode.Accepted:
            # Upgrade occurred, reload install data and accept splash dialog
            self.init_trial_data()
            self.accept()

    def update_window_size(self):
        """Sets fixed width and computes height dynamically based on visible components to prevent Windows resize warnings."""
        self.setFixedWidth(520)
        h = 210
        if self.btn_widget.isVisible():
            if self.emergency_btn.isVisible():
                h += 130
            else:
                h += 95
        if self.dev_panel.isVisible():
            h += 130
        self.setFixedHeight(h)

    # COLLAPSIBLE DEV OVERRIDES PANEL
    def toggle_dev_panel(self):
        if self.dev_panel.isVisible():
            self.dev_panel.hide()
            self.update_window_size()
        else:
            # Prompt for password via QInputDialog
            password, ok = QInputDialog.getText(
                self, "Developer Access", "Enter Developer Password:",
                QLineEdit.EchoMode.Password
            )
            if ok:
                # SHA-256 of '191986kil'
                expected_hash = "60bb26c3adbbdc5c7e607007f33cbca5e0c8b1365844758d7ad41d28f15606d7"
                entered_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()
                
                if entered_hash == expected_hash:
                    self.dev_panel.show()
                    self.update_window_size()
                else:
                    QMessageBox.warning(self, "Access Denied", "Incorrect developer password.")

    def on_override_changed(self, val):
        self.state_override = val
        self.apply_theme()
        # Reset progress bar and run roll again
        self.progress_val = 0
        self.btn_widget.hide()
        self.update_window_size()
        self.timer.start(100)

    def sim_install_date(self, offset_days):
        target_date = (date.today() + timedelta(days=offset_days)).strftime("%Y-%m-%d")
        self.db.set_setting("install_date", target_date)
        # Clear emergency dates to prevent overriding simulation date checks
        with self.db.Session() as s:
            from orm_models import Setting
            s.query(Setting).filter(Setting.key == 'emergency_bypass_date').delete()
            s.commit()

        self.init_trial_data()
        self.apply_theme()
        self.progress_val = 0
        self.btn_widget.hide()
        self.update_window_size()
        self.timer.start(100)

    def reset_trial_settings(self):
        with self.db.Session() as s:
            from orm_models import Setting
            s.query(Setting).filter(Setting.key.in_(['install_date', 'license_status', 'emergency_bypass_date', 'last_run_date', 'trial_attempt_count'])).delete()
            s.commit()

        self.override_combo.setCurrentText("Auto")
        self.init_trial_data()
        self.apply_theme()
        self.progress_val = 0
        self.btn_widget.hide()
        self.update_window_size()
        self.timer.start(100)

    # EVENT LOOP CLEANUP
    def closeEvent(self, event):
        self.timer.stop()
        super().closeEvent(event)

    def reject(self):
        self.timer.stop()
        super().reject()

    def accept(self):
        self.timer.stop()
        super().accept()
