"""
Google One Web Diagnostic Probe.

Performs authorized, non-custodial browser probing of Google One endpoints to
observe public plan availability, promotional cards, and DOM indicators.

Never captures or stores plain passwords or TOTP secret seeds.
Never claims to forge hardware-backed device attestation.
"""

import logging
import os
import platform
import random
import time
from typing import Callable, Dict, Optional, Tuple
from urllib.parse import urlparse

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

import config
from device_simulator import BrowserSimulationProfile

logger = logging.getLogger(__name__)

ProgressCB = Optional[Callable[[str, Optional[bytes]], None]]


class GoogleAutomationError(Exception):
    """Raised when an automation probe encounters an unrecoverable failure."""


def _build_diagnostic_driver(profile: BrowserSimulationProfile) -> webdriver.Chrome:
    """Launch Chrome configured with mobile viewport and client hints."""
    options = Options()

    # Offscreen execution to avoid interfering with user desktop
    has_display = True
    if platform.system() == "Linux":
        has_display = bool(os.environ.get("DISPLAY"))

    if config.HEADLESS or not has_display:
        options.add_argument("--headless=new")
    else:
        options.add_argument("--window-position=-2400,-2400")

    options.add_argument(f"--window-size={profile.screen_width},{profile.screen_height}")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--lang=en-US")

    service = Service()
    driver = webdriver.Chrome(service=service, options=options)

    # CDP layer 1: Screen & Touch Metrics
    driver.execute_cdp_cmd(
        "Emulation.setDeviceMetricsOverride",
        {
            "width": profile.screen_width,
            "height": profile.screen_height,
            "deviceScaleFactor": profile.pixel_ratio,
            "mobile": True,
            "screenWidth": profile.screen_width,
            "screenHeight": profile.screen_height,
            "positionX": 0,
            "positionY": 0,
        },
    )

    # CDP layer 2: User-Agent & Client Hints
    driver.execute_cdp_cmd(
        "Emulation.setUserAgentOverride",
        {
            "userAgent": profile.user_agent,
            "acceptLanguage": "en-US,en;q=0.9",
            "platform": "Linux armv8l",
            "userAgentMetadata": profile.client_hints_metadata(),
        },
    )

    driver.implicitly_wait(config.IMPLICIT_WAIT)
    driver.set_page_load_timeout(config.PAGE_LOAD_TIMEOUT)
    return driver


def probe_google_one_endpoints(
    profile: BrowserSimulationProfile,
    target_url: Optional[str] = None,
    progress_callback: ProgressCB = None,
) -> Tuple[str, Dict[str, str], Optional[bytes]]:
    """
    Probe Google One public and benefits pages in mobile simulation mode.
    Returns (status_code, details, screenshot_bytes).
    """
    driver = None
    try:
        if progress_callback:
            progress_callback("🌐 Launching browser diagnostic probe...", None)

        driver = _build_diagnostic_driver(profile)
        url_to_check = target_url or config.GOOGLE_ONE_BENEFITS_URL

        if progress_callback:
            progress_callback(f"🔍 Probing endpoint: {url_to_check}", None)

        driver.get(url_to_check)
        time.sleep(3.5)

        # Capture screenshot of diagnostic landing
        screenshot = driver.get_screenshot_as_png()
        current_url = driver.current_url
        page_source = driver.page_source.lower()

        # Check for Google security/signin challenge
        if "accounts.google.com" in current_url:
            if "signin" in current_url or "challenge" in current_url:
                return (
                    "MANUAL_REVIEW_REQUIRED",
                    {
                        "url": current_url,
                        "observation": "Endpoint requires active Google Account authentication. Non-custodial sign-in required.",
                    },
                    screenshot,
                )

        # Scan for offer identifiers in DOM
        offer_keywords = [
            "bard_advanced",
            "tier0",
            "gemini advanced",
            "google ai",
            "ai premium",
            "claim offer",
            "nhận ưu đãi",
            "dùng thử",
        ]

        found_keywords = [kw for kw in offer_keywords if kw in page_source]
        links = driver.find_elements(By.TAG_NAME, "a")
        benefit_links = [
            l.get_attribute("href")
            for l in links
            if l.get_attribute("href") and ("benefit" in l.get_attribute("href").lower() or "offer" in l.get_attribute("href").lower())
        ]

        if found_keywords or benefit_links:
            return (
                "OFFER_VISIBLE",
                {
                    "url": current_url,
                    "matched_tokens": ", ".join(found_keywords),
                    "benefit_links_count": str(len(benefit_links)),
                    "first_link": benefit_links[0] if benefit_links else "None",
                },
                screenshot,
            )

        return (
            "OFFER_NOT_VISIBLE",
            {
                "url": current_url,
                "observation": "No promotional entitlement cards found on this web route without native GMS hardware attestation.",
            },
            screenshot,
        )

    except WebDriverException as exc:
        logger.error("Web diagnostic probe failure: %s", exc)
        return "UNKNOWN", {"error": str(exc)}, None
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass
