"""
Unit tests for Authoritative Eligibility Engine.
Covers requirements 1-6:
- Country persistence
- Country mismatch detection
- Promotion expiration
- Unsupported promotion source
- Account eligibility unknown
- Account ineligibility
"""

import pytest
from database import get_db, get_or_create_user, init_db
from device_verification import DeviceTier, DeviceVerificationReport
from eligibility_engine import EligibilityCode, eligibility_engine
from promotion_catalog import PromotionItem, promotion_service


@pytest.fixture(autouse=True)
def setup_db():
    init_db()


def make_test_device(model="Pixel 9 Pro", verified=True) -> DeviceVerificationReport:
    return DeviceVerificationReport(
        device_tier=DeviceTier.VERIFIED_PIXEL if verified else DeviceTier.PHYSICAL_ANDROID,
        reported_model=model,
        reported_manufacturer="Google",
        android_version="15",
        build_fingerprint="google/caiman/caiman:15/...",
        is_hardware_verified=verified,
        is_user_reported=not verified,
        bootloader_locked=verified,
        play_services_installed=True,
        play_store_installed=True,
        adb_connected=verified,
    )


def test_country_persistence():
    """Requirement 1: User country configuration persists accurately."""
    with get_db() as db:
        user = get_or_create_user(db, 8888, username="country_tester")
        user.selected_country_code = "GB"

    with get_db() as db:
        reloaded = get_or_create_user(db, 8888)
        assert reloaded.selected_country_code == "GB"


def test_country_mismatch_detection():
    """Requirement 2: Detecting unsupported regions."""
    promo = promotion_service.get_promotion("pixel-9-pro-12m-ai-premium")
    device = make_test_device()

    # Vietnam (VN) is not in supported countries for Pixel Store promotions
    report = eligibility_engine.evaluate(
        promotion=promo,
        device_report=device,
        country_code="VN",
        account_type="PERSONAL",
    )
    assert report.is_eligible is False
    assert report.primary_code == EligibilityCode.REGION_INELIGIBLE
    assert any(c.category == "REGION" and not c.passed for c in report.assessments)


def test_promotion_expiration():
    """Requirement 3: Detecting expired promotions."""
    expired_promo = PromotionItem(
        promotion_id="expired-promo",
        promotion_name="Old Pixel Promo",
        provider="Google",
        subscription_plan="Google AI",
        duration_months=3,
        supported_device_models=["Pixel 8"],
        supported_countries=["US"],
        account_requirements="Personal",
        billing_requirements="Valid Card",
        start_date="2023-01-01T00:00:00Z",
        expiration_date="2023-12-31T23:59:59Z",  # Expired
        official_terms_url="https://store.google.com",
        source_status="EXPIRED",
    )
    device = make_test_device(model="Pixel 8")
    report = eligibility_engine.evaluate(
        promotion=expired_promo,
        device_report=device,
        country_code="US",
        account_type="PERSONAL",
    )
    assert report.is_eligible is False
    assert report.primary_code == EligibilityCode.PROMOTION_EXPIRED


def test_pixel_11_pro_verified_promotion_eligible():
    """Verify Pixel 11 Pro 6-Month Google AI Pro offer evaluates as eligible."""
    promo = promotion_service.get_promotion("pixel-11-pro-6m-ai-pro")
    assert promo is not None
    assert promo.source_status == "VERIFIED_OFFICIAL"
    device = make_test_device(model="Pixel 11 Pro")

    report = eligibility_engine.evaluate(
        promotion=promo,
        device_report=device,
        country_code="TH",
        account_type="PERSONAL",
    )
    assert report.is_eligible is True
    assert report.primary_code == EligibilityCode.DEVICE_ELIGIBLE


def test_unsupported_promotion_source():
    """Requirement 4: Flagging unreleased / unverified research targets."""
    unverified_promo = PromotionItem(
        promotion_id="future-test-promo",
        promotion_name="Future Unreleased Target",
        provider="Google Store",
        subscription_plan="Google AI Pro",
        duration_months=6,
        supported_device_models=["Future Pixel"],
        supported_countries=["US"],
        account_requirements="",
        billing_requirements="",
        start_date=None,
        expiration_date="2028-12-31T00:00:00Z",
        official_terms_url="https://store.google.com",
        source_status="UNVERIFIED_RESEARCH_TARGET",
    )
    device = make_test_device(model="Future Pixel")

    report = eligibility_engine.evaluate(
        promotion=unverified_promo,
        device_report=device,
        country_code="US",
        account_type="PERSONAL",
    )
    assert report.is_eligible is False
    assert report.primary_code == EligibilityCode.PROMOTION_UNAVAILABLE
    assert "research target" in report.overall_summary.lower()


def test_account_eligibility_unknown():
    """Requirement 5: Account with unverified state reports ACCOUNT_UNKNOWN."""
    promo = promotion_service.get_promotion("pixel-9-pro-12m-ai-premium")
    device = make_test_device()

    finding = eligibility_engine._assess_account(
        account_email=None,
        account_type="UNKNOWN",
        has_active_google_one=None,
        has_redeemed_prior_trial=None,
    )
    assert finding.code == EligibilityCode.ACCOUNT_UNKNOWN
    assert "unconfirmed" in finding.summary.lower()


def test_account_ineligibility():
    """Requirement 6: Enterprise Google Workspace accounts are flagged ACCOUNT_INELIGIBLE."""
    finding = eligibility_engine._assess_account(
        account_email="employee@corp.com",
        account_type="WORKSPACE",
        has_active_google_one=None,
        has_redeemed_prior_trial=None,
    )
    assert finding.passed is False
    assert finding.code == EligibilityCode.ACCOUNT_INELIGIBLE
    assert "Workspace" in finding.summary

