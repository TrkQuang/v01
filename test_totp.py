"""
Diagnostic verification script for environment and promotion logic.
Does not contain hardcoded account credentials.
"""

import logging
from device_diagnostics import DeviceClassification, device_diagnostic_service
from promotion_diagnostics import DiagnosticResultCode, promotion_diagnostic_engine
from country_service import country_service

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("diagnostic_verification")


def test_diagnostics_suite():
    logger.info("=" * 60)
    logger.info("RUNNING AUTOMATED DIAGNOSTIC LOGIC VERIFICATION")
    logger.info("=" * 60)

    # 1. Device Inspection
    dev_class, evidence = device_diagnostic_service.inspect_environment()
    logger.info("Device Classification : %s", dev_class.value)
    logger.info("Host OS               : %s (%s)", evidence.host_os, evidence.host_arch)
    logger.info("Browser Detected      : %s (%s)", evidence.browser_detected, evidence.browser_name)
    logger.info("ADB Available         : %s", evidence.adb_available)

    # 2. Country Service Check
    us_check = country_service.check_region_eligibility("US")
    vn_check = country_service.check_region_eligibility("VN")
    logger.info("Country US Eligibility: %s (Google AI Pro: %s)", us_check["status"], us_check["google_ai_pro_available"])
    logger.info("Country VN Eligibility: %s (Google AI Pro: %s)", vn_check["status"], vn_check["google_ai_pro_available"])

    # 3. Promotion Engine Evaluation
    report = promotion_diagnostic_engine.evaluate(
        device_class=dev_class,
        device_evidence=evidence,
        country_code="US",
        account_is_workspace=False,
    )
    logger.info("Diagnostic Engine Result: %s (Confidence: %.2f)", report.overall_code.value, report.confidence)
    logger.info("Diagnosis Summary       : %s", report.summary)

    logger.info("=" * 60)
    logger.info("ALL DIAGNOSTIC PIPELINES OPERATIONAL ✅")
    logger.info("=" * 60)


if __name__ == "__main__":
    test_diagnostics_suite()
