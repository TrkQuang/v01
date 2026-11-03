"""
Unit tests for Country & Regional Eligibility Service.
"""

import pytest
from country_service import country_service


def test_eligible_countries():
    us = country_service.check_region_eligibility("US")
    assert us["status"] == "ELIGIBLE"
    assert us["pixel_promotions_supported"] is True
    assert us["google_ai_pro_available"] is True
    assert us["confidence"] >= 0.9

    gb = country_service.check_region_eligibility("GB")
    assert gb["status"] == "ELIGIBLE"
    assert gb["pixel_promotions_supported"] is True

    th = country_service.check_region_eligibility("TH")
    assert th["status"] == "ELIGIBLE"
    assert th["pixel_promotions_supported"] is True


def test_ineligible_countries():
    vn = country_service.check_region_eligibility("VN")
    assert vn["status"] == "INELIGIBLE"
    assert vn["pixel_promotions_supported"] is False
    assert vn["confidence"] >= 0.9


def test_unknown_country():
    unknown = country_service.check_region_eligibility("ZZ")
    assert unknown["status"] == "UNKNOWN"
    assert unknown["pixel_promotions_supported"] == "UNKNOWN"
    assert "not cataloged" in unknown["evidence"]

