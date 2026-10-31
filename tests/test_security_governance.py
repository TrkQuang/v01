"""
Unit tests for Security, Data Isolation & Secret Redaction.
Covers requirements 18 and 20:
- Database user isolation
- Credential leakage prevention (redacting secrets, passwords, tokens)
- GDPR right-to-be-forgotten erasure
"""

import pytest
from audit_service import audit_service, redact_secrets
from database import get_db, get_or_create_user, init_db
from models import AuditLog, ClaimSession, User
from session_manager import session_manager


@pytest.fixture(autouse=True)
def setup_db():
    init_db()


def test_database_user_isolation():
    """Requirement 18: Ensuring data belonging to User A cannot be accessed by User B."""
    import uuid
    uid_a = uuid.uuid4().int % 10000000
    uid_b = (uid_a + 1) % 10000000

    with get_db() as db:
        user_a = get_or_create_user(db, uid_a, username="usera")
        user_b = get_or_create_user(db, uid_b, username="userb")
        user_a_id = user_a.id
        user_b_id = user_b.id

    s_a = session_manager.create_claim_session(uid_a)
    s_b = session_manager.create_claim_session(uid_b)

    with get_db() as db:
        sessions_a = db.query(ClaimSession).filter(ClaimSession.user_id == user_a_id).all()
        sessions_b = db.query(ClaimSession).filter(ClaimSession.user_id == user_b_id).all()

        assert len(sessions_a) == 1
        assert len(sessions_b) == 1
        assert sessions_a[0].id != sessions_b[0].id
        assert sessions_a[0].user_id == user_a_id
        assert sessions_b[0].user_id == user_b_id


def test_credential_leakage_prevention():
    """Requirement 20: Secrets, passwords, and tokens are redacted before logging."""
    raw_message = "User provided password: mySecretPassword123 with token: eyJhbGciOiJIUzI1NiJ9"
    redacted = redact_secrets(raw_message)

    assert "mySecretPassword123" not in redacted
    assert "password: [REDACTED]" in redacted

    # Record event through audit service
    audit_service.record_event(
        telegram_id=1001,
        action="TEST_LOG",
        details="Attempting login with secret: superSecretKey99",
    )

    with get_db() as db:
        log = db.query(AuditLog).filter(AuditLog.action == "TEST_LOG").first()
        assert log is not None
        assert "superSecretKey99" not in log.details
        assert "[REDACTED]" in log.details


def test_gdpr_data_erasure():
    """Verification of right-to-be-forgotten deletion."""
    with get_db() as db:
        user = get_or_create_user(db, 5555, username="delete_me")
        user_id = user.id

    session_manager.create_claim_session(5555)

    # Execute deletion
    success = audit_service.delete_all_user_records(5555)
    assert success is True

    # User and sessions should be deleted from DB
    with get_db() as db:
        check_user = db.query(User).filter(User.id == user_id).first()
        assert check_user is None
        check_sessions = db.query(ClaimSession).filter(ClaimSession.user_id == user_id).all()
        assert len(check_sessions) == 0
