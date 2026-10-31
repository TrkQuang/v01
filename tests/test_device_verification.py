"""
Unit tests for Device Verification & Hardware Attestation boundaries.
Covers requirements 7-10:
- Device classification
- ADB unavailable
- Physical Pixel reported but not independently verified
- Browser simulation
"""

import pytest
from device_verification import (
    DeviceTier,
    DeviceVerificationReport,
    DeviceVerificationService,
)


def test_browser_simulation_detection():
    """Requirement 10: Desktop browser mobile emulation is explicitly identified."""
    service = DeviceVerificationService()
    report = service.inspect_environment(is_emulation_probe=True)
    assert report.device_tier == DeviceTier.BROWSER_MOBILE_EMULATION
    assert report.is_hardware_verified is False
    assert any("Titan M2" in note for note in report.verification_notes)


def test_adb_unavailable_fallback():
    """Requirement 8: Graceful fallback when ADB binary is absent."""
    service = DeviceVerificationService()
    service.adb_bin = None  # simulate adb not in PATH
    report = service.inspect_environment()
    assert report.adb_connected is False
    assert report.device_tier == DeviceTier.DESKTOP_BROWSER


def test_physical_pixel_reported_but_unverified():
    """Requirement 9: Self-reported model marked as USER_REPORTED and unverified."""
    service = DeviceVerificationService()
    service.adb_bin = None
    report = service.inspect_environment(manual_model="Pixel 9 Pro")
    assert report.device_tier == DeviceTier.PHYSICAL_ANDROID
    assert report.is_user_reported is True
    assert report.is_hardware_verified is False
    assert any("USER_REPORTED" in note for note in report.verification_notes)


def test_device_classification_tiers():
    """Requirement 7: Distinct device tier classification."""
    service = DeviceVerificationService()
    service.adb_bin = None

    # Desktop
    rep1 = service.inspect_environment()
    assert rep1.device_tier == DeviceTier.DESKTOP_BROWSER

    # Manual Non-Pixel
    rep2 = service.inspect_environment(manual_model="Samsung Galaxy S24")
    assert rep2.device_tier == DeviceTier.UNKNOWN
    assert rep2.is_hardware_verified is False

