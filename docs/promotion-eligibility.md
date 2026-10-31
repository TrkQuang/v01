# Promotion Eligibility Rules & Research

## 1. Verified Promotion Parameters

Google bundles promotional trial subscriptions (such as Google AI Pro with Gemini Advanced and expanded storage) with retail purchases of eligible flagship Google Pixel models.

### Promotion Types & Durations
- **12-Month AI Premium Trial**: Bundled with Pixel 9 Pro, Pixel 9 Pro XL, and Pixel 9 Pro Fold purchases.
- **6-Month AI Pro Trial**: Bundled with recent flagship Pixel Pro hardware generations (including Pixel 11 Pro target campaigns).

---

## 2. Requirement Tiers (Condition Separation)

Promotional eligibility is not a single binary toggle. It requires satisfying four separate tiers:

```
[ Tier A: Geographic & Store Region ]
  └── Account billing country & IP must be an official Google Store territory (e.g. US, UK, DE, JP).
           │
           ▼
[ Tier B: Physical Device Hardware ]
  └── Factory-registered retail Pixel phone with locked bootloader and verified Titan M2 chip.
           │
           ▼
[ Tier C: Google Account State ]
  └── Personal @gmail.com account; NOT Workspace, NOT Family Link shared plan, NOT past trial.
           │
           ▼
[ Tier D: Billing Instrument ]
  └── Valid payment method on Google Play Payments to authorize 0đ recurring subscription.
```

---

## 3. Diagnostic Result Codes

The platform outputs structured result codes based on evaluation evidence:

| Code | Explanation | Evidence | Actionable Step |
|---|---|---|---|
| `OFFER_VISIBLE` | All conditions met; offer card rendered. | DOM tokens or GMS entitlements confirmed. | Complete trial checkout on device. |
| `OFFER_NOT_VISIBLE` | Page or app loaded, but no offer card returned. | Benefits page contains 0 perk cards. | Review account type and device tier. |
| `DEVICE_NOT_VERIFIED` | Session originates from browser emulation or uncertified emulator. | Lack of hardware Titan M2 attestation token. | Switch to physical retail Pixel device. |
| `REGION_NOT_SUPPORTED` | Country is excluded from official retail promotion. | ISO country code not supported in Google Store terms. | Use account from eligible territory. |
| `ACCOUNT_NOT_ELIGIBLE` | Ineligible account type (Workspace, Family Group, or existing sub). | Enterprise domain or active subscription conflict. | Use clean personal @gmail.com account. |
| `PAYMENT_REQUIREMENT_MISSING` | Account lacks billing instrument on Google Play. | Wallet has no credit/debit card on file. | Add payment method at payments.google.com. |
| `PROMOTION_EXPIRED` | Hardware redemption deadline has passed. | Google One catalog marks campaign concluded. | Check official Google Store campaign dates. |
| `MANUAL_REVIEW_REQUIRED` | Google triggered an interactive security challenge. | Redirect to accounts.google.com/challenge. | Authenticate directly in personal browser. |
| `UNKNOWN` | Network or infrastructure anomaly prevented verification. | Timeout or unexpected HTTP response. | Re-run diagnostic probe. |
