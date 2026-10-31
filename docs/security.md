# Security & Data Governance Policy

## 1. Zero Credential Custody Principle

The Pixel Promotion Diagnostic Platform strictly adheres to non-custodial security principles:

1. **No Password Ingestion**: The Telegram bot **never** prompts users to send their Google password, recovery codes, or TOTP secret seeds in chat.
2. **No Credential Persistence**: The database does not contain columns for storing account credentials, cookies, or auth tokens.
3. **No Keylogging or Credential Harvesting**: All legacy code that captured plain passwords via Telegram conversations has been completely removed.

---

## 2. Telemetry & Privacy Controls

- **Audit Logging**: Interactions are logged in the `audit_logs` table with action names (e.g. `CMD_DIAGNOSE`, `CMD_DEVICE`) and timestamps. No personally identifiable account data is stored.
- **Session Lifespans**: Diagnostic session records track test results and confidence levels for debugging history, linked only to the user's Telegram ID.
- **Database Sanitization**: SQLite and PostgreSQL configurations store only diagnostic metrics, country definitions, and device capability summaries.

---

## 3. Anti-Abuse & Integrity Guarantees

- **No Fake Hardware Claims**: The platform will never output fabricated success confirmations or claim that a simulated device redeemed a live Google promotion.
- **No Attestation Bypass Exploits**: The platform does not implement or distribute exploits targeting Google Play Integrity or Titan M2 security chips. It serves purely as an engineering research and diagnostic platform.
