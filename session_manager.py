"""
Claim State Machine & Session Manager.

Manages deterministic state transitions for user claim workflows:
IDLE -> PROMOTION_SELECTED -> DEVICE_SELECTED -> COUNTRY_SELECTED
     -> ELIGIBILITY_CHECKING -> (ELIGIBILITY_PASSED | ELIGIBILITY_BLOCKED | ELIGIBILITY_UNKNOWN)
     -> REDEMPTION_READY -> USER_ACTION_REQUIRED -> CLAIM_IN_PROGRESS
     -> (CLAIM_REPORTED_SUCCESS | CLAIM_FAILED) -> CLAIM_VERIFIED / CANCELLED / EXPIRED

Prevents invalid transitions, duplicate sessions, and step skipping.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple

from database import get_db, get_or_create_user
from models import ClaimSession, ClaimState, ClaimStep, User

logger = logging.getLogger(__name__)

# Valid state transitions graph
VALID_TRANSITIONS: Dict[ClaimState, Set[ClaimState]] = {
    ClaimState.IDLE: {ClaimState.PROMOTION_SELECTED, ClaimState.CANCELLED},
    ClaimState.PROMOTION_SELECTED: {ClaimState.PROMOTION_SELECTED, ClaimState.DEVICE_SELECTED, ClaimState.CANCELLED},
    ClaimState.DEVICE_SELECTED: {ClaimState.DEVICE_SELECTED, ClaimState.COUNTRY_SELECTED, ClaimState.CANCELLED},
    ClaimState.COUNTRY_SELECTED: {ClaimState.COUNTRY_SELECTED, ClaimState.ELIGIBILITY_CHECKING, ClaimState.CANCELLED},
    ClaimState.ELIGIBILITY_CHECKING: {
        ClaimState.ELIGIBILITY_PASSED,
        ClaimState.ELIGIBILITY_BLOCKED,
        ClaimState.ELIGIBILITY_UNKNOWN,
        ClaimState.CANCELLED,
    },
    ClaimState.ELIGIBILITY_PASSED: {ClaimState.REDEMPTION_READY, ClaimState.ELIGIBILITY_CHECKING, ClaimState.CANCELLED},
    ClaimState.ELIGIBILITY_UNKNOWN: {ClaimState.REDEMPTION_READY, ClaimState.ELIGIBILITY_CHECKING, ClaimState.CANCELLED},
    ClaimState.ELIGIBILITY_BLOCKED: {ClaimState.ELIGIBILITY_CHECKING, ClaimState.CANCELLED, ClaimState.IDLE},
    ClaimState.REDEMPTION_READY: {ClaimState.USER_ACTION_REQUIRED, ClaimState.CANCELLED},
    ClaimState.USER_ACTION_REQUIRED: {
        ClaimState.CLAIM_IN_PROGRESS,
        ClaimState.CLAIM_REPORTED_SUCCESS,
        ClaimState.CLAIM_FAILED,
        ClaimState.CANCELLED,
    },
    ClaimState.CLAIM_IN_PROGRESS: {
        ClaimState.CLAIM_REPORTED_SUCCESS,
        ClaimState.CLAIM_FAILED,
        ClaimState.CANCELLED,
    },
    ClaimState.CLAIM_REPORTED_SUCCESS: {
        ClaimState.CLAIM_VERIFIED,
        ClaimState.CLAIM_FAILED,
        ClaimState.CANCELLED,
    },
    ClaimState.CLAIM_VERIFIED: set(),
    ClaimState.CLAIM_FAILED: {ClaimState.IDLE, ClaimState.CANCELLED},
    ClaimState.CANCELLED: {ClaimState.IDLE},
    ClaimState.EXPIRED: {ClaimState.IDLE},
}


class InvalidStateTransitionError(Exception):
    """Raised when an illegal transition is attempted."""


class DuplicateClaimSessionError(Exception):
    """Raised when an active session already exists for the same user and promotion."""


class SessionManager:
    """Handles claim workflow lifecycle, persistence, and transitions."""

    def get_active_session(self, telegram_id: int | str) -> Optional[ClaimSession]:
        """Fetch active in-progress claim session for user."""
        with get_db() as db:
            user = get_or_create_user(db, telegram_id)
            session = (
                db.query(ClaimSession)
                .filter(
                    ClaimSession.user_id == user.id,
                    ClaimSession.is_active == True,
                    ClaimSession.current_state.notin_([
                        ClaimState.CLAIM_VERIFIED.value,
                        ClaimState.CLAIM_FAILED.value,
                        ClaimState.CANCELLED.value,
                        ClaimState.EXPIRED.value,
                    ]),
                )
                .order_by(ClaimSession.created_at.desc())
                .first()
            )
            if session:
                _ = (session.id, session.session_uuid, session.current_state, session.user_id, session.promotion_id)
            return session

    def create_claim_session(self, telegram_id: int | str, promotion_id: Optional[int] = None) -> ClaimSession:
        """Initialize a new claim session enforcing single active session per user."""
        with get_db() as db:
            user = get_or_create_user(db, telegram_id)

            # Check for existing active session
            existing = (
                db.query(ClaimSession)
                .filter(
                    ClaimSession.user_id == user.id,
                    ClaimSession.is_active == True,
                    ClaimSession.current_state.notin_([
                        ClaimState.CLAIM_VERIFIED.value,
                        ClaimState.CLAIM_FAILED.value,
                        ClaimState.CANCELLED.value,
                    ]),
                )
                .first()
            )
            if existing:
                if promotion_id and existing.promotion_id == promotion_id:
                    raise DuplicateClaimSessionError(
                        f"An active claim session ({existing.session_uuid[:8]}) already exists for this promotion."
                    )
                # Deactivate older stale session
                existing.is_active = False

            now = datetime.now(timezone.utc)
            session = ClaimSession(
                session_uuid=str(uuid.uuid4()),
                user_id=user.id,
                promotion_id=promotion_id,
                selected_country_code=user.selected_country_code or "US",
                current_state=ClaimState.IDLE.value,
                is_active=True,
                created_at=now,
                updated_at=now,
            )
            db.add(session)
            db.flush()

            # Record initial step
            step = ClaimStep(
                session_id=session.id,
                step_name="SESSION_INIT",
                from_state=ClaimState.IDLE.value,
                to_state=ClaimState.IDLE.value,
                notes="Claim session created.",
                created_at=now,
            )
            db.add(step)
            db.commit()
            db.refresh(session)
            _ = (session.id, session.session_uuid, session.current_state, session.user_id, session.promotion_id)
            return session

    def transition_state(
        self,
        session_id: int,
        target_state: ClaimState,
        step_name: str,
        notes: Optional[str] = None,
    ) -> ClaimState:
        """Validate and commit a state machine transition."""
        with get_db() as db:
            session = db.query(ClaimSession).filter(ClaimSession.id == session_id).first()
            if not session:
                raise ValueError(f"ClaimSession id={session_id} not found.")

            current = ClaimState(session.current_state)

            # Validate legal transition
            allowed = VALID_TRANSITIONS.get(current, set())
            if target_state not in allowed:
                raise InvalidStateTransitionError(
                    f"Illegal state transition from {current.value} to {target_state.value}. Allowed: {[s.value for s in allowed]}"
                )

            # Commit transition
            now = datetime.now(timezone.utc)
            session.current_state = target_state.value
            session.updated_at = now

            if target_state in (ClaimState.CLAIM_VERIFIED, ClaimState.CLAIM_FAILED, ClaimState.CANCELLED, ClaimState.EXPIRED):
                session.completed_at = now
                session.is_active = False

            # Record step audit
            step = ClaimStep(
                session_id=session.id,
                step_name=step_name,
                from_state=current.value,
                to_state=target_state.value,
                notes=notes,
                created_at=now,
            )
            db.add(step)
            db.commit()
            return target_state

    def cancel_session(self, session_id: int, reason: str = "User requested cancellation") -> None:
        """Cancel an in-progress claim session."""
        self.transition_state(session_id, ClaimState.CANCELLED, "SESSION_CANCELLED", reason)


# Global instance
session_manager = SessionManager()
