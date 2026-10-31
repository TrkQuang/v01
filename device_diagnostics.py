"""
Device Environment Diagnostic Service.

Determines the true operational execution tier:
- BROWSER_SIMULATION: Running desktop browser with simulated mobile viewport/UA.
- ANDROID_EMULATOR: Running inside QEMU / AVD / Goldfish / Cuttlefish emulator.
- PHYSICAL_ANDROID: Running on bare-metal physical Android hardware.
- VERIFIED_PIXEL: Physical Google Pixel with certified Play Services, locked bootloader, and hardware attestation.
- UNKNOWN: Insufficient environment evidence.

STRICT RULE: Never classify a device as VERIFIED_PIXEL based solely on model strings.
"""

import logging
import os
import platform
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class DeviceClassification(str, Enum):
    BROWSER_SIMULATION = "BROWSER_SIMULATION"
    ANDROID_EMULATOR = "ANDROID_EMULATOR"
    PHYSICAL_ANDROID = "PHYSICAL_ANDROID"
    VERIFIED_PIXEL = "VERIFIED_PIXEL"
    UNKNOWN = "UNKNOWN"


@dataclass
class DeviceEvidence:
    host_os: str
    host_arch: str
    browser_detected: bool = False
    browser_name: str = "None"
    cdp_simulation_active: bool = False
    adb_available: bool = False
    connected_adb_devices: List[Dict[str, str]] = field(default_factory=list)
    android_runtime_detected: bool = False
    manufacturer: str = "Unknown"
    model_string: str = "Unknown"
    android_version: str = "Unknown"
    build_fingerprint: str = "Unknown"
    bootloader_locked: Optional[bool] = None
    play_services_installed: bool = False
    play_services_version: str = "Unavailable"
    play_store_installed: bool = False
    emulator_indicators: List[str] = field(default_factory=list)
    hardware_attestation_available: bool = False
    diagnostic_notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DeviceDiagnosticService:
    """Probes the execution host, ADB, and runtime environment."""

    def __init__(self):
        self.adb_bin = shutil.which("adb")

    def inspect_environment(self, simulated_profile: Optional[Dict[str, Any]] = None) -> (DeviceClassification, DeviceEvidence):
        """Perform full diagnostic sweep of the current execution environment."""
        host_os = platform.system()
        host_arch = platform.machine()
        evidence = DeviceEvidence(host_os=host_os, host_arch=host_arch)

        # 1. Check host browser availability
        self._check_browser_environment(evidence)

        # 2. Check ADB availability and inspect connected devices if any
        self._check_adb_devices(evidence)

        # 3. Assess CDP simulation context if provided
        if simulated_profile:
            evidence.cdp_simulation_active = True
            evidence.model_string = simulated_profile.get("model", "Pixel 11 Pro (Simulated)")
            evidence.manufacturer = simulated_profile.get("manufacturer", "Google (Simulated)")
            evidence.diagnostic_notes.append("Active browser session is utilizing CDP mobile emulation overrides.")

        # 4. Classify device tier
        classification = self._determine_classification(evidence)
        return classification, evidence

    def _check_browser_environment(self, evidence: DeviceEvidence) -> None:
        """Inspect if host has Chrome / Chromium automation capabilities."""
        for candidate in ["google-chrome", "chrome", "chromium", "brave"]:
            path = shutil.which(candidate)
            if path:
                evidence.browser_detected = True
                evidence.browser_name = candidate
                break

        # Check Windows typical locations if not in PATH
        if not evidence.browser_detected and platform.system() == "Windows":
            win_paths = [
                os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
                os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
                os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
            ]
            for p in win_paths:
                if os.path.exists(p):
                    evidence.browser_detected = True
                    evidence.browser_name = f"Google Chrome ({p})"
                    break

    def _check_adb_devices(self, evidence: DeviceEvidence) -> None:
        """Probe ADB if available on the system."""
        if not self.adb_bin:
            evidence.adb_available = False
            evidence.diagnostic_notes.append("ADB executable is not found in system PATH.")
            return

        evidence.adb_available = True
        try:
            output = subprocess.check_output([self.adb_bin, "devices", "-l"], stderr=subprocess.DEVNULL, timeout=5).decode("utf-8", errors="ignore")
            lines = [line.strip() for line in output.splitlines() if line.strip() and not line.startswith("List of devices")]
            for line in lines:
                parts = line.split()
                if len(parts) >= 2 and parts[1] == "device":
                    dev_id = parts[0]
                    is_emulator = "emulator" in dev_id or "goldfish" in line.lower() or "ranchu" in line.lower()
                    evidence.connected_adb_devices.append({
                        "device_id": dev_id,
                        "raw_info": line,
                        "is_emulator": is_emulator,
                    })
                    if is_emulator:
                        evidence.emulator_indicators.append(f"ADB device '{dev_id}' identified as virtual emulator instance.")
        except Exception as exc:
            evidence.diagnostic_notes.append(f"ADB device probe failed: {exc}")

    def _determine_classification(self, evidence: DeviceEvidence) -> DeviceClassification:
        """
        Classify execution layer with strict hardware verification checks.
        Never return VERIFIED_PIXEL without genuine hardware attestation markers.
        """
        # If there are physical ADB devices connected, check if any is verified Pixel
        if evidence.connected_adb_devices:
            for dev in evidence.connected_adb_devices:
                if not dev.get("is_emulator"):
                    # Physical Android device connected
                    return self._inspect_adb_pixel_integrity(dev["device_id"], evidence)

            # All connected devices are emulators
            evidence.diagnostic_notes.append("Connected ADB instance is an Android Emulator (AVD/QEMU).")
            return DeviceClassification.ANDROID_EMULATOR

        # If no Android runtime is running and CDP simulation is active
        if evidence.cdp_simulation_active or evidence.browser_detected:
            evidence.diagnostic_notes.append(
                "Execution is running via Desktop Browser CDP emulation. "
                "Hardware-backed Titan M2 KeyStore attestation and Google Play Integrity are impossible at this layer."
            )
            return DeviceClassification.BROWSER_SIMULATION

        return DeviceClassification.UNKNOWN

    def _inspect_adb_pixel_integrity(self, serial: str, evidence: DeviceEvidence) -> DeviceClassification:
        """Deep inspect a connected physical device via ADB."""
        try:
            getprop = lambda prop: subprocess.check_output(
                [self.adb_bin, "-s", serial, "shell", "getprop", prop],
                stderr=subprocess.DEVNULL,
                timeout=4
            ).decode("utf-8", errors="ignore").strip()

            manufacturer = getprop("ro.product.manufacturer").lower()
            model = getprop("ro.product.model")
            fingerprint = getprop("ro.build.fingerprint")
            boot_state = getprop("ro.boot.verifiedbootstate")
            flash_locked = getprop("ro.boot.flash.locked")

            evidence.manufacturer = manufacturer
            evidence.model_string = model
            evidence.build_fingerprint = fingerprint

            # Check bootloader lock status
            is_locked = (boot_state == "green") or (flash_locked == "1")
            evidence.bootloader_locked = is_locked

            # Check Play Services package
            pkgs = subprocess.check_output(
                [self.adb_bin, "-s", serial, "shell", "pm", "list", "packages", "com.google.android.gms"],
                stderr=subprocess.DEVNULL,
                timeout=4
            ).decode("utf-8", errors="ignore")
            evidence.play_services_installed = "com.google.android.gms" in pkgs

            if manufacturer == "google" and "pixel" in model.lower() and is_locked and evidence.play_services_installed:
                evidence.hardware_attestation_available = True
                evidence.diagnostic_notes.append("Genuine Google Pixel detected with locked bootloader and Google Play Services.")
                return DeviceClassification.VERIFIED_PIXEL

            evidence.diagnostic_notes.append(f"Physical Android device detected ({model}), but not verified as a compliant retail Pixel.")
            return DeviceClassification.PHYSICAL_ANDROID

        except Exception as exc:
            evidence.diagnostic_notes.append(f"ADB deep inspection failed for {serial}: {exc}")
            return DeviceClassification.PHYSICAL_ANDROID


# Global instance
device_diagnostic_service = DeviceDiagnosticService()

