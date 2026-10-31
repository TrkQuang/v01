"""
SQLAlchemy models for Pixel Promotion Claim Assistant.
Stores user configuration, device state, promotion catalog, claim sessions,
and redemption evidence.

SECURITY DIRECTIVE:
NEVER stores passwords, 2FA secret seeds, session cookies, or raw auth tokens.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class ClaimState(str, Enum):
    IDLE = "IDLE"
    PROMOTION_SELECTED = "PROMOTION_SELECTED"
    DEVICE_SELECTED = "DEVICE_SELECTED"
    COUNTRY_SELECTED = "COUNTRY_SELECTED"
    ELIGIBILITY_CHECKING = "ELIGIBILITY_CHECKING"
    ELIGIBILITY_UNKNOWN = "ELIGIBILITY_UNKNOWN"
    ELIGIBILITY_PASSED = "ELIGIBILITY_PASSED"
    ELIGIBILITY_BLOCKED = "ELIGIBILITY_BLOCKED"
    REDEMPTION_READY = "REDEMPTION_READY"
    USER_ACTION_REQUIRED = "USER_ACTION_REQUIRED"
    CLAIM_IN_PROGRESS = "CLAIM_IN_PROGRESS"
    CLAIM_REPORTED_SUCCESS = "CLAIM_REPORTED_SUCCESS"
    CLAIM_VERIFIED = "CLAIM_VERIFIED"
    CLAIM_FAILED = "CLAIM_FAILED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class User(Base):
    """Telegram User record with isolation and GDPR privacy controls."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(String(64), unique=True, nullable=False, index=True)
    username = Column(String(128), nullable=True)
    first_name = Column(String(128), nullable=True)
    language_code = Column(String(16), nullable=True)
    selected_country_code = Column(String(8), nullable=True, default="US")
    account_type = Column(String(32), default="PERSONAL")  # PERSONAL, WORKSPACE, UNKNOWN
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    last_active = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    devices = relationship("Device", back_populates="user", cascade="all, delete-orphan")
    claim_sessions = relationship("ClaimSession", back_populates="user", cascade="all, delete-orphan")
    eligibility_checks = relationship("EligibilityCheck", back_populates="user", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user", cascade="all, delete-orphan")


class Device(Base):
    """Device profile evaluated during a diagnostic or claim workflow."""
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    device_type = Column(String(32), nullable=False)  # BROWSER_SIMULATION, ANDROID_EMULATOR, PHYSICAL_ANDROID, VERIFIED_PIXEL, UNKNOWN
    manufacturer = Column(String(64), nullable=True)
    model = Column(String(64), nullable=True)
    android_version = Column(String(32), nullable=True)
    build_fingerprint = Column(String(256), nullable=True)
    is_hardware_verified = Column(Boolean, default=False)
    is_user_reported = Column(Boolean, default=False)
    bootloader_locked = Column(Boolean, nullable=True)
    play_services_status = Column(String(64), nullable=True)
    play_store_status = Column(String(64), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="devices")
    claim_sessions = relationship("ClaimSession", back_populates="device")


class Promotion(Base):
    """Verified catalog of official Google Pixel promotional offers."""
    __tablename__ = "promotions"

    id = Column(Integer, primary_key=True)
    promotion_id = Column(String(64), unique=True, nullable=False, index=True)
    promotion_name = Column(String(128), nullable=False)
    provider = Column(String(64), default="Google")
    subscription_plan = Column(String(64), default="Google AI Pro")
    duration_months = Column(Integer, default=6)
    supported_device_models = Column(Text, nullable=False)  # JSON-serialized list
    supported_countries = Column(Text, nullable=False)      # JSON-serialized list
    account_requirements = Column(Text, nullable=True)
    billing_requirements = Column(Text, nullable=True)
    start_date = Column(DateTime, nullable=True)
    expiration_date = Column(DateTime, nullable=True)
    official_terms_url = Column(String(256), nullable=False)
    source_status = Column(String(32), default="VERIFIED_OFFICIAL")  # VERIFIED_OFFICIAL, UNVERIFIED_RESEARCH_TARGET, EXPIRED
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    sources = relationship("PromotionSource", back_populates="promotion", cascade="all, delete-orphan")
    claim_sessions = relationship("ClaimSession", back_populates="promotion")


class PromotionSource(Base):
    """Authoritative source and landing page verification evidence for promotions."""
    __tablename__ = "promotion_sources"

    id = Column(Integer, primary_key=True)
    promotion_id = Column(Integer, ForeignKey("promotions.id"), nullable=False)
    source_url = Column(String(256), nullable=False)
    source_type = Column(String(64), default="GOOGLE_STORE_TERMS")  # GOOGLE_STORE_TERMS, GOOGLE_ONE_HELP, GMS_METADATA
    observed_title = Column(String(128), nullable=True)
    observed_terms = Column(Text, nullable=True)
    last_checked_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    status = Column(String(32), default="ACCESSIBLE")

    promotion = relationship("Promotion", back_populates="sources")


class ClaimSession(Base):
    """User-controlled claim workflow session tracking state transitions."""
    __tablename__ = "claim_sessions"

    id = Column(Integer, primary_key=True)
    session_uuid = Column(String(64), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    promotion_id = Column(Integer, ForeignKey("promotions.id"), nullable=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=True)
    selected_country_code = Column(String(8), nullable=True)
    current_state = Column(String(32), default=ClaimState.IDLE.value, nullable=False, index=True)
    overall_status = Column(String(32), default="UNKNOWN")
    confidence = Column(Float, default=0.0)
    summary_text = Column(Text, nullable=True)
    target_region = Column(String(8), nullable=True)
    is_active = Column(Boolean, default=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="claim_sessions")
    promotion = relationship("Promotion", back_populates="claim_sessions")
    device = relationship("Device", back_populates="claim_sessions")
    steps = relationship("ClaimStep", back_populates="session", cascade="all, delete-orphan", order_by="ClaimStep.created_at")
    evidences = relationship("RedemptionEvidence", back_populates="session", cascade="all, delete-orphan")
    results = relationship("EligibilityCheck", back_populates="session", cascade="all, delete-orphan")

    @property
    def eligibility_checks(self):
        return self.results


class ClaimStep(Base):
    """Audit log of individual state machine transitions within a claim session."""
    __tablename__ = "claim_steps"

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("claim_sessions.id"), nullable=False)
    step_name = Column(String(64), nullable=False)
    from_state = Column(String(32), nullable=False)
    to_state = Column(String(32), nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    session = relationship("ClaimSession", back_populates="steps")


class EligibilityCheck(Base):
    """Detailed eligibility assessment records associated with a session."""
    __tablename__ = "eligibility_checks"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    session_id = Column(Integer, ForeignKey("claim_sessions.id"), nullable=True)
    check_type = Column(String(64), nullable=True)  # DEVICE, REGION, ACCOUNT, SUBSCRIPTION, PAYMENT, PROMOTION
    check_name = Column(String(64), nullable=True)
    result_code = Column(String(32), nullable=False)  # e.g., REGION_ELIGIBLE, DEVICE_NOT_VERIFIED
    passed = Column(Boolean, default=False)
    confidence = Column(Float, default=1.0)
    evidence = Column(Text, nullable=True)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="eligibility_checks")
    session = relationship("ClaimSession", back_populates="results")


class RedemptionEvidence(Base):
    """User-submitted or observed redemption confirmation evidence."""
    __tablename__ = "redemption_evidences"

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("claim_sessions.id"), nullable=False)
    evidence_type = Column(String(32), nullable=False)  # USER_REPORTED_TEXT, SCREENSHOT, GMS_OBSERVATION
    evidence_payload = Column(Text, nullable=False)     # Text report or secure file path
    verification_status = Column(String(32), default="USER_REPORTED")  # USER_REPORTED, VERIFIED, REJECTED
    reviewer_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    session = relationship("ClaimSession", back_populates="evidences")


class AuditLog(Base):
    """Security and compliance audit trail with user isolation."""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(64), nullable=False, index=True)
    details = Column(Text, nullable=True)
    ip_hash = Column(String(64), nullable=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    user = relationship("User", back_populates="audit_logs")


class Country(Base):
    """Regional eligibility database record."""
    __tablename__ = "countries"

    country_code = Column(String(8), primary_key=True)
    country_name = Column(String(128), nullable=False)
    google_ai_pro_available = Column(String(16), default="UNKNOWN")
    pixel_promotions_supported = Column(String(16), default="UNKNOWN")
    official_source = Column(String(256), nullable=True)
    last_verified = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)


# Backward compatibility aliases
DiagnosticSession = ClaimSession
EligibilityResult = EligibilityCheck
