# Architecture & System Design

## 1. Overview

The **Pixel Promotion Diagnostic & Research Platform** is an enterprise-grade analysis engine built to isolate why Google promotional offers (such as 6-month or 12-month Google AI Pro / Gemini Advanced memberships) cannot be claimed in browser-simulated or unverified virtual environments.

```
Telegram Bot (main.py)
        │
        ├──> Session Manager
        ├──> Audit Logger (models.py)
        │
Python Backend Services
        │
        ├──> Device Diagnostic Service (device_diagnostics.py)
        │       └──> Host OS, Browser Detection, ADB Probing
        │
        ├──> Promotion Diagnostic Engine (promotion_diagnostics.py)
        │       ├──> Device Integrity Evaluator
        │       ├──> Account Type Checker
        │       └──> Promotion Catalog Evaluator
        │
        ├──> Country Service (country_service.py)
        │       └──> ISO-3166 Regional Rules (countries.json)
        │
        └──> Google Web Diagnostic Prober (google_automation.py)
                └──> Non-custodial CDP Browser Observation
        │
Persistent Storage (database.py)
        └──> SQLite (default) / PostgreSQL (via DATABASE_URL)
```

---

## 2. Component Directory

| Module | Purpose | Key Classes & Functions |
|---|---|---|
| `main.py` | Telegram bot command handlers, inline keyboards, and session dispatch. | `/start`, `/status`, `/device`, `/eligibility`, `/diagnose`, `/history`, `/help` |
| `device_diagnostics.py` | Host execution layer identification and hardware evidence probing. | `DeviceDiagnosticService`, `DeviceClassification`, `DeviceEvidence` |
| `promotion_diagnostics.py` | Promotion eligibility rules engine and diagnostic report synthesizer. | `PromotionDiagnosticEngine`, `DiagnosticResultCode`, `DiagnosticReport` |
| `country_service.py` | Regional catalog of Google Store promotion availability. | `CountryService`, `CountryEligibility` |
| `google_automation.py` | Authorized, non-custodial Selenium Chrome prober for public Google One endpoints. | `probe_google_one_endpoints()` |
| `device_simulator.py` | Clean CSS viewport and Client Hints definition for web emulation research. | `BrowserSimulationProfile` |
| `database.py` & `models.py` | SQLAlchemy persistence layer for sessions, devices, and audit telemetry. | `init_db()`, `get_db()`, `User`, `DiagnosticSession` |

---

## 3. Execution Data Flow

1. **User Request**: User sends `/diagnose` in Telegram.
2. **Device Sweep**: `DeviceDiagnosticService` evaluates whether execution is `BROWSER_SIMULATION`, `ANDROID_EMULATOR`, `PHYSICAL_ANDROID`, or `VERIFIED_PIXEL`.
3. **Web Observation**: `google_automation.py` probes public endpoints to observe DOM tokens (`BARD_ADVANCED_MODE`, `TIER0`, or security challenge redirects).
4. **Promotion Evaluation**: `PromotionDiagnosticEngine` runs tests across hardware attestation, account eligibility, region, and payment requirements.
5. **Persistence**: The diagnostic session, individual check findings, and telemetry are written to the database.
6. **Delivery**: The Telegram user receives a structured breakdown with specific blocker codes and actionable next steps.
