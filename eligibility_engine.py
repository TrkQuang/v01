"""
Authoritative Eligibility Evaluation Engine.

Evaluates eligibility across:
1. Device Eligibility (DEVICE_ELIGIBLE, DEVICE_INELIGIBLE, DEVICE_UNKNOWN)
2. Region Eligibility (REGION_ELIGIBLE, REGION_INELIGIBLE, REGION_UNKNOWN)
3. Account Eligibility (ACCOUNT_ELIGIBLE, ACCOUNT_INELIGIBLE, ACCOUNT_UNKNOWN)
4. Payment Requirement (PAYMENT_REQUIREMENT_MISSING)
5. Promotion Validity (PROMOTION_EXPIRED, PROMOTION_UNAVAILABLE)
6. Complex Status (MANUAL_REVIEW_REQUIRED)

Never assumes personal Gmail is automatically eligible without confirmation.
Never infers eligibility from country name alone without evidence.
"""

import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from country_service import country_service
from device_verification import DeviceTier, DeviceVerificationReport
from promotion_catalog import PromotionItem

logger = logging.getLogger(__name__)


class EligibilityCode(str, Enum):
    ACCOUNT_ELIGIBLE = "ACCOUNT_ELIGIBLE"
    ACCOUNT_INELIGIBLE = "ACCOUNT_INELIGIBLE"
    ACCOUNT_UNKNOWN = "ACCOUNT_UNKNOWN"
    REGION_ELIGIBLE = "REGION_ELIGIBLE"
    REGION_INELIGIBLE = "REGION_INELIGIBLE"
    REGION_UNKNOWN = "REGION_UNKNOWN"
    DEVICE_ELIGIBLE = "DEVICE_ELIGIBLE"
    DEVICE_INELIGIBLE = "DEVICE_INELIGIBLE"
    DEVICE_UNKNOWN = "DEVICE_UNKNOWN"
    PAYMENT_REQUIREMENT_MISSING = "PAYMENT_REQUIREMENT_MISSING"
    PROMOTION_EXPIRED = "PROMOTION_EXPIRED"
    PROMOTION_UNAVAILABLE = "PROMOTION_UNAVAILABLE"
    MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"


@dataclass
class CheckAssessment:
    category: str  # DEVICE, REGION, ACCOUNT, PROMOTION, PAYMENT
    code: EligibilityCode
    passed: bool
    summary: str
    evidence: str
    confidence: float
    next_step: str

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["code"] = self.code.value
        return d


@dataclass
class EligibilityEvaluationReport:
    is_eligible: bool
    primary_code: EligibilityCode
    overall_summary: str
    confidence: float
    assessments: List[CheckAssessment] = field(default_factory=list)
    evaluated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_eligible": self.is_eligible,
            "primary_code": self.primary_code.value,
            "overall_summary": self.overall_summary,
            "confidence": self.confidence,
            "assessments": [a.to_dict() for a in self.assessments],
            "evaluated_at": self.evaluated_at,
        }


class EligibilityEngine:
    """Evaluates promotion prerequisites against user-supplied and verified evidence."""

    def evaluate(
        self,
        promotion: PromotionItem,
        device_report: DeviceVerificationReport,
        country_code: str,
        account_email: Optional[str] = None,
        account_type: str = "UNKNOWN",  # PERSONAL, WORKSPACE, UNKNOWN
        has_active_google_one: Optional[bool] = None,
        has_redeemed_prior_trial: Optional[bool] = None,
        has_payment_method: Optional[bool] = None,
        web_observed_status: Optional[str] = None,
    ) -> EligibilityEvaluationReport:
        assessments: List[CheckAssessment] = []

        # 1. Promotion Validity & Expiration Check
        promo_assessment = self._assess_promotion_validity(promotion)
        assessments.append(promo_assessment)

        # 2. Regional Store Eligibility Check
        region_assessment = self._assess_region(promotion, country_code)
        assessments.append(region_assessment)

        # 3. Device Hardware Eligibility Check
        device_assessment = self._assess_device(promotion, device_report)
        assessments.append(device_assessment)

        # 4. Account Type & Conflict Check
        acct_assessment = self._assess_account(
            account_email=account_email,
            account_type=account_type,
            has_active_google_one=has_active_google_one,
            has_redeemed_prior_trial=has_redeemed_prior_trial,
        )
        assessments.append(acct_assessment)

        # 5. Payment Requirement Check
        if has_payment_method is not None:
            pay_assessment = self._assess_payment(has_payment_method)
            assessments.append(pay_assessment)

        # 6. Web Observation Indicator (if probe was performed)
        if web_observed_status:
            web_assessment = self._assess_web_observation(web_observed_status)
            assessments.append(web_assessment)

        return self._synthesize_overall_report(assessments)

    def _assess_promotion_validity(self, promotion: PromotionItem) -> CheckAssessment:
        if promotion.is_expired():
            return CheckAssessment(
                category="PROMOTION",
                code=EligibilityCode.PROMOTION_EXPIRED,
                passed=False,
                summary=f"Promotion '{promotion.promotion_name}' has expired.",
                evidence=f"Expiration date {promotion.expiration_date} has passed.",
                confidence=1.0,
                next_step="Check Google Store for current active device promotions.",
            )

        if promotion.source_status == "UNVERIFIED_RESEARCH_TARGET":
            return CheckAssessment(
                category="PROMOTION",
                code=EligibilityCode.PROMOTION_UNAVAILABLE,
                passed=False,
                summary="Promotion is an unreleased research target not yet active in retail production.",
                evidence=f"Source status: {promotion.source_status}.",
                confidence=0.95,
                next_step="Select an active retail promotion (e.g. Pixel 9 Pro 12M AI Premium).",
            )

        return CheckAssessment(
            category="PROMOTION",
            code=EligibilityCode.PROMOTION_UNAVAILABLE if not promotion.active else EligibilityCode.DEVICE_ELIGIBLE,
            passed=promotion.active,
            summary="Promotion is currently active and within its valid redemption window.",
            evidence=f"Active until {promotion.expiration_date or 'Indefinite'}.",
            confidence=0.9,
            next_step="Verify device and account conditions.",
        )

    def _assess_region(self, promotion: PromotionItem, country_code: str) -> CheckAssessment:
        if not country_code or country_code.upper() == "UNKNOWN":
            return CheckAssessment(
                category="REGION",
                code=EligibilityCode.REGION_UNKNOWN,
                passed=False,
                summary="Country has not been selected or verified.",
                evidence="No country code specified.",
                confidence=0.5,
                next_step="Select your Google Play Store country profile.",
            )

        c_info = country_service.check_region_eligibility(country_code)
        c_status = c_info.get("status")

        if c_status == "INELIGIBLE" or not promotion.supports_country(country_code):
            return CheckAssessment(
                category="REGION",
                code=EligibilityCode.REGION_INELIGIBLE,
                passed=False,
                summary=f"Region '{c_info.get('country_name', country_code)}' ({country_code}) is not eligible for this promotion.",
                evidence=f"Promotion supports: {', '.join(promotion.supported_countries)}. User country: {country_code}.",
                confidence=0.95,
                next_step="Redemption requires a Google account with billing in a supported country.",
            )

        if c_status == "ELIGIBLE" and promotion.supports_country(country_code):
            return CheckAssessment(
                category="REGION",
                code=EligibilityCode.REGION_ELIGIBLE,
                passed=True,
                summary=f"Country '{c_info.get('country_name', country_code)}' ({country_code}) is officially supported.",
                evidence=c_info.get("evidence", ""),
                confidence=0.95,
                next_step="Ensure Google Play billing address matches this territory.",
            )

        return CheckAssessment(
            category="REGION",
            code=EligibilityCode.REGION_UNKNOWN,
            passed=False,
            summary=f"Regional promotional status for '{country_code}' is unverified.",
            evidence=c_info.get("evidence", "Unconfirmed region."),
            confidence=0.5,
            next_step="Consult local Google Store promotion terms.",
        )

    def _assess_device(self, promotion: PromotionItem, device: DeviceVerificationReport) -> CheckAssessment:
        # Check model compatibility
        supports_model = promotion.supports_device(device.reported_model)

        if device.device_tier == DeviceTier.DESKTOP_BROWSER:
            return CheckAssessment(
                category="DEVICE",
                code=EligibilityCode.DEVICE_INELIGIBLE,
                passed=False,
                summary="Desktop browser environments cannot claim Google Pixel hardware promotions.",
                evidence="Host is running a desktop web browser with zero Android or Titan M2 attestation.",
                confidence=1.0,
                next_step="Switch to an eligible physical Google Pixel smartphone.",
            )

        if device.device_tier == DeviceTier.BROWSER_MOBILE_EMULATION:
            return CheckAssessment(
                category="DEVICE",
                code=EligibilityCode.DEVICE_INELIGIBLE,
                passed=False,
                summary="Browser mobile emulation cannot generate hardware Play Integrity attestation tokens.",
                evidence="Session is using Chrome CDP mobile emulation overrides.",
                confidence=1.0,
                next_step="Hardware offers must be claimed natively via the Google One app on a physical Pixel.",
            )

        if device.device_tier == DeviceTier.ANDROID_EMULATOR:
            return CheckAssessment(
                category="DEVICE",
                code=EligibilityCode.DEVICE_INELIGIBLE,
                passed=False,
                summary="Android emulators fail Google Play Integrity device certification.",
                evidence="Detected virtual kernel drivers (goldfish/ranchu) via ADB.",
                confidence=0.95,
                next_step="Connect a physical Pixel smartphone with factory locked bootloader.",
            )

        if device.is_user_reported and not device.is_hardware_verified:
            if not supports_model:
                return CheckAssessment(
                    category="DEVICE",
                    code=EligibilityCode.DEVICE_INELIGIBLE,
                    passed=False,
                    summary=f"Reported model '{device.reported_model}' is not supported by '{promotion.promotion_name}'.",
                    evidence=f"Supported models: {', '.join(promotion.supported_device_models)}.",
                    confidence=0.9,
                    next_step="Check if your device matches an eligible flagship Pro tier.",
                )

            return CheckAssessment(
                category="DEVICE",
                code=EligibilityCode.DEVICE_UNKNOWN,
                passed=True,  # conditionally allowed to proceed with explicit warning
                summary=f"Device '{device.reported_model}' is supported, but authenticity is USER_REPORTED (unverified by ADB).",
                evidence="Hardware attestation has not been cryptographically verified through direct inspection.",
                confidence=0.7,
                next_step="Proceed to official redemption on your physical device to let Google verify hardware.",
            )

        if device.device_tier == DeviceTier.VERIFIED_PIXEL:
            if not supports_model:
                return CheckAssessment(
                    category="DEVICE",
                    code=EligibilityCode.DEVICE_INELIGIBLE,
                    passed=False,
                    summary=f"Verified Pixel model '{device.reported_model}' is not eligible for this specific tier.",
                    evidence=f"Requires one of: {', '.join(promotion.supported_device_models)}.",
                    confidence=0.95,
                    next_step="Select a promotion matching your device model.",
                )

            return CheckAssessment(
                category="DEVICE",
                code=EligibilityCode.DEVICE_ELIGIBLE,
                passed=True,
                summary=f"Verified Google Pixel device '{device.reported_model}' with locked bootloader confirmed.",
                evidence="Hardware attestation markers, locked verified boot, and GMS confirmed via ADB.",
                confidence=0.95,
                next_step="Launch Google One app on the device.",
            )

        return CheckAssessment(
            category="DEVICE",
            code=EligibilityCode.DEVICE_UNKNOWN,
            passed=False,
            summary="Device authenticity and model cannot be determined.",
            evidence=f"Device tier is {device.device_tier.value}.",
            confidence=0.4,
            next_step="Connect your device via USB with ADB debugging enabled or select model manually.",
        )

    def _assess_account(
        self,
        account_email: Optional[str],
        account_type: str,
        has_active_google_one: Optional[bool],
        has_redeemed_prior_trial: Optional[bool],
    ) -> CheckAssessment:
        if account_type == "WORKSPACE" or (account_email and not account_email.lower().endswith("@gmail.com")):
            return CheckAssessment(
                category="ACCOUNT",
                code=EligibilityCode.ACCOUNT_INELIGIBLE,
                passed=False,
                summary="Google Workspace (business/education) accounts are ineligible for Google One promotional trials.",
                evidence=f"Enterprise account domain detected: {account_email or 'Workspace'}.",
                confidence=1.0,
                next_step="Redeem using a standard personal Google Account (@gmail.com).",
            )

        if has_active_google_one is True:
            return CheckAssessment(
                category="ACCOUNT",
                code=EligibilityCode.ACCOUNT_INELIGIBLE,
                passed=False,
                summary="Accounts with existing active Google One subscriptions cannot claim device promotional trials.",
                evidence="Active Google One membership detected.",
                confidence=0.85,
                next_step="Promotional trials are restricted to new or upgrading personal accounts.",
            )

        if has_redeemed_prior_trial is True:
            return CheckAssessment(
                category="ACCOUNT",
                code=EligibilityCode.ACCOUNT_INELIGIBLE,
                passed=False,
                summary="Account has previously redeemed a Google One AI promotional trial.",
                evidence="Prior trial redemption recorded.",
                confidence=0.85,
                next_step="Google restricts AI tier promotions to one per account lifetime.",
            )

        if account_type == "PERSONAL":
            return CheckAssessment(
                category="ACCOUNT",
                code=EligibilityCode.ACCOUNT_ELIGIBLE,
                passed=True,
                summary="Personal Google Account meets account-type criteria.",
                evidence="Standard personal @gmail.com account.",
                confidence=0.85,
                next_step="Confirm in Google One app that no family group restrictions apply.",
            )

        return CheckAssessment(
            category="ACCOUNT",
            code=EligibilityCode.ACCOUNT_UNKNOWN,
            passed=True,  # conditionally allowed to proceed with manual verification
            summary="Account status is unconfirmed by official Google interface.",
            evidence="Account state has not been verified via Google Sign-In.",
            confidence=0.5,
            next_step="Sign in directly on Google's redemption page to let Google verify eligibility.",
        )

    def _assess_payment(self, has_payment_method: bool) -> CheckAssessment:
        if not has_payment_method:
            return CheckAssessment(
                category="PAYMENT",
                code=EligibilityCode.PAYMENT_REQUIREMENT_MISSING,
                passed=False,
                summary="Google Play requires a payment method on file to set up trial auto-renewal.",
                evidence="No credit card, debit card, or approved billing wallet found on Google Play account.",
                confidence=0.95,
                next_step="Add a payment method at payments.google.com before completing checkout.",
            )

        return CheckAssessment(
            category="PAYMENT",
            code=EligibilityCode.ACCOUNT_ELIGIBLE,
            passed=True,
            summary="Payment instrument is available for $0 trial checkout.",
            evidence="Payment method confirmed.",
            confidence=0.9,
            next_step="Proceed with checkout verification.",
        )

    def _assess_web_observation(self, status: str) -> CheckAssessment:
        if status == "SECURITY_CHALLENGE" or status == "LOGIN_REQUIRED":
            return CheckAssessment(
                category="OBSERVATION",
                code=EligibilityCode.MANUAL_REVIEW_REQUIRED,
                passed=False,
                summary="Google requires direct user login/security verification.",
                evidence=f"Web prober encountered: {status}.",
                confidence=0.95,
                next_step="Account owner must complete verification directly in the Google One app or official browser.",
            )

        return CheckAssessment(
            category="OBSERVATION",
            code=EligibilityCode.DEVICE_ELIGIBLE,
            passed=True,
            summary="Web landing is accessible without security block.",
            evidence=status,
            confidence=0.7,
            next_step="Proceed to official redemption.",
        )

    def _synthesize_overall_report(self, assessments: List[CheckAssessment]) -> EligibilityEvaluationReport:
        failed = [a for a in assessments if not a.passed]
        if not failed:
            return EligibilityEvaluationReport(
                is_eligible=True,
                primary_code=EligibilityCode.DEVICE_ELIGIBLE,
                overall_summary="All eligibility criteria satisfied. You are ready to redeem.",
                confidence=0.9,
                assessments=assessments,
            )

        # Priority order for failure codes
        priority = [
            EligibilityCode.PROMOTION_EXPIRED,
            EligibilityCode.PROMOTION_UNAVAILABLE,
            EligibilityCode.REGION_INELIGIBLE,
            EligibilityCode.DEVICE_INELIGIBLE,
            EligibilityCode.ACCOUNT_INELIGIBLE,
            EligibilityCode.PAYMENT_REQUIREMENT_MISSING,
            EligibilityCode.MANUAL_REVIEW_REQUIRED,
            EligibilityCode.DEVICE_UNKNOWN,
            EligibilityCode.REGION_UNKNOWN,
            EligibilityCode.ACCOUNT_UNKNOWN,
        ]

        primary_finding = failed[0]
        for p_code in priority:
            matching = [f for f in failed if f.code == p_code]
            if matching:
                primary_finding = matching[0]
                break

        return EligibilityEvaluationReport(
            is_eligible=False,
            primary_code=primary_finding.code,
            overall_summary=primary_finding.summary,
            confidence=primary_finding.confidence,
            assessments=assessments,
        )


# Global instance
eligibility_engine = EligibilityEngine()
