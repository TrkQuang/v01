"""
Unit tests for Device Environment Diagnostic Service.
"""

import pytest
from device_diagnostics import DeviceClassification, DeviceDiagnosticService, DeviceEvidence


def test_browser_simulation_classification():
    service = DeviceDiagnosticService()
    evidence = DeviceEvidence(host_os="Windows", host_arch="AMD64", browser_detected=True, cdp_simulation_active=True)
    classification = service._determine_classification(evidence)
    assert classification == DeviceClassification.BROWSER_SIMULATION
    assert "Titan M2" in "; ".join(evidence.diagnostic_notes)


def test_emulator_detection_indicators():
    service = DeviceDiagnosticService()
    evidence = DeviceEvidence(
        host_os="Linux",
        host_arch="x86_64",
        connected_adb_devices=[
            {"device_id": "emulator-5554", "raw_info": "emulator-5554 device product:sdk_gphone_x86", "is_emulator": True}
        ],
    )
    classification = service._determine_classification(evidence)
    assert classification == DeviceClassification.ANDROID_EMULATOR


def test_never_verified_pixel_on_model_string_alone():
    """Verify STRICT RULE: Do not classify a device as VERIFIED_PIXEL based only on model strings."""
    service = DeviceDiagnosticService()
    evidence = DeviceEvidence(
        host_os="Windows",
        host_arch="AMD64",
        browser_detected=True,
        cdp_simulation_active=True,
        model_string="Pixel 11 Pro",
        manufacturer="Google",
    )
    classification = service._determine_classification(evidence)
    assert classification != DeviceClassification.VERIFIED_PIXEL
    assert classification == DeviceClassification.BROWSER_SIMULATION


def test_unknown_environment_classification():
    service = DeviceDiagnosticService()
    evidence = DeviceEvidence(host_os="CustomOS", host_arch="arm", browser_detected=False, cdp_simulation_active=False)
    classification = service._determine_classification(evidence)
    assert classification == DeviceClassification.UNKNOWN
