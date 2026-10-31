"""
Redemption Verification Service.

Assesses user-submitted redemption evidence and determines verification status.

STATUS CODES:
- CLAIM_NOT_STARTED
- CLAIM_IN_PROGRESS
- CLAIM_REPORTED_SUCCESS
- CLAIM_VERIFIED
- CLAIM_FAILED
- CLAIM_EXPIRED
- MANUAL_REVIEW_REQUIRED

CRITICAL RULE:
A screenshot or self-report supplied by a user is classified as USER_REPORTED
unless independently verified against official Google Play / GMS records.
Never fabricate CLAIM_VERIFIED status without authoritative proof.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Optional

from database import get_db
from models import ClaimSession, ClaimState, RedemptionEvidence

logger = logging.getLogger(__name__)


class RedemptionStatus(str, Enum):
    CLAIM_NOT_STARTED = "CLAIM_NOT_STARTED"
    CLAIM_IN_PROGRESS = "CLAIM_IN_PROGRESS"
    CLAIM_REPORTED_SUCCESS = "CLAIM_REPORTED_SUCCESS"
    CLAIM_VERIFIED = "CLAIM_VERIFIED"
    CLAIM_FAILED = "CLAIM_FAILED"
    CLAIM_EXPIRED = "CLAIM_EXPIRED"
    MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"


@dataclass
class VerificationAssessment:
    status: RedemptionStatus
    evidence_type: str
    is_authoritative: bool
    explanation: str
    recommended_action: str


class RedemptionVerificationService:
    """Verifies evidence provided after a redemption attempt."""

    def evaluate_user_report(
        self,
        session_id: int,
        user_response: str,
        screenshot_path: Optional[str] = None,
    ) -> VerificationAssessment:
        clean_resp = user_response.strip().lower()

        # Check for user reporting failure or issues
        failure_keywords = [
            "failed", "error", "not available", "ineligible", "khong duoc", "that bai",
            "blocked", "rejected", "denied", "expired"
        ]
        if any(kw in clean_resp for kw in failure_keywords):
            self._record_evidence(session_id, "USER_REPORTED_TEXT", user_response, "REJECTED", "User reported claim failure")
            return VerificationAssessment(
                status=RedemptionStatus.CLAIM_FAILED,
                evidence_type="USER_REPORTED_TEXT",
                is_authoritative=False,
                explanation="User reported an error or disqualification during Google One redemption.",
                recommended_action="Review error message in Google One app; verify country and account eligibility.",
            )

        # Check for user reporting payment requirement
        payment_keywords = ["payment", "card", "momo", "the", "phuong thuc thanh toan"]
        if any(kw in clean_resp for kw in payment_keywords) and "add" in clean_resp or "them" in clean_resp:
            self._record_evidence(session_id, "USER_REPORTED_TEXT", user_response, "PENDING", "Payment method required")
            return VerificationAssessment(
                status=RedemptionStatus.MANUAL_REVIEW_REQUIRED,
                evidence_type="USER_REPORTED_TEXT",
                is_authoritative=False,
                explanation="Google requires adding a payment method before activating trial auto-renewal.",
                recommended_action="Add credit/debit card to Google Play Wallet at payments.google.com and retry.",
            )

        # Check for user reporting success
        success_keywords = [
            "success", "done", "active", "subscribed", "thanh cong", "nhan duoc", "da nhan", "ok", "yes"
        ]
        if any(kw in clean_resp for kw in success_keywords) or screenshot_path:
            self._record_evidence(
                session_id,
                "SCREENSHOT" if screenshot_path else "USER_REPORTED_TEXT",
                screenshot_path or user_response,
                "USER_REPORTED",
                "User reported activation success",
            )
            return VerificationAssessment(
                status=RedemptionStatus.CLAIM_REPORTED_SUCCESS,
                evidence_type="USER_SUBMITTED_SCREENSHOT" if screenshot_path else "USER_SELF_REPORT",
                is_authoritative=False,  # Still user-reported until verified
                explanation="User reported successful redemption. Labeled as USER_REPORTED (unverified by server cryptographic API).",
                recommended_action="Confirm active status in Google One app ➔ Settings ➔ Membership.",
            )

        return VerificationAssessment(
            status=RedemptionStatus.CLAIM_IN_PROGRESS,
            evidence_type="USER_REPORTED_TEXT",
            is_authoritative=False,
            explanation="Reported response is indeterminate.",
            recommended_action="Complete checkout in Google One app and report final status.",
        )

    def _record_evidence(
        self,
        session_id: int,
        evidence_type: str,
        payload: str,
        status: str,
        notes: str,
    ) -> None:
        try:
            with get_db() as db:
                ev = RedemptionEvidence(
                    session_id=session_id,
                    evidence_type=evidence_type,
                    evidence_payload=payload,
                    verification_status=status,
                    reviewer_notes=notes,
                    created_at=datetime.now(timezone.utc),
                )
                db.add(ev)
        except Exception as exc:
            logger.warning("Failed to record redemption evidence: %s", exc)


# Global instance
redemption_verification_service = RedemptionVerificationService()
