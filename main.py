"""
Pixel Promotion Diagnostic & Research Platform – Telegram Bot.

Commands:
  /start        – Platform overview & privacy notice
  /status       – Current platform status, DB health & runtime environment
  /device       – Device diagnostic sweep (Hardware vs Emulator vs Browser)
  /eligibility  – Interactive regional & account eligibility checker
  /diagnose     – Execute full diagnostic battery against Google One endpoints
  /history      – View user diagnostic run history and error codes
  /help         – Command documentation and troubleshooting guide

Security Policy:
Never prompts for, captures, or stores Google passwords, recovery codes, or 2FA seeds.
"""

import asyncio
import io
import logging
import uuid
from datetime import datetime, timezone

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

import config
from country_service import country_service
from database import get_db, get_or_create_user, init_db
from device_diagnostics import DeviceClassification, device_diagnostic_service
from device_simulator import create_browser_simulation_profile
from google_automation import probe_google_one_endpoints
from models import AuditLog, DiagnosticSession, EligibilityResult
from promotion_diagnostics import DiagnosticResultCode, promotion_diagnostic_engine

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(level=config.LOG_LEVEL, format=config.LOG_FORMAT)
logger = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _log_audit_event(telegram_id: int | str, action: str, details: str = None) -> None:
    try:
        with get_db() as db:
            user = get_or_create_user(db, telegram_id)
            log = AuditLog(user_id=user.id, action=action, details=details, timestamp=datetime.now(timezone.utc))
            db.add(log)
    except Exception as exc:
        logger.warning("Audit logging failed: %s", exc)


# ── Command Handlers ──────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send platform overview and menu."""
    user = update.effective_user
    chat_id = update.effective_chat.id

    with get_db() as db:
        get_or_create_user(db, user.id, username=user.username, first_name=user.first_name)
    _log_audit_event(user.id, "CMD_START")

    keyboard = [
        [
            InlineKeyboardButton("📱 Check Device", callback_data="run_device_check"),
            InlineKeyboardButton("🌍 Check Region", callback_data="run_region_menu"),
        ],
        [
            InlineKeyboardButton("🔬 Run Full Diagnosis", callback_data="run_full_diagnose"),
            InlineKeyboardButton("📊 My History", callback_data="show_history"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = (
        f"👋 *Welcome to the Pixel Promotion Diagnostic Platform*, {user.first_name}!\n\n"
        "This platform investigates **Google Pixel promotional eligibility** (e.g. Google AI Pro / Gemini Advanced) "
        "and isolates why simulated environments fail to claim hardware-bound offers.\n\n"
        "🔒 *Security Directive:*\n"
        "This service **never requests or stores passwords, 2FA seeds, or session cookies**.\n\n"
        "📋 *Core Commands:*\n"
        "• /device — Inspect host execution layer & hardware proof\n"
        "• /eligibility — Test country & account type eligibility\n"
        "• /diagnose — Run comprehensive diagnostic battery\n"
        "• /status — View backend status & active environment\n"
        "• /history — View past diagnostic runs\n"
        "• /help — Detailed documentation & error code guide"
    )
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display platform health, database status, and host details."""
    user = update.effective_user
    _log_audit_event(user.id, "CMD_STATUS")

    dev_class, evidence = device_diagnostic_service.inspect_environment()

    text = (
        "📊 *Platform Status & Environment Overview*\n\n"
        f"• **Execution Tier:** `{dev_class.value}`\n"
        f"• **Host OS:** `{evidence.host_os} ({evidence.host_arch})`\n"
        f"• **Browser Detected:** `{'Yes (' + evidence.browser_name + ')' if evidence.browser_detected else 'No'}`\n"
        f"• **ADB Available:** `{'Yes' if evidence.adb_available else 'No'}`\n"
        f"• **Connected ADB Devices:** `{len(evidence.connected_adb_devices)}`\n"
        f"• **Hardware Attestation:** `{'Available' if evidence.hardware_attestation_available else 'Unavailable (Simulated/Desktop)'}`\n\n"
        "💡 *Diagnostic Fact:*\n"
        "Google hardware promotions require **Google Play Integrity (MEETS_DEVICE_INTEGRITY)** backed by factory Titan M2 chips. "
        "Desktop browsers and standard emulators cannot generate these attestation tokens."
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def device(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Run device diagnostic probe and explain limitations."""
    user = update.effective_user
    _log_audit_event(user.id, "CMD_DEVICE")

    sim_profile = create_browser_simulation_profile()
    dev_class, evidence = device_diagnostic_service.inspect_environment(sim_profile.__dict__)

    status_emoji = "✅" if dev_class == DeviceClassification.VERIFIED_PIXEL else "⚠️"

    text = (
        f"📱 *Device Environment Diagnostic Report* {status_emoji}\n\n"
        f"• **Detected Layer:** `{dev_class.value}`\n"
        f"• **Target Simulated Model:** `{sim_profile.model}`\n"
        f"• **Simulated Android Version:** `{sim_profile.android_version}`\n"
        f"• **Simulated Viewport:** `{sim_profile.screen_width}x{sim_profile.screen_height} @{sim_profile.pixel_ratio}x`\n"
        f"• **Bootloader State:** `{'Locked (Verified)' if evidence.bootloader_locked else 'Not Hardware Verified'}`\n"
        f"• **Google Play Services:** `{'Installed' if evidence.play_services_installed else 'Absent at host layer'}`\n\n"
        "🔬 *Analysis:*\n"
    )
    if dev_class == DeviceClassification.BROWSER_SIMULATION:
        text += (
            "You are running within a **Desktop Browser Simulation**.\n"
            "While CSS viewports and Client Hints (`Sec-CH-UA-Model`) can mimic Pixel dimensions, "
            "Google One requires **Titan M2 hardware keystore attestation** via Google Play Services. "
            "Simulated HTTP headers will **never** unlock hardware-bound promotional offers."
        )
    elif dev_class == DeviceClassification.ANDROID_EMULATOR:
        text += (
            "Detected an **Android Studio / AVD Emulator**.\n"
            "Virtual devices fail Google Play Integrity (`MEETS_DEVICE_INTEGRITY`) and are rejected by Google promotional entitlement servers."
        )
    elif dev_class == DeviceClassification.VERIFIED_PIXEL:
        text += "Genuine Google Pixel hardware verified. Device meets promotional attestation prerequisites."
    else:
        text += "Device layer is indeterminate. Please connect physical hardware via ADB for deeper inspection."

    await update.message.reply_text(text, parse_mode="Markdown")


async def eligibility(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Present interactive country eligibility menu."""
    user = update.effective_user
    _log_audit_event(user.id, "CMD_ELIGIBILITY")

    keyboard = [
        [
            InlineKeyboardButton("🇺🇸 United States", callback_data="check_country_US"),
            InlineKeyboardButton("🇬🇧 United Kingdom", callback_data="check_country_GB"),
        ],
        [
            InlineKeyboardButton("🇩🇪 Germany", callback_data="check_country_DE"),
            InlineKeyboardButton("🇯🇵 Japan", callback_data="check_country_JP"),
        ],
        [
            InlineKeyboardButton("🇻🇳 Vietnam", callback_data="check_country_VN"),
            InlineKeyboardButton("🇮🇳 India", callback_data="check_country_IN"),
        ],
        [
            InlineKeyboardButton("🇨🇦 Canada", callback_data="check_country_CA"),
            InlineKeyboardButton("🇦🇺 Australia", callback_data="check_country_AU"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "🌍 *Regional & Country Eligibility Checker*\n\n"
        "Select your Google Play Store / Google Account billing country to verify promotional availability:",
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )


async def diagnose(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Run full diagnostic battery (Device + Region + Web Observation)."""
    user = update.effective_user
    chat_id = update.effective_chat.id
    _log_audit_event(user.id, "CMD_DIAGNOSE")

    status_msg = await update.message.reply_text(
        "🚀 *Starting Comprehensive Promotion Diagnostic Battery…*\n\n"
        "1️⃣ Inspecting execution layer & hardware proof…",
        parse_mode="Markdown",
    )

    sim_profile = create_browser_simulation_profile()
    dev_class, evidence = device_diagnostic_service.inspect_environment(sim_profile.__dict__)

    await status_msg.edit_text(
        "🚀 *Diagnostic in Progress…*\n\n"
        f"1️⃣ Execution Layer: `{dev_class.value}` ✅\n"
        "2️⃣ Probing Google One web endpoint…",
        parse_mode="Markdown",
    )

    loop = asyncio.get_event_loop()
    web_status, web_details, screenshot = await loop.run_in_executor(
        None,
        lambda: probe_google_one_endpoints(sim_profile, config.GOOGLE_ONE_BENEFITS_URL),
    )

    # Run promotion diagnostic engine evaluation
    report = promotion_diagnostic_engine.evaluate(
        device_class=dev_class,
        device_evidence=evidence,
        country_code="US",
        web_observed_status=web_status,
    )

    # Persist session to database
    with get_db() as db:
        db_user = get_or_create_user(db, user.id, username=user.username, first_name=user.first_name)
        session = DiagnosticSession(
            user_id=db_user.id,
            session_uuid=str(uuid.uuid4()),
            target_region="US",
            overall_status=report.overall_code.value,
            confidence=report.confidence,
            summary_text=report.summary,
            completed_at=datetime.now(timezone.utc),
        )
        db.add(session)
        db.flush()

        for f in report.findings:
            db.add(
                EligibilityResult(
                    session_id=session.id,
                    check_name=f.check_name,
                    result_code=f.result_code.value,
                    passed=f.passed,
                    confidence=f.confidence,
                    evidence=f.evidence,
                    recommendation=f.recommended_step,
                )
            )

    # Format structured Telegram response
    result_emoji = "✅" if report.overall_code == DiagnosticResultCode.OFFER_VISIBLE else "❌"
    findings_text = "\n".join(
        [
            f"• **{f.check_name}:** `[{f.result_code.value}]` ({'Passed ✅' if f.passed else 'Failed ❌'})\n  _{f.explanation}_"
            for f in report.findings
        ]
    )

    response_text = (
        f"🔬 *Diagnostic Battery Completed* {result_emoji}\n\n"
        f"• **Overall Result Code:** `{report.overall_code.value}`\n"
        f"• **Diagnostic Confidence:** `{int(report.confidence * 100)}%`\n"
        f"• **Primary Finding:** {report.summary}\n\n"
        f"📋 *Detailed Breakdown:*\n{findings_text}\n\n"
        f"💡 *Technical Recommendation:*\n"
        "To redeem a real Pixel Google AI Pro offer, open the **Google One App** on a **physical Google Pixel device** in an eligible country with a personal Google Account."
    )

    if screenshot:
        await context.bot.send_photo(
            chat_id=chat_id,
            photo=io.BytesIO(screenshot),
            caption=f"📸 Live Google One Landing Observation (`{web_status}`)",
        )

    await context.bot.send_message(chat_id=chat_id, text=response_text, parse_mode="Markdown")


async def history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display past diagnostic runs."""
    user = update.effective_user
    _log_audit_event(user.id, "CMD_HISTORY")

    with get_db() as db:
        db_user = get_or_create_user(db, user.id)
        sessions = (
            db.query(DiagnosticSession)
            .filter(DiagnosticSession.user_id == db_user.id)
            .order_by(DiagnosticSession.created_at.desc())
            .limit(5)
            .all()
        )

    if not sessions:
        await update.message.reply_text("ℹ️ You have no previous diagnostic runs on record. Use /diagnose to start one.")
        return

    lines = ["📊 *Your Recent Diagnostic History:*\n"]
    for s in sessions:
        date_str = s.created_at.strftime("%Y-%m-%d %H:%M UTC")
        lines.append(
            f"• `{date_str}`: `{s.overall_status}` (Confidence: {int(s.confidence * 100)}%)\n  _{s.summary_text}_"
        )

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show detailed documentation and troubleshooting codes."""
    user = update.effective_user
    _log_audit_event(user.id, "CMD_HELP")

    text = (
        "📖 *Pixel Promotion Platform Manual & Error Guide*\n\n"
        "🔍 *Diagnostic Result Codes:*\n"
        "• `OFFER_VISIBLE`: Offer card rendered and ready for subscription.\n"
        "• `OFFER_NOT_VISIBLE`: No promotional card returned for current session.\n"
        "• `DEVICE_NOT_VERIFIED`: Environment lacks hardware Play Integrity.\n"
        "• `REGION_NOT_SUPPORTED`: Country excluded from Pixel hardware store perks.\n"
        "• `ACCOUNT_NOT_ELIGIBLE`: Workspace, family group, or prior trial conflict.\n"
        "• `PAYMENT_REQUIREMENT_MISSING`: No payment method on Google Play Wallet.\n"
        "• `PROMOTION_EXPIRED`: Campaign redemption window closed.\n"
        "• `MANUAL_REVIEW_REQUIRED`: Google triggered an interactive security challenge.\n\n"
        "⚙️ *Available Commands:*\n"
        "/diagnose — Run the automated inspection suite\n"
        "/device — Check host execution layer vs hardware requirements\n"
        "/eligibility — Check supported country catalog\n"
        "/status — Inspect bot and server health\n"
        "/history — View your diagnostic history"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


# ── Callback Query Handlers ───────────────────────────────────────────────────

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle interactive inline buttons."""
    query = update.callback_query
    await query.answer()

    data = query.data
    user = query.from_user

    if data == "run_device_check":
        sim_profile = create_browser_simulation_profile()
        dev_class, evidence = device_diagnostic_service.inspect_environment(sim_profile.__dict__)
        await query.message.reply_text(
            f"📱 *Device Check Result:* `{dev_class.value}`\n\n"
            f"Host OS: {evidence.host_os} | Browser: {evidence.browser_name}\n"
            f"Notes: {'; '.join(evidence.diagnostic_notes)}",
            parse_mode="Markdown",
        )

    elif data == "run_region_menu":
        await query.message.reply_text(
            "🌍 Use `/eligibility` to select and test any country against Google Store terms.",
            parse_mode="Markdown",
        )

    elif data == "run_full_diagnose":
        await query.message.reply_text("🔬 Triggering diagnostic suite. Use /diagnose.")

    elif data == "show_history":
        await history(update, context)

    elif data.startswith("check_country_"):
        code = data.replace("check_country_", "")
        res = country_service.check_region_eligibility(code)
        emoji = "✅" if res["status"] == "ELIGIBLE" else "❌"
        await query.message.reply_text(
            f"{emoji} *Country Eligibility Report for {res.get('country_name', code)} ({code})*\n\n"
            f"• **Pixel Promotion Status:** `{res['status']}`\n"
            f"• **Google AI Pro Available:** `{res['google_ai_pro_available']}`\n"
            f"• **Evidence:** {res['evidence']}\n"
            f"• **Official Source:** {res.get('official_source', 'N/A')}",
            parse_mode="Markdown",
        )


# ── Application Main ──────────────────────────────────────────────────────────

def main() -> None:
    """Initialize DB and run bot."""
    init_db()

    token = config.TELEGRAM_BOT_TOKEN
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN is not configured.")
        return

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("device", device))
    app.add_handler(CommandHandler("eligibility", eligibility))
    app.add_handler(CommandHandler("diagnose", diagnose))
    app.add_handler(CommandHandler("history", history))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CallbackQueryHandler(handle_callback_query))

    logger.info("Pixel Promotion Diagnostic Bot is running.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
