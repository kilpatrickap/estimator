# Implementation Plan: Trial Gating Splash Screen (Code Green/Yellow/Red/Black)

This plan details the design and implementation for a **Trial Gating Splash Screen** in **Estimator Pro**. The gating mechanism uses a probabilistic trial degradation model (based on B.F. Skinner's operant conditioning and variable reinforcement schedules) to incentivize conversion from free to paid users within a 45-day window.

---

## User Review Required

> [!IMPORTANT]
> **Probabilistic App Gating (Extinction Resistance):**
> * Instead of locking the user out completely after 30 days, we gate the **app startup process** itself on a probabilistic scale.
> * Users in Code Yellow (Days 31-40) have a **30% chance** of launching the app.
> * Users in Code Red (Days 41-45) have a **10% chance** of launching the app.
> * If a roll fails, the splash screen displays the current trial status and urges the user to restart the app and "keep trying" (leveraging variable reinforcement) or purchase a Paid license (**Green Pass**) to restore immediate, 100% reliable launch.

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
    D --> E{License Status == 'Paid'?}
    E -- Yes --> F[Code Green: Load MainWindow]
    E -- No --> G[Calculate Days Since Install]
    G --> H{Determine Stage}
    H -- Days <= 30 --> I[Code Green: 100% Launch]
    H -- Days 31-40 --> J[Code Yellow: 30% Launch Roll]
    H -- Days 41-45 --> K[Code Red: 10% Launch Roll]
    H -- Days >= 46 --> L[Code Black: 1% Launch Roll]
    
    I --> F
    J -- Pass --> F
    K -- Pass --> F
    L -- Pass --> F
    
    J -- Fail --> M[Show Splash screen with Retry/Purchase buttons]
    K -- Fail --> M
    L -- Fail --> M
```

---

### Components

#### [NEW] [trial_splash.py](file:///c:/Users/Consar-Kilpatrick/Estimator_Pro_20May26/estimator/trial_splash.py)
This module will define the `TrialSplashDialog` class, inheriting from `QDialog`:
*   **Window Configuration:** Borderless frame (`Qt.WindowType.FramelessWindowHint`) with translucent background and drop shadow support.
*   **Curated Aesthetics:** Curated color gradients matching the status code:
    *   **Code Green:** Deep forest green and charcoal gradient with bright emerald highlights.
    *   **Code Yellow:** Warm amber and charcoal gradient with bright gold highlights.
    *   **Code Red:** Crimson red and dark charcoal gradient with rose highlights.
    *   **Code Black:** Sleek carbon-fiber black gradient with dark slate and violet highlights.
*   **Interactive Simulation Dialog:** Clicking the "Upgrade to Paid" button displays a payment simulation window. Clicking "Simulate Purchase" instantly writes `license_status = 'Paid'` to the database and re-evaluates the launch state.
*   **Developer Panel (Testing Toolbar):**
    *   Dropdown: `Auto (Date-based)`, `Force Green`, `Force Yellow`, `Force Red`, `Force Black`.
    *   Buttons: `Set Install to Day -35 (Yellow)`, `Set Install to Day -42 (Red)`, `Set Install to Day -50 (Black)`, `Reset Trial`.
    *   Simulates rolls instantly when inputs are toggled.

#### [MODIFY] [main.py](file:///c:/Users/Consar-Kilpatrick/Estimator_Pro_20May26/estimator/main.py)
We will integrate the splash screen before displaying `MainWindow`:
*   Import `TrialSplashDialog` and `DatabaseManager`.
*   Check if running in a pytest environment (e.g. searching `sys.modules`). If yes, bypass splash screen to keep tests green.
*   Instantiate `TrialSplashDialog` and run `exec()`.
*   If the splash screen dialog accepts (returns `Accepted`), instantiate and show `MainWindow`.
*   If the dialog rejects (returns `Rejected`), exit the application process.

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
