# Pixel Promotion Research & Diagnostic Platform

A Telegram-based research and diagnostic platform designed to analyze Google Pixel promotional eligibility (Google AI Pro / Gemini Advanced offers) and diagnose why browser-simulated and virtual environments fail to claim hardware-bound offers.

---

## 🌟 Key Features

| Capability | Technical Details |
|---|---|
| 📱 **Device Environment Diagnostics** | Classifies execution into `BROWSER_SIMULATION`, `ANDROID_EMULATOR`, `PHYSICAL_ANDROID`, or `VERIFIED_PIXEL`. Probes ADB, bootloader state, and Play Services. |
| 🔬 **Eligibility Diagnostic Engine** | Evaluates promotional eligibility across 9 deterministic result codes (`OFFER_VISIBLE`, `DEVICE_NOT_VERIFIED`, `REGION_NOT_SUPPORTED`, `ACCOUNT_NOT_ELIGIBLE`, etc.). |
| 🌍 **Country & Store Database** | ISO-3166 regional matrix detailing Google AI Pro and Google Pixel promotion support. |
| 🔒 **Non-Custodial Architecture** | Never collects or stores Google account passwords, 2FA codes, recovery codes, or session tokens. |
| 📊 **Persistent Audit & History** | SQLite (default) and PostgreSQL support via SQLAlchemy tracking diagnostic sessions and telemetry. |
| 🤖 **Interactive Telegram Bot** | Modern Telegram UI with inline keyboards, live diagnostic sweeps, and structured reports. |

---

## 🏗️ Architecture

```
Telegram Bot (main.py)
        │
        ├──> Device Diagnostic Service (device_diagnostics.py)
        ├──> Promotion Diagnostic Engine (promotion_diagnostics.py)
        ├──> Country Service (country_service.py)
        ├──> Google Web Diagnostic Prober (google_automation.py)
        │
        └──> SQLAlchemy Storage (database.py) ──> SQLite / PostgreSQL
```

For detailed architectural diagrams and data flows, see [docs/architecture.md](docs/architecture.md).

---

## 🚀 Quickstart

### 1. Installation

```bash
git clone https://github.com/TrkQuang/v01.git
cd v01
pip install -r requirements.txt
```

### 2. Configure Environment

Set your Telegram Bot token:

```bash
# On Linux / macOS / Replit Secrets:
export TELEGRAM_BOT_TOKEN="your_bot_token_from_botfather"

# On Windows PowerShell:
$env:TELEGRAM_BOT_TOKEN="your_bot_token_from_botfather"
```

### 3. Run Automated Tests

Run the full pytest test suite (19 unit & integration tests):

```bash
pytest tests -v
```

### 4. Start the Platform

```bash
python main.py
```

---

## 📱 Telegram Commands

| Command | Purpose |
|---|---|
| `/start` | Platform welcome message, privacy policy, and interactive menu. |
| `/device` | Diagnostic sweep of execution host, browser, ADB, and hardware attestation. |
| `/eligibility` | Interactive country selector to test regional eligibility against Google Store terms. |
| `/diagnose` | Comprehensive multi-tier diagnostic run (Device + Region + Web Prober). |
| `/status` | Platform health, active database, and execution tier overview. |
| `/history` | View your past 5 diagnostic sessions and result codes. |
| `/help` | Detailed manual and explanation of all diagnostic result codes. |

---

## 📚 Technical Documentation

- [Device Diagnostics & Hardware Attestation](docs/device-diagnostics.md)
- [Promotion Eligibility & Condition Matrix](docs/promotion-eligibility.md)
- [Security & Non-Custodial Architecture](docs/security.md)
- [System Architecture & Data Flows](docs/architecture.md)

---

## ⚠️ Important Engineering Note

Google Pixel promotional offers are **cryptographically hardware-bound**. Desktop browser simulations, User-Agent overrides (`Sec-CH-UA-Model`), and standard Android emulators cannot forge Titan M2 KeyStore attestation or Google Play Integrity tokens. 

To redeem a live promotional offer, the account owner must activate the offer directly through the **Google One App** on a **physical Google Pixel device** in an officially supported country with an eligible personal Google Account.
