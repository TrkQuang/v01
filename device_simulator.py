"""
Android Pixel 11 Pro device simulator.

Each session gets unique identifiers (IMEI, Android ID, device fingerprint,
Chrome version patch) while the hardware identity remains "Pixel 11 Pro".

Key implementation detail:
  Chrome 110+ uses UA Reduction — the User-Agent string always shows
  "Android 10; K" regardless of real device. The actual device model
  is communicated via Sec-CH-UA-Model client hint (set via CDP).
"""

import random
import string
import uuid
from dataclasses import dataclass, field

import config


# ── Real Google Pixel TAC prefixes (Type Allocation Code) ────────────────────
PIXEL_TAC_PREFIXES = [
    "35272012",  # Pixel 9 Pro
    "35383711",  # Pixel 8 Pro
    "35174912",  # Pixel 7 Pro
    "35632208",  # Pixel 6a
    "35383714",  # Pixel 8
    "35272014",  # Pixel 9
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _luhn_checksum(number: str) -> int:
    digits = [int(d) for d in number]
    odd_digits = digits[-1::-2]
    even_digits = digits[-2::-2]
    total = sum(odd_digits)
    for d in even_digits:
        total += sum(divmod(d * 2, 10))
    return total % 10


def _generate_imei() -> str:
    """Generate a Luhn-valid IMEI using a real Google Pixel TAC prefix."""
    tac = random.choice(PIXEL_TAC_PREFIXES)   # 8-digit real TAC
    serial = "".join(random.choices(string.digits, k=6))
    partial = tac + serial                      # 14 digits
    check_digit = (10 - _luhn_checksum(partial + "0")) % 10
    return partial + str(check_digit)


def _generate_android_id() -> str:
    return "".join(random.choices("0123456789abcdef", k=16))


def _generate_device_fingerprint(model: str, build_id: str, android: str, codename: str = "") -> str:
    cname = codename or getattr(config, "DEVICE_CODENAME", "grizzly")
    return f"google/{cname}/{cname}:{android}/{build_id}/12589321:user/release-keys"


def _random_chrome_patch() -> str:
    """Return a realistic Chrome version string with slight random patch."""
    major = config.CHROME_MAJOR_VERSION
    build = random.randint(7880, 7920)
    patch = random.randint(120, 180)
    return f"{major}.0.{build}.{patch}"


# ── Device profile dataclass ──────────────────────────────────────────────────

@dataclass
class DeviceProfile:
    imei:               str
    android_id:         str
    device_fingerprint: str
    user_agent:         str
    chrome_version:     str
    session_id:         str = field(default_factory=lambda: str(uuid.uuid4()))

    # Fixed Pixel 11 Pro hardware identity
    model:           str   = config.DEVICE_MODEL
    brand:           str   = config.DEVICE_BRAND
    manufacturer:    str   = config.DEVICE_MANUFACTURER
    android_version: str   = config.ANDROID_VERSION
    android_sdk:     str   = config.ANDROID_SDK
    build_id:        str   = config.BUILD_ID

    # Hardware capabilities
    device_memory:          int   = config.DEVICE_RAM_GB
    hardware_concurrency:   int   = config.DEVICE_CPU_CORES
    max_touch_points:       int   = 5
    screen_width:           int   = config.SCREEN_CSS_WIDTH
    screen_height:          int   = config.SCREEN_CSS_HEIGHT
    pixel_ratio:            float = config.SCREEN_PIXEL_RATIO
    gpu_vendor:             str   = config.DEVICE_GPU_VENDOR
    gpu_renderer:           str   = config.DEVICE_GPU_RENDERER

    def client_hints_metadata(self) -> dict:
        """
        Full userAgentMetadata dict for CDP Emulation.setUserAgentOverride.
        """
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
            "platformVersion": f"{config.ANDROID_VERSION}.0.0",
            "architecture":    "arm",
            "model":           self.model,      # "Pixel 11 Pro"
            "mobile":          True,
            "bitness":         "64",
            "wow64":           False,
        }

    def as_headers(self) -> dict:
        return {
            "User-Agent":      self.user_agent,
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
        }

    def summary(self) -> str:
        return (
            f"📱 *Device Profile*\n"
            f"Model: {self.model}  |  Build: {self.build_id}\n"
            f"Android: {self.android_version}  |  Chrome: {self.chrome_version}\n"
            f"RAM: {self.device_memory}GB  |  CPU: {self.hardware_concurrency} cores\n"
            f"Screen: {self.screen_width}×{self.screen_height} @{self.pixel_ratio}×\n"
            f"GPU: {self.gpu_renderer}\n"
            f"IMEI: `{self.imei}`\n"
            f"Android ID: `{self.android_id}`\n"
            f"Session: `{self.session_id[:8]}…`"
        )


# ── Public factory ────────────────────────────────────────────────────────────

def create_device_profile() -> DeviceProfile:
    """
    Create a fresh Pixel 11 Pro device profile with unique per-session
    identifiers and a realistic hardware fingerprint.
    """
    chrome_version = _random_chrome_patch()

    template   = config.USER_AGENT_TEMPLATES[0]
    user_agent = template.format(chrome=chrome_version)

    fingerprint = _generate_device_fingerprint(
        config.DEVICE_MODEL,
        config.BUILD_ID,
        config.ANDROID_VERSION,
    )
    return DeviceProfile(
        imei=_generate_imei(),
        android_id=_generate_android_id(),
        device_fingerprint=fingerprint,
        user_agent=user_agent,
        chrome_version=chrome_version,
    )
