"""
Configuration and constants for the Pixel 11 Pro Google One Gemini Bot.
"""

import os
import subprocess

# ── Telegram ──────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8807729422:AAHW7lDWYV6q2jNtAtSBez7H-g0hdlZeKmQ")

# ── Device specs – Google Pixel 11 Pro (Android 17) ──────────────────────────
DEVICE_MODEL        = "Pixel 11 Pro"
DEVICE_CODENAME     = "grizzly"               # Pixel 11 Pro codename (XL is "kodiak")
DEVICE_BRAND        = "google"
DEVICE_MANUFACTURER = "Google"
ANDROID_VERSION     = "17"
ANDROID_SDK         = "37"
BUILD_ID            = "CD1A.261005.003"       # Pixel 11 Pro factory build ID

# Hardware profile (used for navigator injection)
DEVICE_RAM_GB           = 16                  # 16 GB RAM
DEVICE_CPU_CORES        = 7                   # Tensor G6 (malibu): 7 reported cores
DEVICE_MAX_TOUCH        = 5                   # 5-point multitouch (realistic)
DEVICE_GPU_VENDOR       = "Imagination Technologies"
DEVICE_GPU_RENDERER     = "PowerVR CXTP-48-1536"  # Tensor G6 GPU architecture

# Screen – Pixel 11 Pro: CSS viewport 412×915 @3.5× density (~495 PPI)
SCREEN_CSS_WIDTH    = 412
SCREEN_CSS_HEIGHT   = 915
SCREEN_PIXEL_RATIO  = 3.5

# ── Chrome Version ────────────────────────────────────────────────────────────
def _detect_chrome_version() -> str:
    """Detect installed Chrome/Chromium version or fallback to 156.0.8078.74."""
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

# ── User-Agent – Chrome UA Reduction (Chrome 110+) ───────────────────────────
USER_AGENT_TEMPLATES = [
    (
        "Mozilla/5.0 (Linux; Android 10; K) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/{chrome} Mobile Safari/537.36"
    ),
]

# ── Google URLs ───────────────────────────────────────────────────────────────
# NOTE: accounts.google.com/ServiceLogin?hl=en avoids high-risk service check
# that triggers "This browser or app may not be secure" block.
GMAIL_LOGIN_URL         = "https://accounts.google.com/ServiceLogin?hl=en"
GOOGLE_ONE_URL          = "https://one.google.com/"
GOOGLE_ONE_BENEFITS_URL = "https://one.google.com/benefits"
GOOGLE_ONE_OFFERS_URL   = "https://one.google.com/about/plans"

# ── Gemini / Google One Pixel offer detection keywords ──────────────────────
GEMINI_OFFER_KEYWORDS = [
    "gemini pro",
    "gemini advanced",
    "bard advanced",
    "bard_advanced",
    "12 month",
    "12-month",
    "6 month",
    "6-month",
    "3 month",
    "3-month",
    "free trial",
    "activate",
    "get started",
    "claim offer",
    "redeem",
    "benefit",
    "ưu đãi",
    "dùng thử",
    "quyền lợi",
]

# ── Selenium / WebDriver ──────────────────────────────────────────────────────
WEBDRIVER_TIMEOUT  = 30   # seconds – explicit wait
IMPLICIT_WAIT      = 10   # seconds
PAGE_LOAD_TIMEOUT  = 60   # seconds
HEADLESS           = False # Keep False so Chrome runs in headed/offscreen mode (bypasses Google bot detection)

# ── Session storage ───────────────────────────────────────────────────────────
SESSION_STORE: dict = {}

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_LEVEL  = "INFO"
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
