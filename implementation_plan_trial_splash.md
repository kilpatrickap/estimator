# Implementation Plan: Trial Gating Splash Screen (Code Green/Yellow/Red/Black)

This plan details the design and implementation for a **Trial Gating Splash Screen** in **Estimator Pro**. The gating mechanism uses a probabilistic trial degradation model (based on B.F. Skinner's operant conditioning and variable reinforcement schedules) to incentivize conversion from free to paid users within a 45-day window.

> [!IMPORTANT]
> **Psychological Honesty Principle:** All messaging in this system uses a **Trial Pass / Fuel Gauge** metaphor — not fake network or server errors. Deceptive server-failure framing is a detectable lie (no network traffic occurs) that destroys user trust before conversion can happen. Skinner's conditioning only works when the organism cannot identify the mechanism as manipulative. The revised framing is honest, professional, and more effective.

---

## User Review Required

> [!IMPORTANT]
> **Probabilistic App Gating (Extinction Resistance):**
> * Instead of locking the user out completely after 30 days, we gate the **app startup process** itself on a probabilistic scale.
> * Users in Yellow Zone (Days 31-40) have a **30% chance** of launching the app — a **Variable Ratio Schedule**, the same schedule used by slot machines and the most extinction-resistant reinforcement pattern known.
> * Users in Red Zone (Days 41-45) have a **10% chance** of launching the app — **Scarcity + Loss Aversion** framing ("every day you wait is a bid you can't price").
> * Users in Black Zone (Days 46+) have a **1% chance** — near-extinction state with a one-time **Emergency Pass** safety valve to prevent review-damaging lockouts.
> * If a roll fails, the splash displays the current **Trial Pass status** (not a fake server error) with stage-specific copy and CTAs (Try Again / Emergency Pass / Upgrade).

> [!TIP]
> **Developer Testing Panel:**
> To make it easy for you to review and verify all 4 states, we will build a collapsible **Developer Panel** at the bottom of the splash screen. It will allow you to instantly switch the simulated trial stage, reset the trial, or shift the installation date backward.

---

## Proposed Changes

We will introduce a new module [trial_splash.py](file:///c:/Users/Consar-Kilpatrick/Estimator_Pro_20May26/estimator/trial_splash.py) and modify the application entry point [main.py](file:///c:/Users/Consar-Kilpatrick/Estimator_Pro_20May26/estimator/main.py).

---

### Gating Logic & Startup Flow

```mermaid
graph TD
    A[Start App] --> B{Is Test Mode?}
    B -- Yes --> C[Load MainWindow Directly]
    B -- No --> D[Check Database Settings]
    D --> E{License Status == Encrypted Signature?}
    E -- Yes --> F[Code Green: Load MainWindow]
    E -- No --> G[Check Date Integrity]
    G -- Tampered --> H[Force Code Red/Black]
    G -- Ok --> I[Calculate Days Since Install]
    I --> J{Determine Stage}
    J -- Days <= 30 --> K[Code Green: 100% Launch]
    J -- Days 31-40 --> L[Code Yellow: 30% Launch Roll]
    J -- Days 41-45 --> M[Code Red: 10% Launch Roll]
    J -- Days >= 46 --> N[Code Black: 1% Launch Roll]
    
    K --> F
    L -- Pass --> F
    M -- Pass --> F
    N -- Pass --> F
    
    L -- Fail --> O[Show Splash screen with Retry/Purchase/Emergency buttons]
    M -- Fail --> O
    N -- Fail --> O
```

---

### Components

#### [NEW] [trial_splash.py](file:///c:/Users/Consar-Kilpatrick/Estimator_Pro_20May26/estimator/trial_splash.py)
This module defines the `TrialSplashDialog` class, inheriting from `QDialog`:
*   **Window Configuration:** Borderless frame (`Qt.WindowType.FramelessWindowHint`) with translucent background and drop shadow support.
*   **Curated Aesthetics:** Curated color gradients matching the status code:
    *   **Green Zone:** Deep forest green and charcoal gradient with bright emerald highlights.
    *   **Yellow Zone:** Warm amber and charcoal gradient with bright gold highlights.
    *   **Red Zone:** Crimson red and dark charcoal gradient with rose highlights.
    *   **Black Zone:** Sleek carbon-fiber black gradient with dark slate and violet highlights.
*   **Honest Trial Pass Framing:** All messaging uses a **Trial Pass / Fuel Gauge** metaphor. No fake server or network-failure language is used anywhere — it is detectable (no network traffic occurs on a standalone desktop app) and destroys user trust before conversion.
*   **Stage-Specific Skinnerian Copy:**
    *   **Green (Days 1–30):** Shows `Day X of 30 (Y days remaining)` — Fixed Interval awareness primes urgency *before* Yellow kicks in.
    *   **Yellow (Days 31–40, 30%):** `"Your Trial Pass is in the Yellow Zone — launches are no longer guaranteed. Upgrade for instant, guaranteed access every time."` — Variable Ratio framing, upgrade = certainty.
    *   **Red (Days 41–45, 10%):** `"Only 10% of trial launches succeed at this stage. Every day you wait is a bid you can't price."` — Loss Aversion framing.
    *   **Black (Days 46+, 1%):** `"Are you in the middle of an urgent bid? Use your one-time Emergency Pass, or upgrade for permanent access."` — Crisis relief → reciprocity obligation.
*   **Near-Miss Animation:** In Yellow and Red zones, ~40% of failed rolls show the progress bar filling to 72–91% before draining back — a classic near-miss effect that maintains engagement and slot-machine psychology.
*   **Attempt Counter:** Tracks `trial_attempt_count` in the DB. On failure in Yellow/Red/Black, shows: `"You've attempted N launches this trial. Upgrade once — launch forever."` — Ratio fatigue framing.
*   **Interactive Simulation Dialog:** Clicking "Upgrade" opens a checkout window. "Activate Green Pass (Simulation)" writes an encrypted license signature (SHA-256) to the DB and re-evaluates state.
*   **Emergency Pass Button:** Visible **only** in Black Zone. One-time use. Grants 24-hour access. Dialog copy makes reciprocity obligation explicit: `"Remember: this pass is one-time only and cannot be extended. Upgrade to a permanent Green Pass to never face this again."`
*   **Developer Panel (Testing Toolbar):** Hidden behind `Ctrl+Shift+Alt+D` + password prompt.
    *   Dropdown: `Auto (Date-based)`, `Force Green`, `Force Yellow`, `Force Red`, `Force Black`.
    *   Buttons: `Set Install to Day -35 (Yellow)`, `Set Install to Day -42 (Red)`, `Set Install to Day -50 (Black)`, `Reset Trial` (clears `install_date`, `license_status`, `emergency_bypass_date`, `last_run_date`, `trial_attempt_count`).

#### [MODIFY] [main.py](file:///c:/Users/Consar-Kilpatrick/Estimator_Pro_20May26/estimator/main.py)
We will integrate the splash screen before displaying `MainWindow`:
*   Import `TrialSplashDialog` and `DatabaseManager`.
*   **Test Environment Check:** Check if running in a pytest environment (e.g. searching `sys.modules` and inspecting `PYTEST_CURRENT_TEST` env). If yes, bypass splash screen to keep tests green.
*   **Database Access Guard:** Wrap startup database connection in a try-except block with 3 connection retries (500ms delay) to prevent lockout from Windows ghost processes. If connection completely fails, fallback to a safe **Code Green** trial state.
*   **Date Integrity Check:** Compare current date against database's `last_run_date`. If time went backward by more than 24 hours, flag a date-tamper state. Otherwise, update `last_run_date` to the current date.
*   Instantiate `TrialSplashDialog` and run `exec()`.
*   If the splash screen dialog accepts (returns `Accepted`), instantiate and show `MainWindow`.
*   If the dialog rejects (returns `Rejected`), exit the application process.

---

## Risk Mitigation Plan

### 1. Clock Manipulation Guard (Date-Tamper Protection)
*   **Risk:** Users changing their system clock backward to artificially extend Code Green/Yellow status.
*   **Mitigation:** The database will track `last_run_date`. To prevent false-positives when users change timezones or travel, we only trigger a clock-rollback lockout if `current_date < last_run_date - 1 day` (more than 24 hours difference). If rollback is detected, the app is restricted to **Code Red** or **Code Black** until corrected.

### 2. PyTest & CI Hang Prevention
*   **Risk:** Automated test runs getting blocked by interactive `exec()` dialogs, causing infinite hangs.
*   **Mitigation:** We implement a robust multi-point check in `main.py` looking for `pytest` and `_pytest` in `sys.modules` and inspecting `PYTEST_CURRENT_TEST` in environment variables.

### 3. Safe Startup Exception Handling (Locked Databases)
*   **Risk:** Application crashes if database is locked by another instance or file system access fails.
*   **Mitigation:** Database operations in `main.py` will be wrapped in try-except blocks. If a connection failure occurs, the app falls back to a safe **Code Green** state to prevent locking out legitimate paying users. Additionally, connection attempts will retry 3 times with a 500ms delay to accommodate quick restarts.

### 4. Memory and Threading Safety (Event Loop Cleanup)
*   **Risk:** Stray progress bar animation timers in the splash screen causing PyQt warnings or crashes upon transition to the main window.
*   **Mitigation:** All timers in the `TrialSplashDialog` will be explicitly terminated on dialog destruction.

### 5. Existing User Database Migration
*   **Risk:** Existing users updating the app won't have trial date rows in their settings database.
*   **Mitigation:** If the check fails to find `install_date`, we default to setting it to the **current date**, giving existing upgraders a fresh 30 days.

### 6. License Tamper Prevention (Basic DRM)
*   **Risk:** Users manually opening their SQLite database with external tools and writing `'Paid'` to the settings table.
*   **Mitigation:** We will store a hashed/encrypted signature (e.g., a hash of a constant combined with a secret salt) in `license_status` instead of a plain text string to prevent simple DB editor manipulation.

### 7. Support & Review Backlash Prevention (Emergency Valve)
*   **Risk:** A critical user blocked in Code Red/Black from finishing an urgent construction bid, causing support bottlenecks and 1-star reviews.
*   **Mitigation:** When a roll fails in the Code Black lane, we will provide a **"24-Hour Emergency Extension"** button. This grants a temporary 1-day launch pass to ensure business safety during deadlines, with a clear note that they must upgrade to permanent status afterward. The button is hidden in other lanes.

---

## Verification Plan

### Automated Tests
*   We will ensure the existing test suite continues to pass (39/39 tests) by bypassing the gating logic during testing environments.
*   Add verification assertions checking that `DatabaseManager` gets/sets settings correctly.

### Manual Verification
1.  **Launch the App:** Confirm that the splash screen loads first.
2.  **Verify Code Green (Days 1–30):** Select `Force Green` or set `Reset Trial`. The screen should show a green progress bar and load the main app automatically after a short delay.
3.  **Verify Code Yellow (Days 31–40):** Toggle to `Force Yellow` or click the `-35 Days` button. Click "Try to Load". Observe the 30% success rate (some clicks will load the app, others will fail and show the connection failed screen).
4.  **Verify Code Red (Days 41–45):** Toggle to `Force Red` or click the `-42 Days` button. Click "Try to Load" and observe the 10% success rate.
5.  **Verify Code Black (Days 46+):** Toggle to `Force Black` or click the `-50 Days` button. Verify the 1% success rate and the dark lock screen.
6.  **Verify Checkout Simulation:** Click "Upgrade to Paid" from any failed state, click "Simulate Purchase", verify the success message, and confirm the app now opens immediately as a premium Paid License user.
7.  **Verify Emergency Valve:** Click the "24-Hour Emergency Extension" button in Code Black (confirming it is hidden/inaccessible in Green, Yellow, and Red lanes) and confirm it temporarily grants access and launches the main window.
