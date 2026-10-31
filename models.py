"""
SQLAlchemy models for Pixel Promotion Research & Diagnostic Platform.
Never stores sensitive Google credentials, passwords, recovery codes, or session tokens.
"""

from datetime import datetime, timezone
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


class User(Base):
    """Telegram User record."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(String(64), unique=True, nullable=False, index=True)
    username = Column(String(128), nullable=True)
    first_name = Column(String(128), nullable=True)
    language_code = Column(String(16), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    last_active = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    sessions = relationship("DiagnosticSession", back_populates="user", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user", cascade="all, delete-orphan")


class Device(Base):
    """Device profile evaluated during a diagnostic."""
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True)
    device_type = Column(String(32), nullable=False)  # BROWSER_SIMULATION, ANDROID_EMULATOR, etc.
    manufacturer = Column(String(64), nullable=True)
    model = Column(String(64), nullable=True)
    android_version = Column(String(32), nullable=True)
    build_fingerprint = Column(String(256), nullable=True)
    is_hardware_verified = Column(Boolean, default=False)
    play_services_status = Column(String(64), nullable=True)
    play_store_status = Column(String(64), nullable=True)
    certification_status = Column(String(64), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    sessions = relationship("DiagnosticSession", back_populates="device")


class DiagnosticSession(Base):
    """A diagnostic test session run by a user."""
    __tablename__ = "diagnostic_sessions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=True)
    session_uuid = Column(String(64), unique=True, nullable=False, index=True)
    target_region = Column(String(8), nullable=True)
    target_plan = Column(String(64), default="Google One AI Premium")
    overall_status = Column(String(32), default="UNKNOWN")  # OFFER_VISIBLE, DEVICE_NOT_VERIFIED, etc.
    confidence = Column(Float, default=0.0)
    summary_text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="sessions")
    device = relationship("Device", back_populates="sessions")
    results = relationship("EligibilityResult", back_populates="session", cascade="all, delete-orphan")


class EligibilityResult(Base):
    """Specific check result within a diagnostic session."""
    __tablename__ = "eligibility_results"

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("diagnostic_sessions.id"), nullable=False)
    check_name = Column(String(64), nullable=False)  # e.g., 'device_integrity', 'region', 'account'
    result_code = Column(String(32), nullable=False)  # OFFER_NOT_VISIBLE, DEVICE_NOT_VERIFIED, etc.
    passed = Column(Boolean, default=False)
    confidence = Column(Float, default=1.0)
    evidence = Column(Text, nullable=True)
    recommendation = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    session = relationship("DiagnosticSession", back_populates="results")


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


class Promotion(Base):
    """Catalog of known Google Pixel promotions."""
    __tablename__ = "promotions"

    id = Column(Integer, primary_key=True)
    promo_code = Column(String(64), unique=True, nullable=False)
    title = Column(String(128), nullable=False)
    duration_months = Column(Integer, default=6)
    target_model_family = Column(String(64), nullable=False)  # e.g., 'Pixel 9 Pro', 'Pixel 11 Pro'
    plan_name = Column(String(64), default="Google AI Pro")
    storage_capacity = Column(String(32), default="2 TB")
    requires_hardware_attestation = Column(Boolean, default=True)
    redemption_channel = Column(String(64), default="Google One App on Device")
    active = Column(Boolean, default=True)
    notes = Column(Text, nullable=True)


class AuditLog(Base):
    """Audit log for user interactions, diagnoses, and security events."""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(64), nullable=False)
    details = Column(Text, nullable=True)
    ip_hash = Column(String(64), nullable=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    user = relationship("User", back_populates="audit_logs")
