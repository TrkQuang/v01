"""
Browser Simulation Profile for Web UI and Viewport Research.

Note on Hardware Attestation:
This module configures Chrome DevTools Protocol (CDP) emulation metrics
(viewport, user-agent client hints) for web research. It does NOT and
CANNOT generate hardware-backed KeyStore attestation or Google Play
Integrity tokens required for native Pixel hardware promotions.
"""

import uuid
from dataclasses import dataclass, field
from typing import Dict

import config


@dataclass
class BrowserSimulationProfile:
    """Browser emulation profile for desktop Selenium sessions."""
    model: str = config.DEVICE_MODEL
    brand: str = config.DEVICE_BRAND
    manufacturer: str = config.DEVICE_MANUFACTURER
    android_version: str = config.ANDROID_VERSION
    android_sdk: str = config.ANDROID_SDK
    build_id: str = config.BUILD_ID
    chrome_version: str = config.CHROME_VERSION
    screen_width: int = config.SCREEN_CSS_WIDTH
    screen_height: int = config.SCREEN_CSS_HEIGHT
    pixel_ratio: float = config.SCREEN_PIXEL_RATIO
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    @property
    def user_agent(self) -> str:
        # Chrome 110+ UA Reduction format
        return (
            "Mozilla/5.0 (Linux; Android 10; K) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            f"Chrome/{self.chrome_version} Mobile Safari/537.36"
        )

    def client_hints_metadata(self) -> dict:
        """UserAgentMetadata dict for CDP Emulation.setUserAgentOverride."""
        major = str(config.CHROME_MAJOR_VERSION)
        return {
            "brands": [
                {"brand": "Google Chrome",  "version": major},
                {"brand": "Chromium",       "version": major},
                {"brand": "Not:A-Brand",    "version": "24"},
            ],
            "fullVersionList": [
                {"brand": "Google Chrome",  "version": self.chrome_version},
                {"brand": "Chromium",       "version": self.chrome_version},
                {"brand": "Not:A-Brand",    "version": "24.0.0.0"},
            ],
            "platform":        "Android",
            "platformVersion": f"{self.android_version}.0.0",
            "architecture":    "arm",
            "model":           self.model,
            "mobile":          True,
            "bitness":         "64",
            "wow64":           False,
        }

    def summary(self) -> str:
        return (
            f"🌐 *Simulated Web Profile*\n"
            f"Target Model: {self.model}\n"
            f"Simulated Android: {self.android_version} (API {self.android_sdk})\n"
            f"Browser: Chrome {self.chrome_version}\n"
            f"Viewport: {self.screen_width}×{self.screen_height} @{self.pixel_ratio}x\n"
            f"Session ID: `{self.session_id[:8]}…`\n\n"
            f"⚠️ *Verification Notice:* Running in browser emulation. Physical hardware keybox and Play Integrity tokens are unavailable."
        )


def create_browser_simulation_profile() -> BrowserSimulationProfile:
    """Create a fresh browser simulation profile."""
    return BrowserSimulationProfile()
