# Pixel Promotion Claim Assistant & Diagnostic Platform

A Telegram-based assistant and diagnostic platform designed to help owners of Google Pixel devices discover, evaluate, access, redeem, and verify official Google AI Pro / Gemini promotional offers through official, non-custodial workflows.

---

## 🌟 Key Capabilities

| Capability | Description |
|---|---|
| 🎯 **Guided Redemption Workflow** | Step-by-step 7-phase non-custodial claim assistant with deterministic state management (`/claim`). |
| 📋 **Official Promotion Catalog** | Authoritative catalog of verified Google Pixel offers (Pixel 9 Pro 12M AI Premium, Pixel 9 6M) and unverified research targets (`/promotions`). |
| 🛡️ **Non-Custodial Architecture** | Zero password/2FA harvesting. Generates official deep links and in-app instructions; all sensitive actions occur directly on official Google services. |
| 📱 **Device Environment Diagnostics** | Classifies environments into `DESKTOP_BROWSER`, `BROWSER_MOBILE_EMULATION`, `ANDROID_EMULATOR`, `PHYSICAL_ANDROID`, or `VERIFIED_PIXEL`. Probes ADB, bootloader state, GMS, and Play Store (`/device`). |
| 🔬 **Authoritative Eligibility Engine** | Comprehensive matrix checking device, country, Google account type, active subscriptions, payment methods, and redemption history (`/eligibility`). |
| 🔍 **Redemption Verification** | Multi-tier evidence verification (direct verification or user-reported outcome classification) enforcing integrity (`/status`, `/history`). |
| 📊 **Full Audit Trail & GDPR Erasure** | Structured audit logging with token/credential regex sanitization and one-click data deletion (`/cancel`). |

---

## 🏗️ System Architecture

```
Telegram Bot (main.py)
        │
        ├──> User Session Manager (session_manager.py)
        │         └──> State Machine (INIT -> IN_PROGRESS -> CLAIM_VERIFIED)
        │
        ├──> Promotion Discovery Service (promotion_service.py)
        │         └──> Official Catalog (promotion_catalog.py)
        │
        ├──> Eligibility Evaluation Engine (eligibility_engine.py)
        │         ├──> Country Service (country_service.py & countries.json)
        │         └──> Account Guidance Flow (google_account_flow.py)
        │
        ├──> Device Verification Service (device_verification.py)
        │         └──> ADB Hardware Prober & Environment Classifier
        │
        ├──> Redemption Workflow & Verification (redemption_workflow.py, redemption_verification.py)
        │         └──> Assisted Non-Custodial Redemption Flow
        │
        └──> Audit & Storage Engine (audit_service.py & database.py)
                  └──> SQLite / PostgreSQL via SQLAlchemy
```

For complete architectural specifications, see [docs/architecture.md](docs/architecture.md).

---

## 📱 Telegram Bot Commands

| Command | Description |
|---|---|
| `/start` | Welcome screen, non-custodial security policy, and interactive main menu. |
| `/claim` | Start a guided, 7-step promotional redemption workflow. |
| `/promotions` | Browse official active Google Pixel promotional campaigns and research targets. |
| `/account` | Check Google account readiness (Workspace check, Family Group conflicts, payment methods). |
| `/device` | Diagnostic sweep of execution host, browser, ADB, and hardware attestation. |
| `/eligibility` | Interactive country selector to test regional eligibility against Google Store terms. |
| `/diagnose` | Comprehensive multi-tier diagnostic run (Device + Region + Web Prober). |
| `/status` | Active claim session status, database health, and execution tier overview. |
| `/history` | View your past claim sessions and eligibility check results. |
| `/cancel` | Cancel active claim workflow and execute GDPR data erasure. |
| `/help` | Detailed command manual and explanation of all diagnostic result codes. |

---

## 🚀 Quickstart Guide

### 1. Installation

```bash
git clone https://github.com/TrkQuang/v01.git
cd v01
python -m venv .venv

# On Linux / macOS:
source .venv/bin/activate
# On Windows PowerShell:
.venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

### 2. Configuration

Copy the example environment template and configure your Telegram bot token:

```bash
cp .env.example .env
```

Edit `.env`:
```ini
TELEGRAM_BOT_TOKEN="your_bot_token_from_botfather"
DATABASE_URL="sqlite:///pixel_diagnostics.db"
LOG_LEVEL="INFO"
```

### 3. Automated Test Suite

Run the full pytest test suite (40 unit and integration tests covering all 15 architecture phases):

```bash
pytest tests -v
```

### 4. Run the Bot

```bash
python main.py
```

---

## 📚 Detailed Documentation

- **[Deployment Guide](DEPLOYMENT.md)**: Production deployment instructions for Replit, Docker Compose, Linux VPS (systemd), and PostgreSQL.
- **[Security & Trust Policy](SECURITY.md)**: Details on non-custodial principles, why automated Google sign-in is blocked, and GDPR erasure.
- **[Promotional Campaigns Registry](PROMOTION_SOURCES.md)**: Verified Google Store terms, eligible models, and disclosure of unverified research targets.
- **[Device Diagnostics & Hardware Attestation](docs/device-diagnostics.md)**: In-depth analysis of Titan M2 Keystore, Play Integrity, and emulator limitations.
- **[Promotion Eligibility Engine](docs/promotion-eligibility.md)**: Decision trees and condition matrices for account and regional qualification.

---

## ⚠️ Important Engineering Notice

Google Pixel promotional offers are **cryptographically hardware-bound**. Desktop browser simulations, User-Agent overrides (`Sec-CH-UA-Model`), and standard Android emulators cannot forge Titan M2 KeyStore attestation or Google Play Integrity tokens. 

To redeem a live promotional offer, the account owner must activate the offer directly through the **Google One App** on a **physical Google Pixel device** in an officially supported country with an eligible personal Google Account.
