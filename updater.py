# updater.py
"""
Remote auto-update system for Estimator Pro.

Checks the GitHub Releases API for kilpatrickap/estimator to determine if a
newer version is available.  When the user opts to download, it fetches the
Inno Setup installer (.exe asset) to a temp directory and launches it.

All network I/O runs in a background QThread so the UI is never blocked.
"""

import os
import re
import json
import tempfile
import subprocess
from urllib.request import urlopen, Request
from urllib.error import URLError

from PyQt6.QtCore import QThread, pyqtSignal, QObject, Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QFrame, QMessageBox, QApplication
)
from PyQt6.QtGui import QFont

from version import APP_VERSION

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
GITHUB_OWNER = "kilpatrickap"
GITHUB_REPO = "estimator"
RELEASES_URL = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"

# Accept header recommended by GitHub for their REST API
_GITHUB_HEADERS = {
    "Accept": "application/vnd.github+json",
    "User-Agent": f"EstimatorPro/{APP_VERSION}",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _parse_version(tag: str) -> tuple:
    """Extracts a (major, minor, patch) tuple from a tag like 'v1.2.3' or '1.2.3'."""
    match = re.match(r"v?(\d+)\.(\d+)\.(\d+)", tag.strip(), re.IGNORECASE)
    if not match:
        return (0, 0, 0)
    return tuple(int(x) for x in match.groups())


def _is_newer(remote_tag: str, local_version: str = APP_VERSION) -> bool:
    """Returns True when *remote_tag* represents a version higher than *local_version*."""
    return _parse_version(remote_tag) > _parse_version(local_version)


def _find_installer_asset(assets: list) -> dict | None:
    """Picks the first .exe asset from a GitHub release's asset list."""
    for asset in assets:
        name = asset.get("name", "")
        if name.lower().endswith(".exe"):
            return asset
    return None


# ---------------------------------------------------------------------------
# UpdateChecker — runs in a QThread
# ---------------------------------------------------------------------------
class UpdateChecker(QThread):
    """Background thread that queries GitHub Releases for the latest version.

    Signals
    -------
    update_available(version, download_url, changelog, asset_size)
        Emitted when a newer release exists.  *asset_size* is in bytes (0 if unknown).
    up_to_date()
        Emitted when the local version matches or exceeds the latest release.
    check_failed(error_message)
        Emitted on any network or parsing error so callers can handle gracefully.
    """

    update_available = pyqtSignal(str, str, str, int)  # version, url, changelog, size
    up_to_date = pyqtSignal()
    check_failed = pyqtSignal(str)

    def __init__(self, parent=None, skipped_version: str = ""):
        super().__init__(parent)
        self._skipped_version = skipped_version

    def run(self):
        try:
            req = Request(RELEASES_URL, headers=_GITHUB_HEADERS)
            with urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            tag = data.get("tag_name", "")
            if not _is_newer(tag):
                self.up_to_date.emit()
                return

            # Honour "skip this version"
            if self._skipped_version and tag == self._skipped_version:
                self.up_to_date.emit()
                return

            changelog = data.get("body", "") or "No release notes."
            asset = _find_installer_asset(data.get("assets", []))
            download_url = asset["browser_download_url"] if asset else ""
            asset_size = asset.get("size", 0) if asset else 0

            self.update_available.emit(tag, download_url, changelog, asset_size)

        except (URLError, TimeoutError, json.JSONDecodeError, KeyError) as exc:
            self.check_failed.emit(str(exc))
        except Exception as exc:
            self.check_failed.emit(f"Unexpected error: {exc}")


# ---------------------------------------------------------------------------
# UpdateDownloader — runs in a QThread
# ---------------------------------------------------------------------------
class UpdateDownloader(QThread):
    """Downloads a release asset and optionally launches the installer.

    Signals
    -------
    progress(percent, message)
        Emitted periodically with download progress (0-100).
    download_complete(file_path)
        Emitted when the download finishes successfully.
    download_failed(error_message)
        Emitted on any error during the download.
    """

    progress = pyqtSignal(int, str)          # percent, status text
    download_complete = pyqtSignal(str)       # local file path
    download_failed = pyqtSignal(str)

    def __init__(self, download_url: str, parent=None):
        super().__init__(parent)
        self._url = download_url

    def run(self):
        try:
            self.progress.emit(0, "Connecting...")
            req = Request(self._url, headers=_GITHUB_HEADERS)
            with urlopen(req, timeout=60) as resp:
                total = int(resp.headers.get("Content-Length", 0))
                # Write to a temp file that persists until the installer runs
                tmp_dir = tempfile.mkdtemp(prefix="estimator_update_")
                # Extract filename from URL or use a default
                filename = self._url.rsplit("/", 1)[-1] if "/" in self._url else "EstimatorPro_Setup.exe"
                dest = os.path.join(tmp_dir, filename)

                downloaded = 0
                chunk_size = 64 * 1024  # 64 KB
                with open(dest, "wb") as f:
                    while True:
                        chunk = resp.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total > 0:
                            pct = int(downloaded / total * 100)
                            mb_done = downloaded / (1024 * 1024)
                            mb_total = total / (1024 * 1024)
                            self.progress.emit(pct, f"Downloading... {mb_done:.1f} / {mb_total:.1f} MB")
                        else:
                            mb_done = downloaded / (1024 * 1024)
                            self.progress.emit(-1, f"Downloading... {mb_done:.1f} MB")

            self.progress.emit(100, "Download complete.")
            self.download_complete.emit(dest)

        except Exception as exc:
            self.download_failed.emit(str(exc))


def launch_installer(file_path: str):
    """Launches the downloaded Inno Setup installer and returns immediately.

    The caller should exit the application shortly after calling this so the
    installer can replace files without locking conflicts.
    """
    # /SILENT runs the installer with a progress bar but no user prompts.
    # Remove /SILENT if you want the full Inno Setup wizard experience.
    subprocess.Popen([file_path, "/SILENT"], shell=False)


# ---------------------------------------------------------------------------
# UpdateDialog — premium-styled modal shown when an update is available
# ---------------------------------------------------------------------------
class UpdateDialog(QDialog):
    """Shows update details and allows the user to download, skip, or dismiss."""

    def __init__(self, version: str, download_url: str, changelog: str,
                 asset_size: int = 0, parent=None):
        super().__init__(parent)
        self._version = version
        self._download_url = download_url
        self._changelog = changelog
        self._asset_size = asset_size
        self._downloader = None

        self.setWindowTitle("Update Available")
        self.setMinimumWidth(500)
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e24;
                color: #e4e4e7;
                font-family: 'Segoe UI', sans-serif;
            }
            QLabel { color: #e4e4e7; }
        """)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        # ── Header ──
        title = QLabel(f"🚀 Estimator Pro {self._version} is Available!")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        current = QLabel(f"You are currently running <b>v{APP_VERSION}</b>.")
        current.setStyleSheet("color: #a1a1aa; font-size: 10pt;")
        current.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(current)

        # ── Changelog ──
        if self._changelog:
            sep = QFrame()
            sep.setFrameShape(QFrame.Shape.HLine)
            sep.setStyleSheet("color: #3f3f46;")
            layout.addWidget(sep)

            cl_header = QLabel("What's New")
            cl_header.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            cl_header.setStyleSheet("color: #10b981;")
            layout.addWidget(cl_header)

            cl_body = QLabel(self._changelog)
            cl_body.setWordWrap(True)
            cl_body.setStyleSheet("""
                color: #d1d5db;
                font-size: 9pt;
                background-color: rgba(255, 255, 255, 0.04);
                border: 1px solid #3f3f46;
                border-radius: 6px;
                padding: 10px 14px;
            """)
            layout.addWidget(cl_body)

        # ── Size indicator ──
        if self._asset_size > 0:
            size_mb = self._asset_size / (1024 * 1024)
            size_lbl = QLabel(f"Download size: {size_mb:.1f} MB")
            size_lbl.setStyleSheet("color: #71717a; font-size: 9pt;")
            size_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(size_lbl)

        # ── Progress bar (hidden initially) ──
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(10)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #27272a;
                border: 1px solid #3f3f46;
                border-radius: 5px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #10b981, stop:1 #059669);
                border-radius: 5px;
            }
        """)
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #a1a1aa; font-size: 9pt;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.hide()
        layout.addWidget(self.status_label)

        # ── Buttons ──
        btn_layout = QHBoxLayout()

        self.skip_btn = QPushButton("Skip This Version")
        self.skip_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #71717a;
                border: 1px solid #3f3f46;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 9pt;
            }
            QPushButton:hover { background-color: #27272a; }
        """)
        self.skip_btn.clicked.connect(self._on_skip)

        self.later_btn = QPushButton("Remind Me Later")
        self.later_btn.setStyleSheet("""
            QPushButton {
                background-color: #3f3f46;
                color: #e4e4e7;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 9pt;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #52525b; }
        """)
        self.later_btn.clicked.connect(self.reject)

        self.download_btn = QPushButton("⬇️  Download Update")
        self.download_btn.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                color: #000000;
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
                font-size: 10pt;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #059669; }
        """)
        self.download_btn.clicked.connect(self._on_download)

        btn_layout.addWidget(self.skip_btn)
        btn_layout.addWidget(self.later_btn)
        btn_layout.addWidget(self.download_btn)
        layout.addLayout(btn_layout)

        # Disable download if no URL
        if not self._download_url:
            self.download_btn.setEnabled(False)
            self.download_btn.setText("No Download Available")

    # ── Slots ─────────────────────────────────────────────────────────
    def _on_skip(self):
        """Persist the skipped version so the startup check won't show it again."""
        try:
            from database import DatabaseManager
            db = DatabaseManager()
            db.set_setting("skipped_update_version", self._version)
        except Exception:
            pass
        self.reject()

    def _on_download(self):
        if not self._download_url:
            return
        self.download_btn.setEnabled(False)
        self.skip_btn.setEnabled(False)
        self.later_btn.setEnabled(False)
        self.progress_bar.show()
        self.progress_bar.setRange(0, 100)
        self.status_label.show()
        self.status_label.setText("Connecting…")

        self._downloader = UpdateDownloader(self._download_url, parent=self)
        self._downloader.progress.connect(self._on_progress)
        self._downloader.download_complete.connect(self._on_download_done)
        self._downloader.download_failed.connect(self._on_download_error)
        self._downloader.start()

    def _on_progress(self, pct: int, text: str):
        if pct >= 0:
            self.progress_bar.setValue(pct)
        self.status_label.setText(text)

    def _on_download_done(self, filepath: str):
        self.status_label.setText("Download complete ✓")
        self.status_label.setStyleSheet("color: #10b981; font-size: 9pt;")

        if filepath.lower().endswith((".exe", ".msi")):
            reply = QMessageBox.question(
                self,
                "Install Update",
                "The update has been downloaded.\n\n"
                "Would you like to launch the installer now?\n"
                "Estimator Pro will close so the update can proceed.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                try:
                    launch_installer(filepath)
                    QApplication.instance().quit()
                except Exception as exc:
                    QMessageBox.warning(self, "Error", f"Could not launch installer:\n{exc}")
        else:
            QMessageBox.information(
                self,
                "Download Complete",
                f"The update has been saved to:\n{filepath}\n\n"
                "Please extract / install it manually.",
            )
        self.accept()

    def _on_download_error(self, message: str):
        self.status_label.setText(f"Download failed: {message}")
        self.status_label.setStyleSheet("color: #f43f5e; font-size: 9pt;")
        self.download_btn.setEnabled(True)
        self.skip_btn.setEnabled(True)
        self.later_btn.setEnabled(True)


# ---------------------------------------------------------------------------
# ManualUpdateCheckDialog — compact dialog for Help → Check for Updates
# ---------------------------------------------------------------------------
class ManualUpdateCheckDialog(QDialog):
    """Shows an indeterminate spinner while checking, then the result."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Check for Updates")
        self.setFixedSize(420, 170)
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e24;
                color: #e4e4e7;
                font-family: 'Segoe UI', sans-serif;
            }
            QLabel { color: #e4e4e7; }
        """)
        self._checker = None
        self._build_ui()
        self._start_check()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)

        self.status_label = QLabel("Checking for updates…")
        self.status_label.setFont(QFont("Segoe UI", 11))
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.spinner = QProgressBar()
        self.spinner.setFixedHeight(6)
        self.spinner.setRange(0, 0)  # indeterminate
        self.spinner.setStyleSheet("""
            QProgressBar {
                background-color: #27272a;
                border: none;
                border-radius: 3px;
            }
            QProgressBar::chunk {
                background-color: #10b981;
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.spinner)

        self.close_btn = QPushButton("Close")
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: #3f3f46;
                color: #e4e4e7;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #52525b; }
        """)
        self.close_btn.clicked.connect(self.reject)
        self.close_btn.hide()
        layout.addWidget(self.close_btn, alignment=Qt.AlignmentFlag.AlignCenter)

    def _start_check(self):
        skip_ver = ""
        try:
            from database import DatabaseManager
            db = DatabaseManager()
            skip_ver = db.get_setting("skipped_update_version") or ""
        except Exception:
            pass

        self._checker = UpdateChecker(self, skipped_version=skip_ver)
        self._checker.update_available.connect(self._on_update_found)
        self._checker.up_to_date.connect(self._on_up_to_date)
        self._checker.check_failed.connect(self._on_error)
        self._checker.start()

    def _on_update_found(self, version: str, download_url: str,
                         changelog: str, asset_size: int):
        self.spinner.hide()
        self.close()
        dlg = UpdateDialog(version, download_url, changelog, asset_size,
                           parent=self.parent())
        dlg.exec()

    def _on_up_to_date(self):
        self.spinner.hide()
        self.status_label.setText("✅ You are running the latest version.")
        self.status_label.setStyleSheet("color: #10b981; font-size: 11pt;")
        self.close_btn.show()

    def _on_error(self, message: str):
        self.spinner.hide()
        self.status_label.setText(f"⚠️ Could not check for updates.\n{message}")
        self.status_label.setStyleSheet("color: #f59e0b; font-size: 10pt;")
        self.close_btn.show()

