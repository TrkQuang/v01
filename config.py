"""
Configuration and constants for Pixel Promotion Research & Diagnostic Platform.
"""

import os
import subprocess
from pathlib import Path

# ── Telegram ──────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.environ.get(
    "TELEGRAM_BOT_TOKEN",
    "8807729422:AAHW7lDWYV6q2jNtAtSBez7H-g0hdlZeKmQ",
)

# ── Database ──────────────────────────────────────────────────────────────────
DEFAULT_DB_PATH = Path(__file__).parent / "pixel_diagnostics.db"
DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH}")

# ── Device Profile Parameters for Web Emulation ──────────────────────────────
# Used solely for viewport and browser Client Hints research testing
DEVICE_MODEL        = "Pixel 11 Pro"
DEVICE_CODENAME     = "grizzly"
DEVICE_BRAND        = "google"
DEVICE_MANUFACTURER = "Google"
ANDROID_VERSION     = "17"
ANDROID_SDK         = "37"
BUILD_ID            = "CD1A.261005.003"

# CSS Viewport settings (Pixel standard 412x915 @3.5x density)
SCREEN_CSS_WIDTH    = 412
SCREEN_CSS_HEIGHT   = 915
SCREEN_PIXEL_RATIO  = 3.5

# ── Chrome Version Detection ──────────────────────────────────────────────────
def _detect_chrome_version() -> str:
    """Detect installed Chrome/Chromium version or fallback."""
    for cmd in ["google-chrome --version", "google-chrome-stable --version", "chromium --version", "chrome --version"]:
        try:
            out = subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL).decode().strip()
            parts = [p for p in out.split() if "." in p]
            if parts:
                return parts[0]
        except Exception:
            pass
    return "156.0.8078.74"

CHROME_VERSION       = _detect_chrome_version()
CHROME_MAJOR_VERSION = int(CHROME_VERSION.split(".")[0]) if "." in CHROME_VERSION else 156

# ── Google URLs ───────────────────────────────────────────────────────────────
GMAIL_LOGIN_URL             = "https://accounts.google.com/ServiceLogin?hl=en"
GOOGLE_ONE_URL              = "https://one.google.com/"
GOOGLE_ONE_BENEFITS_URL     = "https://one.google.com/benefits"
GOOGLE_ONE_DIRECT_OFFER_URL = "https://one.google.com/benefits/LOCKED:BARD_ADVANCED_MODE:BENEFIT_OFFERING_MEMBER:IN:TIER0?from=1"
GOOGLE_ONE_OFFERS_URL       = "https://one.google.com/about/plans"

# ── Hardware Profile for Navigator Spoofing ──────────────────────────────────
DEVICE_RAM_GB       = 16
DEVICE_CPU_CORES    = 7
DEVICE_GPU_VENDOR   = "Imagination Technologies"
DEVICE_GPU_RENDERER = "PowerVR CXTP-48-1536"

# ── User-Agent ────────────────────────────────────────────────────────────────
USER_AGENT_TEMPLATES = [
    (
        "Mozilla/5.0 (Linux; Android 10; K) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/{chrome} Mobile Safari/537.36"
    ),
]

# ── Gemini Offer Detection Keywords ──────────────────────────────────────────
GEMINI_OFFER_KEYWORDS = [
    "gemini pro",
    "gemini advanced",
    "bard advanced",
    "bard_advanced",
    "12 month",
    "12-month",
    "6 month",
    "6-month",
    "free trial",
    "claim offer",
    "redeem",
    "google ai pro",
    "5 tb",
    "ưu đãi",
    "dùng thử",
]

# ── Session Storage ───────────────────────────────────────────────────────────
SESSION_STORE: dict = {}

# ── Webdriver Settings ────────────────────────────────────────────────────────
WEBDRIVER_TIMEOUT = 25
IMPLICIT_WAIT     = 8
PAGE_LOAD_TIMEOUT = 45
HEADLESS          = False

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_LEVEL  = os.environ.get("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
