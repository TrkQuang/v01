"""
Database initialization and session management using SQLAlchemy.
Supports SQLite (default) and PostgreSQL via DATABASE_URL environment variable.
"""

import logging
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from models import Base, Country, Promotion, User
from country_service import country_service

logger = logging.getLogger(__name__)

DEFAULT_SQLITE_PATH = Path(__file__).parent / "pixel_diagnostics.db"
DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{DEFAULT_SQLITE_PATH}")

# Handle Postgres protocol prefix for modern SQLAlchemy if provided by platforms like Replit/Render
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@contextmanager
def get_db() -> Generator[Session, None, None]:
    """Provide a transactional database session scope."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db() -> None:
    """Create all tables and seed default data."""
    logger.info("Initializing database with engine: %s", engine.url)
    Base.metadata.create_all(bind=engine)

    with get_db() as db:
        # Seed countries from country_service if empty
        if db.query(Country).count() == 0:
            logger.info("Seeding countries database table...")
            for c in country_service._countries.values():
                db.add(
                    Country(
                        country_code=c.country_code,
                        country_name=c.country_name,
                        google_ai_pro_available=str(c.google_ai_pro_available),
                        pixel_promotions_supported=str(c.pixel_promotions_supported),
                        official_source=c.official_source,
                        last_verified=datetime.now(timezone.utc),
                        notes=c.notes,
                    )
                )

        # Seed known Pixel promotions
        if db.query(Promotion).count() == 0:
            logger.info("Seeding promotions table...")
            promos = [
                Promotion(
                    promo_code="PIXEL_9_PRO_12M_AI_PREMIUM",
                    title="Google Pixel 9 Pro 12-Month Google One AI Premium Offer",
                    duration_months=12,
                    target_model_family="Pixel 9 Pro / Pro XL / Pro Fold",
                    plan_name="Google One AI Premium (Gemini Advanced)",
                    storage_capacity="2 TB",
                    requires_hardware_attestation=True,
                    redemption_channel="Google One App on certified Pixel device",
                    active=True,
                    notes="Requires physical device GMS checkin, locked bootloader, and MEETS_DEVICE_INTEGRITY.",
                ),
                Promotion(
                    promo_code="PIXEL_11_PRO_6M_AI_PRO",
                    title="Google Pixel 11 Pro 6-Month Google AI Pro Promotion (Research Target)",
                    duration_months=6,
                    target_model_family="Pixel 11 Pro / Pro XL",
                    plan_name="Google AI Pro",
                    storage_capacity="5 TB",
                    requires_hardware_attestation=True,
                    redemption_channel="Google One App on certified Pixel device",
                    active=True,
                    notes="Flagship promotional trial with Gemini Pro access and expanded storage limits.",
                ),
            ]
            db.add_all(promos)


def get_or_create_user(db: Session, telegram_id: int | str, username: str = None, first_name: str = None) -> User:
    """Retrieve existing user or create a new user record."""
    tid = str(telegram_id)
    user = db.query(User).filter(User.telegram_id == tid).first()
    if not user:
        user = User(
            telegram_id=tid,
            username=username,
            first_name=first_name,
            created_at=datetime.now(timezone.utc),
            last_active=datetime.now(timezone.utc),
        )
        db.add(user)
        db.flush()
    else:
        user.last_active = datetime.now(timezone.utc)
        if username:
            user.username = username
        if first_name:
            user.first_name = first_name
        db.flush()
    return user
