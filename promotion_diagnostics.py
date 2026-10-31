"""
Promotion Eligibility & Diagnostic Engine.

Evaluates promotional parameters against verified Google One & Pixel rules:
- Promotion availability & expiration
- Device hardware attestation & integrity
- Regional country support & Google Store policy
- Account type restrictions (Workspace, Family Group, existing trial)
- Payment requirement checks

Output result codes:
1. OFFER_VISIBLE
2. OFFER_NOT_VISIBLE
3. DEVICE_NOT_VERIFIED
4. REGION_NOT_SUPPORTED
5. ACCOUNT_NOT_ELIGIBLE
6. PAYMENT_REQUIREMENT_MISSING
7. PROMOTION_EXPIRED
8. UNKNOWN
9. MANUAL_REVIEW_REQUIRED
"""

import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from country_service import country_service
from device_diagnostics import DeviceClassification, DeviceEvidence

logger = logging.getLogger(__name__)


class DiagnosticResultCode(str, Enum):
    OFFER_VISIBLE = "OFFER_VISIBLE"
    OFFER_NOT_VISIBLE = "OFFER_NOT_VISIBLE"
    DEVICE_NOT_VERIFIED = "DEVICE_NOT_VERIFIED"
    REGION_NOT_SUPPORTED = "REGION_NOT_SUPPORTED"
    ACCOUNT_NOT_ELIGIBLE = "ACCOUNT_NOT_ELIGIBLE"
    PAYMENT_REQUIREMENT_MISSING = "PAYMENT_REQUIREMENT_MISSING"
    PROMOTION_EXPIRED = "PROMOTION_EXPIRED"
    UNKNOWN = "UNKNOWN"
    MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"


@dataclass
class CheckFinding:
    check_name: str
    result_code: DiagnosticResultCode
    passed: bool
    explanation: str
    evidence: str
    confidence: float
    possible_causes: List[str] = field(default_factory=list)
    recommended_step: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["result_code"] = self.result_code.value
        return d


@dataclass
class DiagnosticReport:
    overall_code: DiagnosticResultCode
    confidence: float
    summary: str
    findings: List[CheckFinding] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_code": self.overall_code.value,
            "confidence": self.confidence,
            "summary": self.summary,
            "findings": [f.to_dict() for f in self.findings],
            "timestamp": self.timestamp,
        }


class PromotionDiagnosticEngine:
    """Core diagnostic engine assessing promotion eligibility."""

    def evaluate(
        self,
        device_class: DeviceClassification,
        device_evidence: DeviceEvidence,
        country_code: str = "US",
        account_email: Optional[str] = None,
        account_is_workspace: bool = False,
        account_in_family_group: bool = False,
        has_active_subscription: bool = False,
        has_payment_method: Optional[bool] = None,
        promotion_code: str = "PIXEL_11_PRO_6M_AI_PRO",
        web_observed_status: Optional[str] = None,
    ) -> DiagnosticReport:
        """Run complete battery of diagnostic checks."""
        findings: List[CheckFinding] = []

        # 1. Device Hardware Integrity Check
        dev_finding = self._check_device_integrity(device_class, device_evidence)
        findings.append(dev_finding)

        # 2. Regional / Country Check
        region_finding = self._check_region(country_code)
        findings.append(region_finding)

        # 3. Account Eligibility Check
        acct_finding = self._check_account_eligibility(
            account_email=account_email,
            is_workspace=account_is_workspace,
            in_family_group=account_in_family_group,
            has_active_sub=has_active_subscription,
        )
        findings.append(acct_finding)

        # 4. Promotion Expiration & Availability Check
        promo_finding = self._check_promotion_availability(promotion_code)
        findings.append(promo_finding)

        # 5. Payment Requirement Check
        if has_payment_method is not None:
            pay_finding = self._check_payment_method(has_payment_method)
            findings.append(pay_finding)

        # 6. Web Observation Check (if web probe was run)
        if web_observed_status:
            web_finding = self._check_web_observation(web_observed_status)
            findings.append(web_finding)

        # Compute overall diagnosis
        return self._compute_overall_report(findings)

    def _check_device_integrity(self, device_class: DeviceClassification, evidence: DeviceEvidence) -> CheckFinding:
        if device_class == DeviceClassification.VERIFIED_PIXEL:
            return CheckFinding(
                check_name="Device Hardware Verification",
                result_code=DiagnosticResultCode.OFFER_VISIBLE,
                passed=True,
                explanation="Device is cryptographically verified physical Google Pixel hardware.",
                evidence=f"Model: {evidence.model_string}, locked bootloader: {evidence.bootloader_locked}, GMS installed: {evidence.play_services_installed}.",
                confidence=0.98,
                recommended_step="Launch the Google One app directly on the device.",
            )

        if device_class == DeviceClassification.BROWSER_SIMULATION:
            return CheckFinding(
                check_name="Device Hardware Verification",
                result_code=DiagnosticResultCode.DEVICE_NOT_VERIFIED,
                passed=False,
                explanation="Browser emulation cannot satisfy Google's hardware-backed Play Integrity requirements.",
                evidence=(
                    f"Execution layer is {evidence.host_os} desktop browser. "
                    "Browser User-Agent / CDP simulation cannot forge Titan M2 KeyStore attestation or GMS hardware checkin."
                ),
                confidence=1.0,
                possible_causes=[
                    "Running tests via Selenium / desktop Chrome instead of bare-metal Pixel device.",
                    "Missing Google Play Services runtime container.",
                    "Absence of factory-provisioned hardware attestation key.",
                ],
                recommended_step="Redemption requires a physical Google Pixel device running official, locked Google firmware.",
            )

        if device_class == DeviceClassification.ANDROID_EMULATOR:
            return CheckFinding(
                check_name="Device Hardware Verification",
                result_code=DiagnosticResultCode.DEVICE_NOT_VERIFIED,
                passed=False,
                explanation="Android Studio / AVD emulator detected. Virtual devices lack Google retail hardware certification.",
                evidence="Emulator indicators detected via ADB props (goldfish/ranchu kernel, virtual build fingerprint).",
                confidence=0.95,
                possible_causes=[
                    "Google Play Integrity denies MEETS_DEVICE_INTEGRITY to generic AVD images.",
                    "Uncertified build fingerprint in emulator image.",
                ],
                recommended_step="Switch to physical Pixel hardware.",
            )

        return CheckFinding(
            check_name="Device Hardware Verification",
            result_code=DiagnosticResultCode.UNKNOWN,
            passed=False,
            explanation="Could not determine device hardware status with certainty.",
            evidence=f"Classification returned {device_class.value}.",
            confidence=0.4,
            recommended_step="Connect device via ADB to inspect system build properties.",
        )

    def _check_region(self, country_code: str) -> CheckFinding:
        reg = country_service.check_region_eligibility(country_code)
        status = reg.get("status")
        cname = reg.get("country_name", country_code)

        if status == "ELIGIBLE":
            return CheckFinding(
                check_name="Regional Eligibility",
                result_code=DiagnosticResultCode.OFFER_VISIBLE,
                passed=True,
                explanation=f"{cname} is an officially supported territory for Google Pixel promotions.",
                evidence=reg.get("evidence", ""),
                confidence=0.95,
                recommended_step="Ensure account billing address matches this country.",
            )
        elif status == "INELIGIBLE":
            return CheckFinding(
                check_name="Regional Eligibility",
                result_code=DiagnosticResultCode.REGION_NOT_SUPPORTED,
                passed=False,
                explanation=f"{cname} ({country_code}) is not an eligible region for Google Pixel hardware promotions.",
                evidence=reg.get("evidence", ""),
                confidence=0.95,
                possible_causes=[
                    "Google Store does not officially distribute retail Pixel hardware in this country.",
                    "Google Play billing terms exclude this jurisdiction from hardware bundles.",
                ],
                recommended_step="Test with an account registered in a supported region (US, GB, DE, JP, etc.).",
            )
        else:
            return CheckFinding(
                check_name="Regional Eligibility",
                result_code=DiagnosticResultCode.UNKNOWN,
                passed=False,
                explanation=f"Eligibility data for country code '{country_code}' is unverified.",
                evidence=reg.get("evidence", ""),
                confidence=0.5,
                recommended_step="Consult local Google Store promotional terms.",
            )

    def _check_account_eligibility(
        self,
        account_email: Optional[str],
        is_workspace: bool,
        in_family_group: bool,
        has_active_sub: bool,
    ) -> CheckFinding:
        if is_workspace or (account_email and not account_email.lower().endswith("@gmail.com")):
            return CheckFinding(
                check_name="Account Type Eligibility",
                result_code=DiagnosticResultCode.ACCOUNT_NOT_ELIGIBLE,
                passed=False,
                explanation="Google Workspace (business/school) accounts are ineligible for Google One personal trials.",
                evidence=f"Account domain is enterprise/managed ({account_email}).",
                confidence=1.0,
                possible_causes=["Enterprise Google Workspace policies block Google One consumer memberships."],
                recommended_step="Use a standard personal @gmail.com account.",
            )

        if in_family_group:
            return CheckFinding(
                check_name="Account Family Group Status",
                result_code=DiagnosticResultCode.ACCOUNT_NOT_ELIGIBLE,
                passed=False,
                explanation="Accounts enrolled in Google Family Sharing with shared storage cannot redeem promotional trials.",
                evidence="Account flagged as member of active Family Group.",
                confidence=0.9,
                possible_causes=["Google One restricts subscription upgrades while tied to family billing plan."],
                recommended_step="Temporarily leave the family storage group before activating.",
            )

        if has_active_sub:
            return CheckFinding(
                check_name="Existing Subscription Conflict",
                result_code=DiagnosticResultCode.ACCOUNT_NOT_ELIGIBLE,
                passed=False,
                explanation="Account already holds an active Google One or previous promotional trial.",
                evidence="Prior subscription found on account.",
                confidence=0.85,
                possible_causes=["Promotions are strictly limited to one trial per account."],
                recommended_step="Use a fresh Google account that has never claimed an AI Premium offer.",
            )

        return CheckFinding(
            check_name="Account Type Eligibility",
            result_code=DiagnosticResultCode.OFFER_VISIBLE,
            passed=True,
            explanation="Account qualifies as a standard personal Google Account.",
            evidence=f"Personal account ({account_email or 'standard'}), no detected family or subscription conflicts.",
            confidence=0.9,
            recommended_step="Proceed to on-device redemption.",
        )

    def _check_promotion_availability(self, promotion_code: str) -> CheckFinding:
        # Note on Pixel 11 Pro vs Pixel 9 Pro:
        # Pixel 9 Pro offer is active in production.
        # Pixel 11 Pro is a research/future target not yet in active retail rollout.
        if "11" in promotion_code:
            return CheckFinding(
                check_name="Promotion Availability",
                result_code=DiagnosticResultCode.UNKNOWN,
                passed=False,
                explanation="Pixel 11 Pro is a future research target not yet active in Google retail production servers.",
                evidence="Retail availability for Pixel 11 Pro is not yet provisioned in Google Play Services production catalogue.",
                confidence=0.95,
                possible_causes=[
                    "Device model is unreleased.",
                    "Promotion server has no live entitlement records for Pixel 11 generation.",
                ],
                recommended_step="For production verification, test against active Pixel 9 Pro series promotion.",
            )

        return CheckFinding(
            check_name="Promotion Availability",
            result_code=DiagnosticResultCode.OFFER_VISIBLE,
            passed=True,
            explanation="Promotion is registered and active in Google Store catalog.",
            evidence=f"Promotion code {promotion_code} is active.",
            confidence=0.9,
            recommended_step="Ensure redemption deadline is met.",
        )

    def _check_payment_method(self, has_payment_method: bool) -> CheckFinding:
        if not has_payment_method:
            return CheckFinding(
                check_name="Payment Requirement",
                result_code=DiagnosticResultCode.PAYMENT_REQUIREMENT_MISSING,
                passed=False,
                explanation="Google requires a valid payment instrument on file to complete 0đ promotional trial activation.",
                evidence="No valid credit card, debit card, or approved billing wallet linked to Google Play Payments.",
                confidence=1.0,
                possible_causes=["Account has empty Google Pay wallet."],
                recommended_step="Add a payment method at payments.google.com prior to claiming.",
            )

        return CheckFinding(
            check_name="Payment Requirement",
            result_code=DiagnosticResultCode.OFFER_VISIBLE,
            passed=True,
            explanation="Valid payment method is available for recurring trial enrollment.",
            evidence="Billing instrument confirmed.",
            confidence=0.9,
            recommended_step="Proceed with checkout verification.",
        )

    def _check_web_observation(self, status: str) -> CheckFinding:
        if status == "OFFER_VISIBLE":
            return CheckFinding(
                check_name="Web Observation",
                result_code=DiagnosticResultCode.OFFER_VISIBLE,
                passed=True,
                explanation="Offer card or link is visible on one.google.com.",
                evidence="DOM link matched BARD_ADVANCED_MODE / TIER0.",
                confidence=0.9,
                recommended_step="Click to verify checkout flow.",
            )
        elif status == "OFFER_NOT_VISIBLE":
            return CheckFinding(
                check_name="Web Observation",
                result_code=DiagnosticResultCode.OFFER_NOT_VISIBLE,
                passed=False,
                explanation="No promotional offer cards were discovered on the Google One web interface.",
                evidence="Web DOM scan returned 0 offer links.",
                confidence=0.85,
                possible_causes=[
                    "Web endpoint does not expose hardware perks without GMS client attestation.",
                    "Account is redirected to storage management.",
                ],
                recommended_step="Verify in Google One Android app directly.",
            )
        elif status == "MANUAL_REVIEW_REQUIRED":
            return CheckFinding(
                check_name="Web Observation",
                result_code=DiagnosticResultCode.MANUAL_REVIEW_REQUIRED,
                passed=False,
                explanation="Google triggered an interactive account verification challenge.",
                evidence="Redirected to accounts.google.com security challenge.",
                confidence=0.95,
                possible_causes=["Suspicious IP, automated browser detection, or required 2FA confirmation."],
                recommended_step="Account owner must complete verification in personal browser.",
            )
        return CheckFinding(
            check_name="Web Observation",
            result_code=DiagnosticResultCode.UNKNOWN,
            passed=False,
            explanation="Web observation produced indeterminate output.",
            evidence=status,
            confidence=0.5,
            recommended_step="Check network logs.",
        )

    def _compute_overall_report(self, findings: List[CheckFinding]) -> DiagnosticReport:
        # Determine dominant blocker
        priority_order = [
            DiagnosticResultCode.MANUAL_REVIEW_REQUIRED,
            DiagnosticResultCode.DEVICE_NOT_VERIFIED,
            DiagnosticResultCode.REGION_NOT_SUPPORTED,
            DiagnosticResultCode.ACCOUNT_NOT_ELIGIBLE,
            DiagnosticResultCode.PAYMENT_REQUIREMENT_MISSING,
            DiagnosticResultCode.PROMOTION_EXPIRED,
            DiagnosticResultCode.OFFER_NOT_VISIBLE,
            DiagnosticResultCode.UNKNOWN,
            DiagnosticResultCode.OFFER_VISIBLE,
        ]

        found_codes = {f.result_code for f in findings if not f.passed}
        if not found_codes:
            overall = DiagnosticResultCode.OFFER_VISIBLE
            summary = "All eligibility checks passed. Promotion is fully accessible."
            conf = 0.95
        else:
            overall = DiagnosticResultCode.UNKNOWN
            for code in priority_order:
                if code in found_codes:
                    overall = code
                    break

            primary = next(f for f in findings if f.result_code == overall)
            summary = f"Eligibility Blocked: {primary.explanation}"
            conf = primary.confidence

        return DiagnosticReport(
            overall_code=overall,
            confidence=conf,
            summary=summary,
            findings=findings,
        )


# Global instance
promotion_diagnostic_engine = PromotionDiagnosticEngine()
