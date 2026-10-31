"""
Unit tests for Claim State Machine, Workflow & Redemption Verification.
Covers requirements 11-17:
- Claim state transitions
- Claim cancellation
- Interrupted claim recovery
- Duplicate claim prevention
- Redemption reported success
- Redemption verification
- Screenshot evidence classification
"""

import uuid
import pytest
from database import init_db
from models import ClaimState
from redemption_verification import RedemptionStatus, redemption_verification_service
from redemption_workflow import redemption_workflow
from session_manager import (
    DuplicateClaimSessionError,
    InvalidStateTransitionError,
    session_manager,
)


@pytest.fixture(autouse=True)
def setup_db():
    init_db()


def test_claim_state_transitions():
    """Requirement 11: Valid progression through claim states."""
    uid = uuid.uuid4().int % 10000000
    session = session_manager.create_claim_session(telegram_id=uid)
    assert session.current_state == ClaimState.IDLE.value

    # IDLE -> PROMOTION_SELECTED
    s1 = session_manager.transition_state(session.id, ClaimState.PROMOTION_SELECTED, "STEP_1")
    assert s1 == ClaimState.PROMOTION_SELECTED

    # PROMOTION_SELECTED -> DEVICE_SELECTED
    s2 = session_manager.transition_state(session.id, ClaimState.DEVICE_SELECTED, "STEP_2")
    assert s2 == ClaimState.DEVICE_SELECTED

    # Invalid jump (skipping steps directly to CLAIM_VERIFIED) must raise
    with pytest.raises(InvalidStateTransitionError):
        session_manager.transition_state(session.id, ClaimState.CLAIM_VERIFIED, "ILLEGAL_JUMP")


def test_claim_cancellation():
    """Requirement 12: Cancellation from any active state."""
    uid = uuid.uuid4().int % 10000000
    session = session_manager.create_claim_session(telegram_id=uid)
    session_manager.transition_state(session.id, ClaimState.PROMOTION_SELECTED, "STEP_1")

    session_manager.cancel_session(session.id, "User cancelled")
    active = session_manager.get_active_session(uid)
    assert active is None  # no longer active


def test_interrupted_claim_recovery():
    """Requirement 13: Resuming an active interrupted session."""
    uid = uuid.uuid4().int % 10000000
    session = session_manager.create_claim_session(telegram_id=uid)
    session_manager.transition_state(session.id, ClaimState.PROMOTION_SELECTED, "STEP_1")

    # Re-invoking start_claim resumes active session
    resumed, msg = redemption_workflow.start_claim(uid)
    assert resumed.id == session.id
    assert "Resuming" in msg
    assert resumed.current_state == ClaimState.PROMOTION_SELECTED.value


def test_duplicate_claim_prevention():
    """Requirement 14: Prevent duplicate active claim sessions for same user and promo."""
    uid = uuid.uuid4().int % 10000000
    session = session_manager.create_claim_session(telegram_id=uid, promotion_id=1)

    with pytest.raises(DuplicateClaimSessionError):
        session_manager.create_claim_session(telegram_id=uid, promotion_id=1)


def test_redemption_reported_success_and_screenshot_classification():
    """Requirements 15, 16, 17: User report and screenshot verification."""
    uid = uuid.uuid4().int % 10000000
    session = session_manager.create_claim_session(telegram_id=uid)

    # User reports success via text
    assessment_text = redemption_verification_service.evaluate_user_report(
        session_id=session.id,
        user_response="I successfully claimed the Google One trial!",
    )
    assert assessment_text.status == RedemptionStatus.CLAIM_REPORTED_SUCCESS
    assert assessment_text.is_authoritative is False  # Must be labeled USER_REPORTED
    assert "USER_REPORTED" in assessment_text.explanation

    # User submits a screenshot
    assessment_img = redemption_verification_service.evaluate_user_report(
        session_id=session.id,
        user_response="Attached screenshot of membership",
        screenshot_path="/tmp/fake_proof.png",
    )
    assert assessment_img.status == RedemptionStatus.CLAIM_REPORTED_SUCCESS
    assert assessment_img.evidence_type == "USER_SUBMITTED_SCREENSHOT"
    assert assessment_img.is_authoritative is False  # Screenshot alone is not cryptographic server proof
