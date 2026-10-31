"""
Unit tests for the Promotion Diagnostic Engine.
"""

import pytest
from device_diagnostics import DeviceClassification, DeviceEvidence
from promotion_diagnostics import DiagnosticResultCode, promotion_diagnostic_engine


def test_full_evaluation_browser_simulation_blocks_offer():
    evidence = DeviceEvidence(host_os="Windows", host_arch="AMD64", browser_detected=True, cdp_simulation_active=True)
    report = promotion_diagnostic_engine.evaluate(
        device_class=DeviceClassification.BROWSER_SIMULATION,
        device_evidence=evidence,
        country_code="US",
        account_email="tester@gmail.com",
    )
    assert report.overall_code == DiagnosticResultCode.DEVICE_NOT_VERIFIED
    assert report.confidence >= 0.95
    assert any(f.check_name == "Device Hardware Verification" and not f.passed for f in report.findings)


def test_full_evaluation_ineligible_region_blocks_offer():
    evidence = DeviceEvidence(host_os="Linux", host_arch="x86_64")
    report = promotion_diagnostic_engine.evaluate(
        device_class=DeviceClassification.PHYSICAL_ANDROID,
        device_evidence=evidence,
        country_code="VN",
        account_email="tester@gmail.com",
    )
    assert report.overall_code in (DiagnosticResultCode.DEVICE_NOT_VERIFIED, DiagnosticResultCode.REGION_NOT_SUPPORTED)


def test_missing_payment_method_flagged():
    finding = promotion_diagnostic_engine._check_payment_method(has_payment_method=False)
    assert finding.passed is False
    assert finding.result_code == DiagnosticResultCode.PAYMENT_REQUIREMENT_MISSING
    assert "payment" in finding.explanation.lower()


def test_web_observation_security_challenge():
    finding = promotion_diagnostic_engine._check_web_observation("MANUAL_REVIEW_REQUIRED")
    assert finding.passed is False
    assert finding.result_code == DiagnosticResultCode.MANUAL_REVIEW_REQUIRED

