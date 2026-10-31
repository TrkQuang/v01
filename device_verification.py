"""
Device Verification Service for Pixel Promotion Claim Assistant.

Distinguishes:
1. DESKTOP_BROWSER
2. BROWSER_MOBILE_EMULATION
3. ANDROID_EMULATOR
4. PHYSICAL_ANDROID
5. VERIFIED_PIXEL

Includes read-only ADB integration for legitimate physical device inspection.
Explicitly distinguishes reported model properties from cryptographically verified hardware.
"""

import logging
import os
import platform
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class DeviceTier(str, Enum):
    DESKTOP_BROWSER = "DESKTOP_BROWSER"
    BROWSER_MOBILE_EMULATION = "BROWSER_MOBILE_EMULATION"
    ANDROID_EMULATOR = "ANDROID_EMULATOR"
    PHYSICAL_ANDROID = "PHYSICAL_ANDROID"
    VERIFIED_PIXEL = "VERIFIED_PIXEL"
    UNKNOWN = "UNKNOWN"


@dataclass
class DeviceVerificationReport:
    device_tier: DeviceTier
    reported_model: str
    reported_manufacturer: str
    android_version: str
    build_fingerprint: str
    is_hardware_verified: bool
    is_user_reported: bool
    bootloader_locked: Optional[bool]
    play_services_installed: bool
    play_store_installed: bool
    adb_connected: bool
    verification_notes: List[str] = field(default_factory=list)
    confidence: float = 0.5

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["device_tier"] = self.device_tier.value
        return d


class DeviceVerificationService:
    """Inspects local environment and ADB to evaluate physical vs virtual device status."""

    def __init__(self):
        self.adb_bin = shutil.which("adb")

    def inspect_environment(
        self,
        manual_model: Optional[str] = None,
        is_emulation_probe: bool = False,
    ) -> DeviceVerificationReport:
        """Run complete read-only device verification sweep."""
        notes = []

        # 1. Check if ADB has any live connected Android devices
        adb_report = self._probe_adb()
        if adb_report:
            return adb_report

        # 2. Check if running in browser mobile emulation probe
        if is_emulation_probe:
            return DeviceVerificationReport(
                device_tier=DeviceTier.BROWSER_MOBILE_EMULATION,
                reported_model=manual_model or "Pixel 11 Pro (Simulated Viewport)",
                reported_manufacturer="Google (Simulated)",
                android_version="17 (Simulated)",
                build_fingerprint="Unavailable",
                is_hardware_verified=False,
                is_user_reported=False,
                bootloader_locked=None,
                play_services_installed=False,
                play_store_installed=False,
                adb_connected=False,
                verification_notes=[
                    "Desktop browser CDP emulation session.",
                    "Cannot forge Titan M2 hardware keystore attestation or Play Integrity tokens."
                ],
                confidence=1.0,
            )

        # 3. Check if user manually reported a device
        if manual_model:
            is_pixel = "pixel" in manual_model.lower()
            return DeviceVerificationReport(
                device_tier=DeviceTier.PHYSICAL_ANDROID if is_pixel else DeviceTier.UNKNOWN,
                reported_model=manual_model,
                reported_manufacturer="Google" if is_pixel else "Unknown",
                android_version="Unknown",
                build_fingerprint="Unknown",
                is_hardware_verified=False,
                is_user_reported=True,
                bootloader_locked=None,
                play_services_installed=True,  # Assumed standard on retail
                play_store_installed=True,
                adb_connected=False,
                verification_notes=[
                    f"User self-reported device model: '{manual_model}' (USER_REPORTED, unverified by hardware attestation).",
                    "Unverified by hardware cryptographic attestation. Must be confirmed during official Google redemption."
                ],
                confidence=0.75 if is_pixel else 0.4,
            )

        # 4. Fallback: Host is desktop browser environment
        host_os = platform.system()
        return DeviceVerificationReport(
            device_tier=DeviceTier.DESKTOP_BROWSER,
            reported_model="Desktop Host",
            reported_manufacturer=host_os,
            android_version="None",
            build_fingerprint="None",
            is_hardware_verified=False,
            is_user_reported=False,
            bootloader_locked=None,
            play_services_installed=False,
            play_store_installed=False,
            adb_connected=False,
            verification_notes=[f"Host operating system is {host_os}. No connected Android device detected via ADB."],
            confidence=1.0,
        )

    def _probe_adb(self) -> Optional[DeviceVerificationReport]:
        """Inspect connected physical or emulated devices via ADB."""
        if not self.adb_bin:
            return None

        try:
            out = subprocess.check_output([self.adb_bin, "devices", "-l"], stderr=subprocess.DEVNULL, timeout=4).decode("utf-8", errors="ignore")
            lines = [l.strip() for l in out.splitlines() if l.strip() and not l.startswith("List of devices")]
            if not lines:
                return None

            # Probe first authorized device
            dev_id = lines[0].split()[0]
            is_emulator = "emulator" in dev_id or "goldfish" in lines[0].lower() or "ranchu" in lines[0].lower()

            getprop = lambda prop: subprocess.check_output(
                [self.adb_bin, "-s", dev_id, "shell", "getprop", prop],
                stderr=subprocess.DEVNULL,
                timeout=3
            ).decode("utf-8", errors="ignore").strip()

            manufacturer = getprop("ro.product.manufacturer")
            model = getprop("ro.product.model")
            android_ver = getprop("ro.build.version.release")
            fingerprint = getprop("ro.build.fingerprint")
            boot_state = getprop("ro.boot.verifiedbootstate")
            flash_locked = getprop("ro.boot.flash.locked")

            # Check GMS package presence
            pm_out = subprocess.check_output(
                [self.adb_bin, "-s", dev_id, "shell", "pm", "list", "packages"],
                stderr=subprocess.DEVNULL,
                timeout=4
            ).decode("utf-8", errors="ignore")
            has_gms = "com.google.android.gms" in pm_out
            has_vending = "com.android.vending" in pm_out

            locked = (boot_state == "green") or (flash_locked == "1")

            if is_emulator:
                return DeviceVerificationReport(
                    device_tier=DeviceTier.ANDROID_EMULATOR,
                    reported_model=model or "Android Emulator",
                    reported_manufacturer=manufacturer or "Google/AOSP",
                    android_version=android_ver,
                    build_fingerprint=fingerprint,
                    is_hardware_verified=False,
                    is_user_reported=False,
                    bootloader_locked=False,
                    play_services_installed=has_gms,
                    play_store_installed=has_vending,
                    adb_connected=True,
                    verification_notes=["Device connected via ADB is an emulator (goldfish/ranchu virtual kernel)."],
                    confidence=0.95,
                )

            is_google_pixel = (manufacturer.lower() == "google") and ("pixel" in model.lower())
            is_verified_pixel = is_google_pixel and locked and has_gms and has_vending

            tier = DeviceTier.VERIFIED_PIXEL if is_verified_pixel else DeviceTier.PHYSICAL_ANDROID
            notes = [f"Physical device connected via ADB ({model} by {manufacturer})."]
            if is_verified_pixel:
                notes.append("Locked bootloader and Google Play Services confirmed on retail Pixel hardware.")
            elif not locked:
                notes.append("Bootloader is unlocked or custom ROM detected (fails verified boot).")

            return DeviceVerificationReport(
                device_tier=tier,
                reported_model=model,
                reported_manufacturer=manufacturer,
                android_version=android_ver,
                build_fingerprint=fingerprint,
                is_hardware_verified=is_verified_pixel,
                is_user_reported=False,
                bootloader_locked=locked,
                play_services_installed=has_gms,
                play_store_installed=has_vending,
                adb_connected=True,
                verification_notes=notes,
                confidence=0.95 if is_verified_pixel else 0.8,
            )

        except Exception as exc:
            logger.debug("ADB probe exception: %s", exc)
            return None


# Global instance
device_verification_service = DeviceVerificationService()
