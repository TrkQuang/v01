"""
Google One automation using Selenium.

Logs into a Gmail account, navigates to Google One, detects the
12-month free Gemini Pro offer, and returns the activation / payment link.

progress_callback(msg, screenshot_bytes=None) is called at every key step
so callers can relay updates to Telegram in real time.
"""

import io
import logging
import os
import random
import re
import shutil
import time
from typing import Callable, Optional
from urllib.parse import urlparse

import pyotp
from selenium import webdriver
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

import config
from device_simulator import DeviceProfile

logger = logging.getLogger(__name__)

ProgressCB = Optional[Callable[[str, Optional[bytes]], None]]


# ── Screenshot helper ─────────────────────────────────────────────────────────

def _shot(driver: webdriver.Chrome) -> Optional[bytes]:
    """Return a PNG screenshot as bytes, or None on failure."""
    try:
        return driver.get_screenshot_as_png()
    except Exception:
        return None


def _report(cb: ProgressCB, msg: str, driver: Optional[webdriver.Chrome] = None) -> None:
    """Send a progress message (and optional screenshot) via the callback."""
    logger.info(msg)
    if cb:
        screenshot = _shot(driver) if driver else None
        try:
            cb(msg, screenshot)
        except Exception as e:
            logger.warning("progress_callback error: %s", e)


# ── Driver factory ────────────────────────────────────────────────────────────

def _patch_chromedriver(original_path: str) -> str:
    """Patch ChromeDriver binary to replace 'cdc_' signature with 'dog_'."""
    try:
        import stat
        import tempfile
        tmp_dir = os.path.join(tempfile.gettempdir(), "patched_chromedriver")
        os.makedirs(tmp_dir, exist_ok=True)
        patched_path = os.path.join(tmp_dir, "chromedriver")
        if os.path.exists(patched_path) and os.path.getsize(patched_path) > 0:
            return patched_path

        with open(original_path, "rb") as f:
            content = f.read()

        new_content = content.replace(b"cdc_", b"dog_")
        with open(patched_path, "wb") as f:
            f.write(new_content)

        st = os.stat(patched_path)
        os.chmod(patched_path, st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
        return patched_path
    except Exception as e:
        logger.warning("Could not patch chromedriver: %s", e)
        return original_path


def _human_type(el, text: str):
    """Simulate realistic human typing with random per-key delay."""
    el.click()
    time.sleep(random.uniform(0.2, 0.4))
    el.clear()
    time.sleep(random.uniform(0.1, 0.2))
    for char in text:
        el.send_keys(char)
        time.sleep(random.uniform(0.04, 0.12))
    time.sleep(random.uniform(0.4, 0.8))


def _build_driver(profile: DeviceProfile) -> webdriver.Chrome:
    """
    Return a headless Chrome WebDriver fully configured to impersonate a
    real Google Pixel 11 Pro running Android 17 / Chrome 152.

    Spoofing layers (applied in order):
      1. Chrome launch flags   – mobile emulation, reduced UA, anti-detection
      2. CDP commands          – authoritative screen metrics, UA client hints,
                                 touch emulation
      3. JS injection          – navigator props, WebGL GPU, battery, network,
                                 chrome runtime object, plugins
    """
    options = Options()

    # If running with Xvfb virtual display (DISPLAY=:99), run headed for max stealth
    has_display = bool(os.environ.get("DISPLAY"))
    if config.HEADLESS and not has_display:
        options.add_argument("--headless=new")

    # ── Core stability flags ──────────────────────────────────────────────────
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-notifications")
    options.add_argument("--mute-audio")
    options.add_argument("--disable-background-networking")
    options.add_argument("--disable-sync")
    options.add_argument("--metrics-recording-only")
    options.add_argument("--js-flags=--max-old-space-size=512")
    options.add_argument("--renderer-process-limit=1")

    # ── Realism flags (match a real Chrome on Android) ────────────────────────
    options.add_argument("--enable-features=NetworkService,NetworkServiceInProcess")
    options.add_argument("--lang=en-US")

    # ── Window size = Pixel 11 Pro CSS viewport ───────────────────────────────
    w, h = profile.screen_width, profile.screen_height
    options.add_argument(f"--window-size={w},{h}")
    options.add_argument(f"--user-agent={profile.user_agent}")

    # ── Anti-detection ────────────────────────────────────────────────────────
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    # ── Stealth launch options ────────────────────────────────────────────────
    options.add_argument("--disable-backgrounding-occluded-windows")
    options.add_argument("--disable-renderer-backgrounding")

    # ── Launch browser ────────────────────────────────────────────────────────
    chromium_binary = shutil.which("chromium") or shutil.which("chromium-browser")
    chromedriver_binary = shutil.which("chromedriver") or "chromedriver"
    if chromium_binary:
        options.binary_location = chromium_binary
    if os.path.isabs(chromedriver_binary) or shutil.which(chromedriver_binary):
        chromedriver_binary = _patch_chromedriver(shutil.which(chromedriver_binary) or chromedriver_binary)
    service = Service(executable_path=chromedriver_binary)
    driver = webdriver.Chrome(service=service, options=options)

    # ── CDP layer 1: authoritative screen metrics + touch ─────────────────────
    driver.execute_cdp_cmd("Emulation.setDeviceMetricsOverride", {
        "width":             w,
        "height":            h,
        "deviceScaleFactor": profile.pixel_ratio,
        "mobile":            True,
        "screenWidth":       w,
        "screenHeight":      h,
        "positionX":         0,
        "positionY":         0,
    })

    # ── CDP layer 2: User-Agent + full Sec-CH-UA-* client hints ──────────────
    # This is what Google reads to know the real device behind the reduced UA.
    driver.execute_cdp_cmd("Emulation.setUserAgentOverride", {
        "userAgent":         profile.user_agent,
        "acceptLanguage":    "en-US,en;q=0.9",
        "platform":          "Linux armv8l",
        "userAgentMetadata": profile.client_hints_metadata(),
    })

    # ── CDP layer 3: multitouch emulation ────────────────────────────────────
    driver.execute_cdp_cmd("Emulation.setTouchEmulationEnabled", {
        "enabled":       True,
        "maxTouchPoints": profile.max_touch_points,
    })

    # ── CDP layer 4: JS navigator/WebGL/battery/network spoofing ─────────────
    # Injected before every page's own JS runs.
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": profile.navigator_js()
    })

    driver.implicitly_wait(config.IMPLICIT_WAIT)
    driver.set_page_load_timeout(config.PAGE_LOAD_TIMEOUT)
    return driver


# ── Helpers ───────────────────────────────────────────────────────────────────

def _wait_for(driver: webdriver.Chrome, by: str, value: str,
              timeout: int = config.WEBDRIVER_TIMEOUT):
    """Return element after waiting for it to be clickable."""
    return WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((by, value))
    )


def _click_element_by_inner_text(driver: webdriver.Chrome,
                                 keyword: str, tag: str = "*") -> bool:
    """Click the first visible element whose full inner text contains keyword."""
    try:
        el = driver.find_element(
            By.XPATH,
            f"//{tag}[contains(translate(., "
            f"'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz')"
            f", '{keyword.lower()}')]"
        )
        if el.is_displayed():
            el.click()
            return True
    except Exception:
        pass
    # JS fallback — walks every element and checks innerText
    try:
        driver.execute_script(
            """
            var kw = arguments[0].toLowerCase();
            var els = document.querySelectorAll(arguments[1]);
            for (var i = 0; i < els.length; i++) {
                if (els[i].innerText && els[i].innerText.toLowerCase().includes(kw)
                        && els[i].offsetParent !== null) {
                    els[i].click();
                    return true;
                }
            }
            return false;
            """,
            keyword.lower(), tag
        )
        return True
    except Exception:
        pass
    return False


def _find_totp_field(driver: webdriver.Chrome):
    """
    Find ONLY the real 6-digit Google Authenticator input field.
    Returns None if the page is asking for a 10-digit Android Settings security code.
    """
    src = driver.page_source.lower()
    path = urlparse(driver.current_url).path

    # If currently on the ootp (10-digit offline security code) challenge page, do NOT match it as TOTP!
    if "ootp" in path or ("security code" in src and ("settings app" in src or "settings" in src)) or "get your android" in src:
        return None

    for inp in driver.find_elements(By.CSS_SELECTOR, "input"):
        try:
            if (inp.get_attribute("aria-hidden") or "").lower() == "true":
                continue
            if not inp.is_displayed():
                continue
            iname = (inp.get_attribute("name") or "").lower()
            iid = (inp.get_attribute("id") or "").lower()
            itype = (inp.get_attribute("type") or "").lower()
            iac = (inp.get_attribute("autocomplete") or "").lower()

            if "totp" in iname or "totp" in iid or iname == "totppin" or iid == "totppin":
                return inp
            if iac == "one-time-code":
                return inp
            if "pin" in iname and "security" not in iname:
                return inp
            if itype in ("tel", "number", "text") and ("authenticator" in src or "totp" in path):
                return inp
        except Exception:
            continue
    return None


def _enter_totp(driver: webdriver.Chrome, totp_secret: str,
                cb: ProgressCB = None) -> bool:
    """Generate a fresh TOTP code and fill it into the visible input. Returns True on submit."""
    totp_field = _find_totp_field(driver)
    if not totp_field:
        _report(cb, "⚠️ Google Authenticator 6-digit input field not found on this page", driver)
        return False

    code = _generate_totp(totp_secret)
    secs_left = 30 - (int(time.time()) % 30)
    _report(cb, f"🔢 Entering TOTP code: `{code}` ({secs_left}s remaining)", driver)

    _human_type(totp_field, code)
    time.sleep(0.5)

    # Submit
    for sid in ["totpNext", "passwordNext"]:
        try:
            btn = driver.find_element(By.ID, sid)
            if btn.is_displayed():
                btn.click()
                return True
        except NoSuchElementException:
            continue
    try:
        btn = driver.find_element(
            By.CSS_SELECTOR, 'button[type="submit"], [jsname="LgbsSe"], button[type="button"]'
        )
        if btn.is_displayed():
            btn.click()
            return True
    except NoSuchElementException:
        pass
    return False


def _click_authenticator_option(driver: webdriver.Chrome,
                                cb: ProgressCB = None) -> bool:
    """Click the Authenticator app option on Google's method-selection page."""
    # Method 1: Target via Selenium XPath
    xpaths = [
        "//*[@data-challengetype='6']",
        "//li[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'authenticator')]",
        "//*[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'authenticator') and (@role='button' or @role='link')]",
        "//li[.//span[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'authenticator')]]",
        "//li[.//div[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'authenticator')]]",
    ]
    for xp in xpaths:
        try:
            for el in driver.find_elements(By.XPATH, xp):
                if el.is_displayed():
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", el)
                    time.sleep(0.2)
                    try:
                        el.click()
                        _report(cb, "✅ Clicked Authenticator option via XPath", driver)
                        return True
                    except Exception:
                        from selenium.webdriver.common.action_chains import ActionChains
                        ActionChains(driver).move_to_element(el).pause(0.2).click().perform()
                        _report(cb, "✅ Clicked Authenticator option via ActionChains", driver)
                        return True
        except Exception:
            continue

    # Method 2: Comprehensive JS query and event dispatch
    result = driver.execute_script(
        """
        // Strategy A: data-challengetype="6" = TOTP (Google Authenticator).
        var directEl = document.querySelector('[data-action="selectchallenge"][data-challengetype="6"], [data-challengetype="6"]');
        if (directEl && directEl.offsetParent !== null) {
            directEl.scrollIntoView({block: 'center'});
            directEl.click();
            return 'direct_challengetype6';
        }

        // Strategy B: find li or interactive element containing 'authenticator'
        var items = document.querySelectorAll('li, [role="link"], [role="button"], [role="option"], [data-action="selectchallenge"]');
        for (var i = 0; i < items.length; i++) {
            var item = items[i];
            var t = (item.innerText || item.textContent || '').toLowerCase();
            if ((t.includes('authenticator') || t.includes('xác minh từ ứng dụng') || t.includes('authenticator app'))
                    && item.offsetParent !== null) {
                item.scrollIntoView({block: 'center'});
                var child = item.querySelector('a, button, [role="button"], [role="link"], div');
                if (child) {
                    child.click();
                    return 'item_child:' + child.tagName;
                }
                item.click();
                return 'item:' + item.tagName;
            }
        }
        return 'not_found';
        """
    )
    _report(cb, f"🔍 Authenticator option click result: {result}", driver)
    return result != "not_found"


def _click_try_another_way(driver: webdriver.Chrome) -> bool:
    """Click the 'Try another way' link/button. Returns True on success."""
    xpaths = [
        "//span[normalize-space(text())='Try another way']",
        "//button[.//span[contains(text(), 'Try another way')]]",
        "//button[contains(., 'Try another way')]",
        "//a[contains(., 'Try another way')]",
        "//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'try another way')]",
        "//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'thử cách khác')]",
    ]

    for xp in xpaths:
        try:
            elements = driver.find_elements(By.XPATH, xp)
            for el in elements:
                if el.is_displayed():
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", el)
                    time.sleep(0.2)
                    try:
                        el.click()
                        return True
                    except Exception:
                        pass
        except Exception:
            continue

    try:
        from selenium.webdriver.common.action_chains import ActionChains
        for xp in xpaths[:3]:
            for el in driver.find_elements(By.XPATH, xp):
                if el.is_displayed():
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", el)
                    ActionChains(driver).move_to_element(el).pause(0.2).click().perform()
                    return True
    except Exception:
        pass

    try:
        res = driver.execute_script(
            """
            var candidates = document.querySelectorAll('button, a, span, div[role="button"]');
            for (var i = 0; i < candidates.length; i++) {
                var el = candidates[i];
                var t = (el.innerText || el.textContent || '').trim().toLowerCase();
                if (t === 'try another way' || t.includes('try another way') || t.includes('thử cách khác')) {
                    var btn = el.closest('button') || el.closest('a') || el;
                    btn.scrollIntoView({block: 'center'});
                    btn.dispatchEvent(new MouseEvent('mousedown', {bubbles: true, cancelable: true}));
                    btn.dispatchEvent(new MouseEvent('mouseup', {bubbles: true, cancelable: true}));
                    btn.click();
                    return true;
                }
            }
            return false;
            """
        )
        if res:
            return True
    except Exception:
        pass

    return False


def _handle_2fa(driver: webdriver.Chrome, totp_secret: str,
                cb: ProgressCB = None) -> bool:
    """
    Handle Google 2FA challenges. If the initial challenge is a device prompt,
    Security Code (10-digit from Android settings), or g.co/sc code, click
    'Try another way', select Google Authenticator, and submit the 6-digit TOTP code.
    """
    for attempt in range(1, 8):
        time.sleep(2)
        current_url = driver.current_url
        parsed = urlparse(current_url)
        hostname = parsed.hostname or ""
        path = parsed.path or ""

        # Check if already logged in past 2FA
        if ("accounts.google.com" not in hostname
                or hostname == "myaccount.google.com"
                or (hostname.endswith(".google.com") and "/u/" in path and "signin" not in path and "challenge" not in path)):
            _report(cb, "✅ Step 4/6 — 2FA passed, logged in!", driver)
            return True

        src = driver.page_source.lower()
        _report(cb, f"🔐 Step 4/6 (Attempt {attempt}) — 2FA checkpoint\n📍 {path}", driver)

        # 1. Are we on the Authenticator TOTP input screen?
        totp_input = _find_totp_field(driver)
        if totp_input and ("authenticator" in src or "totp" in path or "totp" in (totp_input.get_attribute("name") or "").lower()):
            _report(cb, "🔑 Step 4 — Google Authenticator 6-digit input detected. Entering code…", driver)
            submitted = _enter_totp(driver, totp_secret, cb)
            if submitted:
                time.sleep(3.5)
                new_src = driver.page_source.lower()
                new_path = urlparse(driver.current_url).path
                if "wrong code" in new_src or "wrong number of digits" in new_src:
                    _report(cb, "⚠️ Code rejected, retrying with next code…", driver)
                    time.sleep(2)
                    continue
                if "signin" not in new_path and "challenge" not in new_path:
                    _report(cb, "✅ Step 4 — 2FA verified successfully!", driver)
                    return True
                time.sleep(2)
                continue

        # 2. Are we on the Method Selection page (list of 2FA options)?
        is_selection_page = "selection" in path or ("authenticator" in src and not totp_input)
        if is_selection_page:
            _report(cb, "🔍 Step 4 — Method selection list detected. Selecting 'Google Authenticator'…", driver)
            picked = _click_authenticator_option(driver, cb)
            time.sleep(3)
            continue

        # 3. Are we on a Non-Authenticator Challenge (Security code / ootp / prompt / etc.)?
        has_try_another_way = "try another way" in src or "thử cách khác" in src
        if has_try_another_way:
            reason = "Security code (ootp)" if "ootp" in path or "security code" in src else "Device verification"
            _report(cb, f"🔄 Step 4 — {reason} screen detected. Clicking 'Try another way'…", driver)
            clicked = _click_try_another_way(driver)
            _report(cb, f"{'✅' if clicked else '⚠️'} Clicked 'Try another way', waiting for method list…", driver)
            time.sleep(3)
            continue

    return False


def _generate_totp(secret: str) -> str:
    """Generate the current TOTP code from a base32 secret."""
    totp = pyotp.TOTP(secret)
    code = totp.now()
    secs_left = 30 - (int(time.time()) % 30)
    logger.info("Generated TOTP: %s (%ds left)", code, secs_left)
    return code


# ── Login ─────────────────────────────────────────────────────────────────────

def _gmail_login(driver: webdriver.Chrome, email: str, password: str,
                 totp_secret: Optional[str] = None,
                 cb: ProgressCB = None) -> bool:
    """
    Perform Gmail login with optional TOTP 2FA.
    Calls cb() with a message + screenshot at every key step.
    Returns True on success, False on detectable failure.
    """
    try:
        # ── Step 1: Load login page ───────────────────────────────────────────
        _report(cb, "🌐 Step 1/6 — Loading Google sign-in page…", driver)
        driver.get(config.GMAIL_LOGIN_URL)
        time.sleep(2)

        # ── Step 2: Enter email ───────────────────────────────────────────────
        _report(cb, f"📧 Step 2/6 — Entering email: {email}", driver)
        email_field = _wait_for(driver, By.CSS_SELECTOR,
                                'input[name="identifier"], input[type="email"]')
        _human_type(email_field, email)
        time.sleep(random.uniform(0.6, 1.2))
        _wait_for(driver, By.ID, "identifierNext").click()
        time.sleep(3)

        # Early check: Detect Google anti-bot block before password step
        page_src = driver.page_source.lower()
        if "couldn't sign you in" in page_src or "this browser or app may not be secure" in page_src:
            _report(cb, "❌ Step 2/6 — Google blocked login (This browser or app may not be secure).", driver)
            return False

        # ── Step 3: Enter password ────────────────────────────────────────────
        _report(cb, "🔒 Step 3/6 — Entering password…", driver)
        password_field = _wait_for(driver, By.CSS_SELECTOR,
                                   'input[type="password"]')
        _human_type(password_field, password)
        time.sleep(random.uniform(0.6, 1.2))
        _wait_for(driver, By.ID, "passwordNext").click()
        time.sleep(3)

        # ── Step 4: 2FA / TOTP ────────────────────────────────────────────────
        if totp_secret:
            _report(cb, "🔐 Step 4/6 — Checking for 2FA challenge…", driver)
            ok_2fa = _handle_2fa(driver, totp_secret, cb)
            if not ok_2fa:
                current_path = urlparse(driver.current_url).path
                if "challenge" in current_path or "signin" in current_path:
                    _report(cb, "❌ Step 4/6 — 2FA was not completed. Please check your TOTP secret or 2FA methods.", driver)
                    return False

        # ── Step 5: Verify login ──────────────────────────────────────────────
        current_url = driver.current_url
        parsed = urlparse(current_url)
        hostname = parsed.hostname or ""
        path = parsed.path or ""

        # Check for visible error text
        try:
            error_el = driver.find_element(
                By.CSS_SELECTOR, '[jsname="B34EJ"], [aria-live="assertive"]'
            )
            if error_el.text.strip():
                _report(cb,
                        f"❌ Step 5/6 — Login error: {error_el.text.strip()}",
                        driver)
                return False
        except NoSuchElementException:
            pass

        if (hostname == "myaccount.google.com"
                or (hostname.endswith(".google.com") and "/u/" in path and "signin" not in path and "challenge" not in path)):
            _report(cb, "✅ Step 5/6 — Logged in successfully!", driver)
            return True

        # If still on accounts.google.com challenge or signin, it is NOT logged in!
        if hostname == "accounts.google.com" and ("signin" in path or "challenge" in path or "rejected" in path):
            _report(cb,
                    f"❌ Step 5/6 — Still on verification/sign-in page\n"
                    f"📍 URL: {current_url[:80]}",
                    driver)
            return False

        _report(cb,
                f"✅ Step 5/6 — Login appears successful\n"
                f"📍 URL: {current_url[:80]}",
                driver)
        return True

    except TimeoutException as exc:
        _report(cb, f"⏱️ Timeout during login: {exc}", driver)
        return False
    except WebDriverException as exc:
        _report(cb, f"❌ WebDriver error during login: {exc}", driver)
        return False


# ── Offer detection ───────────────────────────────────────────────────────────

def _extract_payment_link(driver: webdriver.Chrome) -> Optional[str]:
    """Scan current page for a Gemini Pro offer / activation link."""
    keywords = config.GEMINI_OFFER_KEYWORDS
    url_pat = re.compile(
        r"(gemini|upgrade|activate|offer|redeem|trial|checkout)",
        re.IGNORECASE,
    )

    all_links = driver.find_elements(By.TAG_NAME, "a")

    for link in all_links:
        try:
            text = (link.text + " " + (link.get_attribute("aria-label") or "")).lower()
            href = link.get_attribute("href") or ""
            if any(kw in text for kw in keywords) and href:
                return href
        except Exception:
            continue

    for link in all_links:
        try:
            href = link.get_attribute("href") or ""
            if url_pat.search(href):
                return href
        except Exception:
            continue

    for btn in driver.find_elements(By.CSS_SELECTOR, "button, [role='button']"):
        try:
            if any(kw in btn.text.lower() for kw in keywords):
                try:
                    parent = btn.find_element(By.XPATH, "ancestor::a")
                    href = parent.get_attribute("href") or ""
                    if href:
                        return href
                except NoSuchElementException:
                    pass
                return driver.current_url
        except Exception:
            continue

    return None


def _navigate_google_one(driver: webdriver.Chrome,
                         cb: ProgressCB = None) -> Optional[str]:
    """Navigate Google One pages and return the Gemini offer link."""
    for url in (config.GOOGLE_ONE_URL, config.GOOGLE_ONE_OFFERS_URL):
        try:
            _report(cb, f"🔍 Step 6/6 — Scanning: {url}", driver)
            driver.get(url)
            time.sleep(3)

            for selector in (
                '[aria-label="Accept all"]',
                'button[jsname="higCR"]',
                '[data-action="accept"]',
            ):
                try:
                    driver.find_element(By.CSS_SELECTOR, selector).click()
                    time.sleep(1)
                    break
                except NoSuchElementException:
                    pass

            _report(cb, f"🔎 Searching page for Gemini offer links…", driver)
            link = _extract_payment_link(driver)
            if link:
                _report(cb,
                        f"🎯 Offer link found!\n🔗 {link}",
                        driver)
                return link
            else:
                _report(cb, f"😔 No offer link on {url}, trying next…", driver)

        except (TimeoutException, WebDriverException) as exc:
            _report(cb, f"⚠️ Error loading {url}: {exc}", driver)

    return None


# ── Public API ────────────────────────────────────────────────────────────────

class GoogleAutomationError(Exception):
    """Raised when automation encounters an unrecoverable error."""


def check_gemini_offer(email: str, password: str,
                       device: DeviceProfile,
                       totp_secret: Optional[str] = None,
                       progress_callback: ProgressCB = None) -> Optional[str]:
    """
    Main entry point.

    Logs into email/password with optional TOTP, navigates to Google One,
    and returns the Gemini Pro offer link (or None).

    progress_callback(msg: str, screenshot_bytes: Optional[bytes]) is called
    at every key step so the caller can relay live updates to Telegram.
    """
    driver: Optional[webdriver.Chrome] = None
    try:
        _report(progress_callback,
                f"🤖 Starting Pixel 11 Pro simulator\n"
                f"📱 Session: {device.session_id[:8]}…\n"
                f"🌐 User-Agent: {device.user_agent[:60]}…")

        driver = _build_driver(device)
        _report(progress_callback, "✅ Browser launched successfully", driver)

        logged_in = _gmail_login(
            driver, email, password,
            totp_secret=totp_secret,
            cb=progress_callback,
        )
        if not logged_in:
            raise GoogleAutomationError(
                "Login failed — please check your credentials."
            )

        offer_link = _navigate_google_one(driver, cb=progress_callback)
        return offer_link

    finally:
        if driver:
            try:
                _report(progress_callback, "🧹 Closing browser session…")
                driver.quit()
            except Exception:
                pass
