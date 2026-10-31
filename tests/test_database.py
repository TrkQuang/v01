"""
Unit tests for Database Models and Persistence.
"""

import uuid
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import Base, DiagnosticSession, EligibilityResult, User, AuditLog
from database import get_or_create_user


@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        yield db
    finally:
        db.close()


def test_user_creation_and_retrieval(test_db):
    user1 = get_or_create_user(test_db, 12345, username="testuser", first_name="Tester")
    assert user1.id is not None
    assert user1.telegram_id == "12345"

    # Fetch again should update last_active without duplicating
    user2 = get_or_create_user(test_db, 12345, username="newusername")
    assert user2.id == user1.id
    assert user2.username == "newusername"


def test_diagnostic_session_cascade(test_db):
    user = get_or_create_user(test_db, 99999)
    session = DiagnosticSession(
        user_id=user.id,
        session_uuid=str(uuid.uuid4()),
        target_region="US",
        overall_status="DEVICE_NOT_VERIFIED",
        confidence=0.95,
        summary_text="Test summary",
    )
    test_db.add(session)
    test_db.flush()

    res = EligibilityResult(
        session_id=session.id,
        check_name="Hardware Check",
        result_code="DEVICE_NOT_VERIFIED",
        passed=False,
    )
    test_db.add(res)
    test_db.commit()

    saved_session = test_db.query(DiagnosticSession).filter(DiagnosticSession.id == session.id).first()
    assert saved_session is not None
    assert len(saved_session.results) == 1
    assert saved_session.results[0].check_name == "Hardware Check"
