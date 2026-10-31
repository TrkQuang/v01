"""
Country and Regional Eligibility Service for Google One & Pixel Promotions.

Maintains verified mapping between ISO-3166 alpha-2 country codes,
Google AI Pro availability, and Google Pixel hardware promotional support.
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Union

logger = logging.getLogger(__name__)

COUNTRIES_JSON_PATH = Path(__file__).parent / "countries.json"


@dataclass
class CountryEligibility:
    country_code: str
    country_name: str
    google_ai_pro_available: Union[bool, str]
    pixel_promotions_supported: Union[bool, str]
    purchase_requirement_regions: List[str]
    redemption_regions: List[str]
    official_source: str
    last_verified: str
    notes: str = ""

    def is_eligible_for_pixel_promotion(self) -> str:
        """
        Return 'ELIGIBLE', 'INELIGIBLE', or 'UNKNOWN'.
        Never assume eligibility when unsupported or unverified.
        """
        if self.pixel_promotions_supported is True:
            return "ELIGIBLE"
        elif self.pixel_promotions_supported is False:
            return "INELIGIBLE"
        return "UNKNOWN"


class CountryService:
    def __init__(self, data_path: Optional[Path] = None):
        self.data_path = data_path or COUNTRIES_JSON_PATH
        self._countries: Dict[str, CountryEligibility] = {}
        self.load()

    def load(self) -> None:
        """Load country database from JSON."""
        if not self.data_path.exists():
            logger.warning("Countries database not found at %s", self.data_path)
            return

        try:
            with open(self.data_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._countries = {
                code.upper(): CountryEligibility(
                    country_code=code.upper(),
                    country_name=item.get("country_name", code.upper()),
                    google_ai_pro_available=item.get("google_ai_pro_available", "UNKNOWN"),
                    pixel_promotions_supported=item.get("pixel_promotions_supported", "UNKNOWN"),
                    purchase_requirement_regions=item.get("purchase_requirement_regions", []),
                    redemption_regions=item.get("redemption_regions", []),
                    official_source=item.get("official_source", ""),
                    last_verified=item.get("last_verified", ""),
                    notes=item.get("notes", ""),
                )
                for code, item in data.items()
            }
            logger.info("Loaded %d country profiles", len(self._countries))
        except Exception as exc:
            logger.error("Failed to load country database: %s", exc)

    def get_country(self, code: str) -> Optional[CountryEligibility]:
        return self._countries.get(code.upper().strip())

    def list_supported_countries(self) -> List[CountryEligibility]:
        return [c for c in self._countries.values() if c.pixel_promotions_supported is True]

    def check_region_eligibility(self, code: str) -> Dict[str, Union[str, bool]]:
        country = self.get_country(code)
        if not country:
            return {
                "country_code": code.upper(),
                "status": "UNKNOWN",
                "google_ai_pro_available": "UNKNOWN",
                "pixel_promotions_supported": "UNKNOWN",
                "evidence": f"Country code '{code.upper()}' is not cataloged in official Google Store promotion database.",
                "confidence": 0.5,
            }

        status = country.is_eligible_for_pixel_promotion()
        confidence = 0.95 if status in ("ELIGIBLE", "INELIGIBLE") else 0.5
        evidence = (
            f"{country.country_name} ({country.country_code}): Pixel hardware promotions "
            f"{'supported' if status == 'ELIGIBLE' else 'not supported or unverified'}. "
            f"Notes: {country.notes}"
        )
        return {
            "country_code": country.country_code,
            "country_name": country.country_name,
            "status": status,
            "google_ai_pro_available": country.google_ai_pro_available,
            "pixel_promotions_supported": country.pixel_promotions_supported,
            "official_source": country.official_source,
            "evidence": evidence,
            "confidence": confidence,
        }


# Global instance
country_service = CountryService()

