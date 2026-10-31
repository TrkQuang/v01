"""
Database initialization and session management using SQLAlchemy.
Supports SQLite (default) and PostgreSQL via DATABASE_URL environment variable.
"""

import json
import logging
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from models import Base, Country, Promotion, PromotionSource, User

logger = logging.getLogger(__name__)

DEFAULT_SQLITE_PATH = Path(__file__).parent / "pixel_diagnostics.db"
DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{DEFAULT_SQLITE_PATH}")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)


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
    """Create all tables and seed default verified data."""
    logger.info("Initializing database with engine: %s", engine.url)
    Base.metadata.create_all(bind=engine)

    with get_db() as db:
        # Seed promotions if empty
        if db.query(Promotion).count() == 0:
            logger.info("Seeding verified promotions catalog...")
            promos = [
                Promotion(
                    promotion_id="pixel-9-pro-12m-ai-premium",
                    promotion_name="Google Pixel 9 Pro 12-Month Google One AI Premium Offer",
                    provider="Google Store & Google One",
                    subscription_plan="Google One AI Premium (Gemini Advanced)",
                    duration_months=12,
                    supported_device_models=json.dumps([
                        "Pixel 9 Pro",
                        "Pixel 9 Pro XL",
                        "Pixel 9 Pro Fold"
                    ]),
                    supported_countries=json.dumps([
                        "US", "GB", "CA", "DE", "FR", "JP", "AU", "SG", "IE", "NL", "IT", "ES"
                    ]),
                    account_requirements="Personal @gmail.com account; not Google Workspace; not active Family Link group storage plan; new to Google One AI tier.",
                    billing_requirements="Valid credit/debit card on Google Play Wallet for $0 recurring trial setup.",
                    start_date=datetime(2024, 8, 13, tzinfo=timezone.utc),
                    expiration_date=datetime(2025, 11, 15, tzinfo=timezone.utc),
                    official_terms_url="https://store.google.com/terms/pixel_ai_promotion",
                    source_status="VERIFIED_OFFICIAL",
                    active=True,
                ),
                Promotion(
                    promotion_id="pixel-9-6m-google-one",
                    promotion_name="Google Pixel 9 Standard 6-Month 2TB Storage Offer",
                    provider="Google One",
                    subscription_plan="Google One Premium (2 TB)",
                    duration_months=6,
                    supported_device_models=json.dumps([
                        "Pixel 9",
                        "Pixel 9a"
                    ]),
                    supported_countries=json.dumps([
                        "US", "GB", "CA", "DE", "FR", "JP", "AU"
                    ]),
                    account_requirements="Personal Google Account; new Google One subscriber.",
                    billing_requirements="Valid payment method on Google Play.",
                    start_date=datetime(2024, 8, 13, tzinfo=timezone.utc),
                    expiration_date=datetime(2025, 12, 31, tzinfo=timezone.utc),
                    official_terms_url="https://one.google.com/about/plans",
                    source_status="VERIFIED_OFFICIAL",
                    active=True,
                ),
                Promotion(
                    promotion_id="pixel-11-pro-6m-ai-pro",
                    promotion_name="Google Pixel 11 Pro 6-Month Google AI Pro Promotion (Research Target)",
                    provider="Google Store (Future / Research Target)",
                    subscription_plan="Google AI Pro (5 TB)",
                    duration_months=6,
                    supported_device_models=json.dumps([
                        "Pixel 11 Pro",
                        "Pixel 11 Pro XL",
                        "Pixel 11 Pro Fold"
                    ]),
                    supported_countries=json.dumps([
                        "US", "GB", "CA", "DE", "FR", "JP"
                    ]),
                    account_requirements="Personal Google Account with qualifying retail Pixel 11 Pro purchase.",
                    billing_requirements="Google Play Payment method required for auto-renewal authorization.",
                    start_date=datetime(2026, 10, 1, tzinfo=timezone.utc),
                    expiration_date=datetime(2027, 10, 31, tzinfo=timezone.utc),
                    official_terms_url="https://store.google.com/terms/pixel_ai_promotion",
                    source_status="UNVERIFIED_RESEARCH_TARGET",
                    active=True,
                ),
            ]
            db.add_all(promos)
            db.flush()

            for p in promos:
                db.add(
                    PromotionSource(
                        promotion_id=p.id,
                        source_url=p.official_terms_url,
                        source_type="GOOGLE_STORE_TERMS",
                        observed_title=p.promotion_name,
                        status="ACCESSIBLE",
                    )
                )


def get_or_create_user(
    db: Session,
    telegram_id: int | str,
    username: Optional[str] = None,
    first_name: Optional[str] = None,
) -> User:
    """Retrieve existing user or create a new user record."""
    tid = str(telegram_id)
    user = db.query(User).filter(User.telegram_id == tid).first()
    now = datetime.now(timezone.utc)
    if not user:
        user = User(
            telegram_id=tid,
            username=username,
            first_name=first_name,
            selected_country_code="US",
            created_at=now,
            last_active=now,
        )
        db.add(user)
        db.flush()
    else:
        user.last_active = now
        if username:
            user.username = username
        if first_name:
            user.first_name = first_name
        db.flush()
    return user


def delete_user_data(db: Session, telegram_id: int | str) -> bool:
    """GDPR right-to-be-forgotten: delete all data belonging to user."""
    tid = str(telegram_id)
    user = db.query(User).filter(User.telegram_id == tid).first()
    if not user:
        return False

    db.delete(user)
    db.commit()
    return True
