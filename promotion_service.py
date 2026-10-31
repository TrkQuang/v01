"""
Promotion Catalog & Service for Pixel Promotion Claim Assistant.

Provides authoritative promotion metadata, supported hardware lists,
official terms URLs, and verification timestamps.
Never invents promotion information; labels unverified targets as UNVERIFIED.
"""

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from database import get_db
from models import Promotion, PromotionSource

logger = logging.getLogger(__name__)


@dataclass
class PromotionItem:
    promotion_id: str
    promotion_name: str
    provider: str
    subscription_plan: str
    duration_months: int
    supported_device_models: List[str]
    supported_countries: List[str]
    account_requirements: str
    billing_requirements: str
    start_date: Optional[str]
    expiration_date: Optional[str]
    official_terms_url: str
    source_status: str  # VERIFIED_OFFICIAL, UNVERIFIED_RESEARCH_TARGET, EXPIRED
    source_verified_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    active: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def is_expired(self) -> bool:
        if not self.expiration_date:
            return False
        try:
            exp = datetime.fromisoformat(self.expiration_date.replace("Z", "+00:00"))
            return datetime.now(timezone.utc) > exp
        except Exception:
            return False

    def supports_device(self, model_name: str) -> bool:
        if not model_name:
            return False
        clean = model_name.strip().lower()
        return any(clean in m.lower() or m.lower() in clean for m in self.supported_device_models)

    def supports_country(self, country_code: str) -> bool:
        if not country_code:
            return False
        return country_code.upper().strip() in [c.upper() for c in self.supported_countries]


class PromotionService:
    """Service for discovering, filtering, and validating Pixel promotions."""

    def list_all_promotions(self, include_unverified: bool = True) -> List[PromotionItem]:
        """Fetch all promotions from database catalog."""
        items: List[PromotionItem] = []
        with get_db() as db:
            promos = db.query(Promotion).filter(Promotion.active == True).all()
            for p in promos:
                if not include_unverified and p.source_status != "VERIFIED_OFFICIAL":
                    continue
                try:
                    devs = json.loads(p.supported_device_models)
                except Exception:
                    devs = []
                try:
                    countries = json.loads(p.supported_countries)
                except Exception:
                    countries = []

                items.append(
                    PromotionItem(
                        promotion_id=p.promotion_id,
                        promotion_name=p.promotion_name,
                        provider=p.provider,
                        subscription_plan=p.subscription_plan,
                        duration_months=p.duration_months,
                        supported_device_models=devs,
                        supported_countries=countries,
                        account_requirements=p.account_requirements or "",
                        billing_requirements=p.billing_requirements or "",
                        start_date=p.start_date.isoformat() if p.start_date else None,
                        expiration_date=p.expiration_date.isoformat() if p.expiration_date else None,
                        official_terms_url=p.official_terms_url,
                        source_status=p.source_status,
                        active=p.active,
                    )
                )
        return items

    def get_promotion(self, promotion_id: str) -> Optional[PromotionItem]:
        """Retrieve single promotion by its identifier."""
        with get_db() as db:
            p = db.query(Promotion).filter(Promotion.promotion_id == promotion_id).first()
            if not p:
                return None
            try:
                devs = json.loads(p.supported_device_models)
                countries = json.loads(p.supported_countries)
            except Exception:
                devs, countries = [], []

            return PromotionItem(
                promotion_id=p.promotion_id,
                promotion_name=p.promotion_name,
                provider=p.provider,
                subscription_plan=p.subscription_plan,
                duration_months=p.duration_months,
                supported_device_models=devs,
                supported_countries=countries,
                account_requirements=p.account_requirements or "",
                billing_requirements=p.billing_requirements or "",
                start_date=p.start_date.isoformat() if p.start_date else None,
                expiration_date=p.expiration_date.isoformat() if p.expiration_date else None,
                official_terms_url=p.official_terms_url,
                source_status=p.source_status,
                active=p.active,
            )

    def find_matching_promotions(self, model: Optional[str], country_code: Optional[str]) -> List[PromotionItem]:
        """Find active promotions matching device model and country code."""
        all_promos = self.list_all_promotions(include_unverified=True)
        matched = []
        for p in all_promos:
            if model and not p.supports_device(model):
                continue
            if country_code and not p.supports_country(country_code):
                continue
            matched.append(p)
        return matched


# Global instance
promotion_service = PromotionService()

