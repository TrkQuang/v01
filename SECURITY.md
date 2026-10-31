# Security & Trust Policy: Pixel Promotion Claim Assistant

## 1. Non-Custodial Architecture

The Pixel Promotion Claim Assistant operates on a strict **non-custodial** architecture designed to safeguard user accounts:

1. **No Password Collection**: The bot **never** prompts for, receives, or stores Google account passwords.
2. **No 2FA / Recovery Harvesting**: The bot **never** requests two-factor authentication codes, TOTP secrets, or account backup codes.
3. **No Session Hijacking**: The bot **never** asks for Google session cookies, OAuth refresh tokens, or account credentials.
4. **Official Redirection Only**: When account action is required (e.g. checking subscription status or verifying payment methods), the assistant generates direct, official Google HTTPS deep links (`https://one.google.com/`, `https://play.google.com/store/account/subscriptions`) for the user to open in their own browser or native app.

---

## 2. Why Automated Browser Login Is Prohibited

Earlier experimental iterations attempted to automate Google sign-in using Playwright/Selenium browser automation. This practice is fundamentally incompatible with Google security and user safety:

- **Automated Login Blocking**: Google's anti-abuse and risk engine detects browser automation flags and immediately blocks login attempts with:
  > *"Couldn't sign you in. This browser or app may not be secure."*
- **Account Lockout Risk**: Repeated automated sign-in attempts from datacenter or proxy IPs trigger automated security challenges and can cause temporary or permanent Google Account suspension.
- **Hardware Separation**: Promotional offers cannot be claimed via web automation because the Google One redemption endpoint checks for **Titan M2 hardware keystore attestation** via Google Play Services, which automated desktop browsers do not possess.

The assistant therefore relies exclusively on **assisted, non-custodial redemption** where the legitimate device owner redeems the offer directly inside the official **Google One App**.

---

## 3. Hardware Attestation & Anti-Spoofing

Google Pixel promotions require verification that the device is a legitimate physical Google Pixel phone:

- **Titan M2 Keystore Attestation**: Genuine Pixel devices use a discrete Titan M2 security coprocessor to sign cryptographic challenges proving hardware authenticity (`MEETS_DEVICE_INTEGRITY` and `MEETS_STRONG_INTEGRITY`).
- **No Spoofing / No Bypass**: The platform does not fabricate fake IMEIs, fake Android IDs, or spoof Play Integrity verdicts.
- **Classification Tiers**: Connected environments are rigorously classified into `DESKTOP_BROWSER`, `BROWSER_MOBILE_EMULATION`, `ANDROID_EMULATOR`, `PHYSICAL_ANDROID`, or `VERIFIED_PIXEL`. Emulators and browser user-agent spoofing are transparently reported to the user as incapable of claiming hardware offers.

---

## 4. Telemetry Sanitization & Log Redaction

All internal logging and audit records pass through regex redaction (`audit_service.py`) to scrub accidental sensitive patterns:

- Email addresses (`*@*.*`) are obfuscated.
- Bearer tokens, API keys, and authorization headers are masked.
- IP addresses are sanitized before persistence.
- User identifiers are tracked by hashed references where appropriate.

---

## 5. GDPR Compliance & Right to Erasure

Users retain complete control over their diagnostic and claim history:

- **Data Erasure**: Sending `/cancel` or executing `delete_user_data(user_id)` completely deletes the user record, active claim sessions, diagnostic sessions, eligibility records, and associated evidence from the database.
- **Data Minimization**: Only the minimal diagnostic flags necessary to evaluate eligibility (e.g., country code, self-reported device model, account type) are stored.

---

## 6. Vulnerability Disclosure

If you discover a security vulnerability in this project, please open an issue or contact the repository maintainers directly with reproducible steps. Do not disclose vulnerabilities publicly before a fix has been committed.

