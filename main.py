"""
Pixel Promotion Claim Assistant – Telegram Bot.

Production-ready guided assistant helping legitimate Google Pixel owners
discover, evaluate, access, redeem, and verify official Google AI Pro promotions.

Commands:
  /start        – Platform discovery & security notice
  /claim        – Start guided 7-step official redemption workflow
  /promotions   – Browse catalog of verified Google Pixel promotional offers
  /account      – View and update account profile & country
  /device       – Run hardware integrity and ADB diagnostic sweep
  /eligibility  – Interactive regional & country eligibility checker
  /diagnose     – Run multi-tier diagnostic battery with web observation
  /status       – System status & active claim session overview
  /history      – View your claim and diagnostic audit history
  /cancel       – Cancel current in-progress claim session
  /help         – Documentation, error code manual & troubleshooting

SECURITY POLICY:
Never prompts for, captures, or stores Google account passwords, 2FA codes,
TOTP secrets, or session cookies.
"""

import asyncio
import io
import logging
from datetime import datetime
from typing import Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import config
from audit_service import audit_service
from country_service import country_service
from database import get_db, get_or_create_user, init_db
from device_verification import DeviceTier, device_verification_service
from device_simulator import create_browser_simulation_profile
from google_automation import probe_google_one_endpoints
from models import ClaimSession, ClaimState, User
from promotion_catalog import promotion_service
from redemption_workflow import redemption_workflow
from session_manager import session_manager

logging.basicConfig(level=config.LOG_LEVEL, format=config.LOG_FORMAT)
logger = logging.getLogger(__name__)


# ── Robust Message Helpers ───────────────────────────────────────────────────

async def safe_reply(
    message,
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    parse_mode: Optional[str] = "Markdown",
    disable_web_page_preview: bool = True,
):
    """Safely reply to a message, falling back to plain text if Markdown entity parsing fails."""
    if not message:
        return None
    try:
        if parse_mode:
            return await message.reply_text(
                text,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
                disable_web_page_preview=disable_web_page_preview,
            )
        else:
            return await message.reply_text(
                text,
                reply_markup=reply_markup,
                disable_web_page_preview=disable_web_page_preview,
            )
    except Exception as exc:
        logger.warning("Markdown reply failed (%s), sending plain text fallback.", exc)
        return await message.reply_text(
            text,
            reply_markup=reply_markup,
            disable_web_page_preview=disable_web_page_preview,
        )


async def safe_edit(
    message,
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    parse_mode: Optional[str] = "Markdown",
):
    """Safely edit a message, falling back to plain text if Markdown parsing fails."""
    if not message:
        return None
    try:
        if parse_mode:
            return await message.edit_text(
                text,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
            )
        else:
            return await message.edit_text(
                text,
                reply_markup=reply_markup,
            )
    except Exception as exc:
        logger.warning("Markdown edit failed (%s), sending plain text fallback.", exc)
        return await message.edit_text(
            text,
            reply_markup=reply_markup,
        )


# ── Command Handlers ──────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send platform overview and main interactive menu."""
    user = update.effective_user
    audit_service.record_event(user.id, "CMD_START")

    with get_db() as db:
        get_or_create_user(db, user.id, username=user.username, first_name=user.first_name)

    keyboard = [
        [
            InlineKeyboardButton("🎁 Start Claim Workflow", callback_data="claim_start"),
            InlineKeyboardButton("📜 Browse Promotions", callback_data="show_promotions"),
        ],
        [
            InlineKeyboardButton("📱 Check Device", callback_data="run_device_check"),
            InlineKeyboardButton("🌍 Regional Eligibility", callback_data="run_region_menu"),
        ],
        [
            InlineKeyboardButton("🔬 Full Diagnosis", callback_data="run_full_diagnose"),
            InlineKeyboardButton("📊 My History", callback_data="show_history"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = (
        f"👋 *Welcome to the Pixel Promotion Claim Assistant*, {user.first_name}!\n\n"
        "This assistant helps legitimate **Google Pixel** owners discover, evaluate, and "
        "activate official **Google AI Pro / Gemini Advanced** promotional offers.\n\n"
        "🔒 *Security Directive:*\n"
        "• This platform **never requests or stores passwords, 2FA codes, or session tokens**.\n"
        "• All redemptions are performed directly by you on Google's official interfaces.\n\n"
        "📋 *Quick Commands:*\n"
        "• /claim — Start the 7-step guided claim workflow\n"
        "• /promotions — Browse officially documented Pixel promotions\n"
        "• /device — Inspect host execution layer & hardware proof\n"
        "• /eligibility — Test country and regional store eligibility\n"
        "• /diagnose — Run comprehensive diagnostic probe\n"
        "• /account — Configure account profile & billing country\n"
        "• /cancel — Cancel an in-progress claim workflow"
    )
    target_msg = update.message if update.message is not None else update.effective_message
    await safe_reply(target_msg, text, reply_markup=reply_markup)


async def claim(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Initiate or resume the 7-step claim workflow."""
    user = update.effective_user
    audit_service.record_event(user.id, "CMD_CLAIM")

    session, message = redemption_workflow.start_claim(user.id)
    context.user_data["active_session_id"] = session.id
    state_val = session.current_state

    # 1. State: IDLE -> Step 1: Select a promotion
    if state_val == ClaimState.IDLE.value:
        promos = promotion_service.list_all_promotions()
        buttons = []
        for p in promos:
            badge = "✅" if p.source_status == "VERIFIED_OFFICIAL" else "🔬"
            buttons.append([InlineKeyboardButton(f"{badge} {p.promotion_name}", callback_data=f"claim_promo_{p.promotion_id}")])
        buttons.append([InlineKeyboardButton("❌ Cancel Claim", callback_data="claim_cancel")])
        reply_markup = InlineKeyboardMarkup(buttons)
        prompt_text = "Please select the promotion you wish to claim:"

    # 2. State: PROMOTION_SELECTED -> Step 2: Select a device
    elif state_val == ClaimState.PROMOTION_SELECTED.value:
        buttons = [
            [InlineKeyboardButton("📱 Google Pixel 9 Pro", callback_data="claim_dev_Pixel 9 Pro")],
            [InlineKeyboardButton("📱 Google Pixel 9 Pro XL", callback_data="claim_dev_Pixel 9 Pro XL")],
            [InlineKeyboardButton("📱 Google Pixel 11 Pro", callback_data="claim_dev_Pixel 11 Pro")],
            [InlineKeyboardButton("💻 Browser Simulation (Test)", callback_data="claim_dev_Browser")],
            [InlineKeyboardButton("🔄 Start Over", callback_data="claim_restart"), InlineKeyboardButton("❌ Cancel Claim", callback_data="claim_cancel")],
        ]
        reply_markup = InlineKeyboardMarkup(buttons)
        prompt_text = "Please select or verify your Google Pixel device model:"

    # 3. State: DEVICE_SELECTED -> Step 3: Select country
    elif state_val == ClaimState.DEVICE_SELECTED.value:
        buttons = [
            [InlineKeyboardButton("🇺🇸 United States", callback_data="claim_ctry_US"), InlineKeyboardButton("🇬🇧 United Kingdom", callback_data="claim_ctry_GB")],
            [InlineKeyboardButton("🇩🇪 Germany", callback_data="claim_ctry_DE"), InlineKeyboardButton("🇯🇵 Japan", callback_data="claim_ctry_JP")],
            [InlineKeyboardButton("🇹🇭 Thailand", callback_data="claim_ctry_TH"), InlineKeyboardButton("🇻🇳 Vietnam", callback_data="claim_ctry_VN")],
            [InlineKeyboardButton("🇮🇳 India", callback_data="claim_ctry_IN")],
            [InlineKeyboardButton("🔄 Start Over", callback_data="claim_restart"), InlineKeyboardButton("❌ Cancel Claim", callback_data="claim_cancel")],
        ]
        reply_markup = InlineKeyboardMarkup(buttons)
        prompt_text = "Please confirm your Google Play Store country profile:"

    # 4. State: COUNTRY_SELECTED or ELIGIBILITY_CHECKING -> Step 4: Run evaluation
    elif state_val in (ClaimState.COUNTRY_SELECTED.value, ClaimState.ELIGIBILITY_CHECKING.value):
        buttons = [
            [InlineKeyboardButton("🔬 Run Eligibility Evaluation", callback_data=f"claim_eval_{session.id}")],
            [InlineKeyboardButton("🔄 Start Over", callback_data="claim_restart"), InlineKeyboardButton("❌ Cancel Claim", callback_data="claim_cancel")],
        ]
        reply_markup = InlineKeyboardMarkup(buttons)
        prompt_text = "Ready to evaluate promotion prerequisites against Google Store policies:"

    # 5. State: ELIGIBILITY_PASSED or ELIGIBILITY_UNKNOWN -> Step 5: Generate Guide
    elif state_val in (ClaimState.ELIGIBILITY_PASSED.value, ClaimState.ELIGIBILITY_UNKNOWN.value):
        buttons = [
            [InlineKeyboardButton("📖 Generate Redemption Instructions", callback_data=f"claim_guide_{session.id}")],
            [InlineKeyboardButton("🔄 Start Over", callback_data="claim_restart"), InlineKeyboardButton("❌ Cancel Claim", callback_data="claim_cancel")],
        ]
        reply_markup = InlineKeyboardMarkup(buttons)
        prompt_text = "Eligibility confirmed! Tap below to generate step-by-step redemption instructions:"

    # 6. State: REDEMPTION_READY, USER_ACTION_REQUIRED, CLAIM_IN_PROGRESS -> Step 6/7: Submit result
    elif state_val in (ClaimState.REDEMPTION_READY.value, ClaimState.USER_ACTION_REQUIRED.value, ClaimState.CLAIM_IN_PROGRESS.value):
        buttons = [
            [InlineKeyboardButton("🎉 I Successfully Claimed It", callback_data=f"claim_rep_success_{session.id}")],
            [InlineKeyboardButton("💳 Payment Method Required", callback_data=f"claim_rep_payment_{session.id}")],
            [InlineKeyboardButton("❌ Claim Failed / Ineligible", callback_data=f"claim_rep_failed_{session.id}")],
            [InlineKeyboardButton("🔄 Start Over", callback_data="claim_restart"), InlineKeyboardButton("❌ Cancel Claim", callback_data="claim_cancel")],
        ]
        reply_markup = InlineKeyboardMarkup(buttons)
        prompt_text = "Awaiting your outcome report on Google One redemption:"

    # Fallback for BLOCKED or other
    else:
        buttons = [
            [InlineKeyboardButton("🔄 Start Over", callback_data="claim_restart"), InlineKeyboardButton("❌ Cancel Claim", callback_data="claim_cancel")],
        ]
        reply_markup = InlineKeyboardMarkup(buttons)
        prompt_text = "Previous evaluation blocked. You can restart with another configuration:"

    text = (
        f"🚀 *Pixel Promotion Claim Assistant*\n"
        f"Session: `{session.session_uuid[:8]}…` | State: `{session.current_state}`\n\n"
        f"{message}\n\n"
        f"{prompt_text}"
    )
    target_msg = update.message if update.message is not None else update.effective_message
    await safe_reply(target_msg, text, reply_markup=reply_markup)


async def promotions_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List catalog of verified promotions."""
    user = update.effective_user
    audit_service.record_event(user.id, "CMD_PROMOTIONS")

    promos = promotion_service.list_all_promotions()
    lines = ["📜 *Official Google Pixel Promotional Catalog:*\n"]

    for p in promos:
        status_tag = "Official Retail" if p.source_status == "VERIFIED_OFFICIAL" else "Research Target (Unreleased)"
        lines.append(
            f"🎁 **{p.promotion_name}**\n"
            f"• **Duration:** {p.duration_months} Months ({p.subscription_plan})\n"
            f"• **Supported Models:** {', '.join(p.supported_device_models)}\n"
            f"• **Supported Regions:** {', '.join(p.supported_countries[:6])}…\n"
            f"• **Status:** `{status_tag}`\n"
            f"• **Official Terms:** [Google Terms URL]({p.official_terms_url})\n"
        )

    lines.append("Use /claim to start a redemption workflow for any eligible promotion.")
    target_msg = update.message if update.message is not None else update.effective_message
    await safe_reply(target_msg, "\n".join(lines), disable_web_page_preview=True)


async def account_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """View and configure account profile."""
    user = update.effective_user
    audit_service.record_event(user.id, "CMD_ACCOUNT")

    with get_db() as db:
        db_user = get_or_create_user(db, user.id, username=user.username, first_name=user.first_name)
        country = db_user.selected_country_code or "US"
        acct_type = db_user.account_type or "PERSONAL"

    keyboard = [
        [
            InlineKeyboardButton("🇺🇸 United States", callback_data="set_country_US"),
            InlineKeyboardButton("🇬🇧 United Kingdom", callback_data="set_country_GB"),
        ],
        [
            InlineKeyboardButton("🇩🇪 Germany", callback_data="set_country_DE"),
            InlineKeyboardButton("🇯🇵 Japan", callback_data="set_country_JP"),
        ],
        [
            InlineKeyboardButton("🇹🇭 Thailand", callback_data="set_country_TH"),
            InlineKeyboardButton("🇻🇳 Vietnam", callback_data="set_country_VN"),
        ],
        [
            InlineKeyboardButton("🇮🇳 India", callback_data="set_country_IN"),
            InlineKeyboardButton("🗑️ Delete My Data (GDPR)", callback_data="gdpr_delete_data"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = (
        "👤 *Your Account Profile*\n\n"
        f"• **Telegram ID:** `{user.id}`\n"
        f"• **Account Type:** `{acct_type}` (Personal @gmail.com required)\n"
        f"• **Configured Google Play Country:** `{country}`\n\n"
        "Select your Google Play Store billing country below to update:"
    )
    target_msg = update.message if update.message is not None else update.effective_message
    await safe_reply(target_msg, text, reply_markup=reply_markup)


async def device_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Run device diagnostic sweep."""
    user = update.effective_user
    audit_service.record_event(user.id, "CMD_DEVICE")

    report = device_verification_service.inspect_environment()
    emoji = "✅" if report.device_tier == DeviceTier.VERIFIED_PIXEL else "⚠️"

    text = (
        f"📱 *Device Environment Report* {emoji}\n\n"
        f"• **Detected Layer:** `{report.device_tier.value}`\n"
        f"• **Reported Model:** `{report.reported_model}`\n"
        f"• **Manufacturer:** `{report.reported_manufacturer}`\n"
        f"• **ADB Connected:** `{'Yes' if report.adb_connected else 'No'}`\n"
        f"• **Hardware Attestation:** `{'Verified' if report.is_hardware_verified else 'Unverified / Software'}`\n\n"
        "🔬 *Analysis:*\n"
        + "\n".join([f"• {n}" for n in report.verification_notes])
    )
    target_msg = update.message if update.message is not None else update.effective_message
    await safe_reply(target_msg, text)


async def eligibility_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Present regional eligibility selector."""
    user = update.effective_user
    audit_service.record_event(user.id, "CMD_ELIGIBILITY")

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
            InlineKeyboardButton("🇹🇭 Thailand", callback_data="check_country_TH"),
            InlineKeyboardButton("🇻🇳 Vietnam", callback_data="check_country_VN"),
        ],
        [
            InlineKeyboardButton("🇮🇳 India", callback_data="check_country_IN"),
            InlineKeyboardButton("🇨🇦 Canada", callback_data="check_country_CA"),
        ],
        [
            InlineKeyboardButton("🇦🇺 Australia", callback_data="check_country_AU"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    target_msg = update.message if update.message is not None else update.effective_message
    await safe_reply(
        target_msg,
        "🌍 *Regional Eligibility Checker*\n\nSelect a country to test eligibility against official Google Store terms:",
        reply_markup=reply_markup,
    )


async def diagnose_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Run full diagnostic battery (Device + Region + Web Prober)."""
    user = update.effective_user
    chat_id = update.effective_chat.id if update.effective_chat else user.id
    audit_service.record_event(user.id, "CMD_DIAGNOSE")

    target_msg = update.message if update.message is not None else update.effective_message
    status_msg = await safe_reply(target_msg, "🚀 *Running multi-tier diagnostic probe…*")

    sim_profile = create_browser_simulation_profile()
    dev_report = device_verification_service.inspect_environment(is_emulation_probe=True)

    loop = asyncio.get_event_loop()
    try:
        web_status, web_details, screenshot = await loop.run_in_executor(
            None,
            lambda: probe_google_one_endpoints(sim_profile, config.GOOGLE_ONE_BENEFITS_URL),
        )
    except Exception as e:
        logger.error("Web probe failed: %s", e)
        web_status, web_details, screenshot = "UNKNOWN", {"error": str(e)}, None

    promos = promotion_service.list_all_promotions()
    target_promo = promos[0] if promos else None

    from eligibility_engine import eligibility_engine
    eval_report = eligibility_engine.evaluate(
        promotion=target_promo,
        device_report=dev_report,
        country_code="US",
        web_observed_status=web_status,
    )

    breakdown = "\n".join(
        [f"• **{c.category}:** `[{c.code.value}]` ({'Passed ✅' if c.passed else 'Failed ❌'})\n  _{c.summary}_" for c in eval_report.assessments]
    )

    resp = (
        f"🔬 *Diagnostic Battery Completed*\n\n"
        f"• **Result Code:** `[{eval_report.primary_code.value}]`\n"
        f"• **Primary Finding:** {eval_report.overall_summary}\n\n"
        f"📋 *Detailed Breakdown:*\n{breakdown}\n\n"
        "💡 *Recommendation:*\nHardware promotions require the Google One app on a physical Pixel phone."
    )

    if screenshot:
        try:
            await context.bot.send_photo(chat_id=chat_id, photo=io.BytesIO(screenshot), caption=f"📸 Observation: `{web_status}`")
        except Exception as e:
            logger.warning("Could not send screenshot photo: %s", e)

    await safe_edit(status_msg, resp)


async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show system and active session status."""
    user = update.effective_user
    audit_service.record_event(user.id, "CMD_STATUS")

    active_session = session_manager.get_active_session(user.id)
    session_text = (
        f"Active Claim Session: `{active_session.session_uuid[:8]}…` (State: `{active_session.current_state}`)"
        if active_session else "No active claim session. Use /claim to start."
    )

    text = (
        "📊 *System & Session Status*\n\n"
        f"• {session_text}\n"
        f"• Database Engine: `Operational`\n"
        f"• Promotion Catalog: `{len(promotion_service.list_all_promotions())} promotions loaded`\n"
        f"• Country Rules: `{len(country_service._countries)} countries cataloged`\n\n"
        "Use /help for command documentation."
    )
    target_msg = update.message if update.message is not None else update.effective_message
    await safe_reply(target_msg, text)


async def history_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show past claim and diagnostic history."""
    user = update.effective_user
    audit_service.record_event(user.id, "CMD_HISTORY")

    with get_db() as db:
        db_user = get_or_create_user(db, user.id)
        sessions = (
            db.query(ClaimSession)
            .filter(ClaimSession.user_id == db_user.id)
            .order_by(ClaimSession.created_at.desc())
            .limit(5)
            .all()
        )

    target_msg = update.message if update.message is not None else update.effective_message
    if not sessions:
        await safe_reply(target_msg, "ℹ️ No previous claim sessions on record. Use /claim to start one.")
        return

    lines = ["📊 *Your Recent Claim Sessions:*\n"]
    for s in sessions:
        date_str = s.created_at.strftime("%Y-%m-%d %H:%M UTC")
        p_name = s.promotion.promotion_name if s.promotion else "Unspecified Promotion"
        lines.append(f"• `{date_str}`: `{s.current_state}`\n  _{p_name}_")

    await safe_reply(target_msg, "\n".join(lines))


async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Cancel any active claim session."""
    user = update.effective_user
    audit_service.record_event(user.id, "CMD_CANCEL")

    target_msg = update.message if update.message is not None else update.effective_message
    active = session_manager.get_active_session(user.id)
    if not active:
        await safe_reply(target_msg, "ℹ️ No active claim session to cancel.")
        return

    session_manager.cancel_session(active.id, "User sent /cancel")
    await safe_reply(target_msg, f"❌ Claim session `{active.session_uuid[:8]}…` has been cancelled.")


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show detailed command guide and troubleshooting."""
    user = update.effective_user
    audit_service.record_event(user.id, "CMD_HELP")

    text = (
        "📖 *Pixel Promotion Claim Assistant – User Manual*\n\n"
        "⚙️ *Available Commands:*\n"
        "• `/claim` — Guided 7-step claim workflow\n"
        "• `/promotions` — View all cataloged Pixel promotions\n"
        "• `/device` — Check execution layer and hardware attestation\n"
        "• `/eligibility` — Check country availability\n"
        "• `/diagnose` — Run complete multi-tier diagnostic probe\n"
        "• `/account` — Configure your Google Play country profile\n"
        "• `/cancel` — Cancel an in-progress claim workflow\n"
        "• `/status` — View current platform status\n"
        "• `/history` — View past claim attempts\n\n"
        "🔍 *Verification Guarantee:*\n"
        "Promotions are validated against official Google Store and Google One terms. "
        "The bot assists you through the official process without accessing your Google account."
    )
    target_msg = update.message if update.message is not None else update.effective_message
    await safe_reply(target_msg, text)


# ── Callback Query Handlers ───────────────────────────────────────────────────

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle interactive inline buttons."""
    query = update.callback_query
    await query.answer()

    data = query.data
    user = query.from_user

    if data == "claim_start":
        active = session_manager.get_active_session(user.id)
        session = active or session_manager.create_claim_session(user.id)
        context.user_data["active_session_id"] = session.id

        promos = promotion_service.list_all_promotions()
        buttons = [[InlineKeyboardButton(p.promotion_name, callback_data=f"claim_promo_{p.promotion_id}")] for p in promos]
        buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="claim_cancel")])
        await safe_reply(query.message, "Step 1: Select a promotion to claim:", reply_markup=InlineKeyboardMarkup(buttons))

    elif data == "claim_restart":
        active = session_manager.get_active_session(user.id)
        if active:
            session_manager.cancel_session(active.id, "User requested restart")
        new_session = session_manager.create_claim_session(user.id)
        context.user_data["active_session_id"] = new_session.id

        promos = promotion_service.list_all_promotions()
        buttons = [[InlineKeyboardButton(p.promotion_name, callback_data=f"claim_promo_{p.promotion_id}")] for p in promos]
        buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="claim_cancel")])
        await safe_reply(query.message, "🔄 Previous session reset. Step 1: Select a promotion to claim:", reply_markup=InlineKeyboardMarkup(buttons))

    elif data.startswith("claim_promo_"):
        promo_id = data.replace("claim_promo_", "")
        s_id = context.user_data.get("active_session_id")
        if not s_id:
            s = session_manager.get_active_session(user.id)
            s_id = s.id if s else None

        if not s_id:
            s = session_manager.create_claim_session(user.id)
            s_id = s.id

        res = redemption_workflow.select_promotion(s_id, promo_id)
        if res.data and "session_id" in res.data:
            s_id = res.data["session_id"]
            context.user_data["active_session_id"] = s_id

        buttons = [
            [InlineKeyboardButton("📱 Google Pixel 9 Pro", callback_data="claim_dev_Pixel 9 Pro")],
            [InlineKeyboardButton("📱 Google Pixel 9 Pro XL", callback_data="claim_dev_Pixel 9 Pro XL")],
            [InlineKeyboardButton("📱 Google Pixel 11 Pro", callback_data="claim_dev_Pixel 11 Pro")],
            [InlineKeyboardButton("💻 Browser Simulation (Test)", callback_data="claim_dev_Browser")],
            [InlineKeyboardButton("🔄 Start Over", callback_data="claim_restart"), InlineKeyboardButton("❌ Cancel", callback_data="claim_cancel")],
        ]
        await safe_reply(query.message, res.message, reply_markup=InlineKeyboardMarkup(buttons))

    elif data.startswith("claim_dev_"):
        model = data.replace("claim_dev_", "")
        s_id = context.user_data.get("active_session_id")
        if not s_id:
            await safe_reply(query.message, "Session expired. Please type /claim.")
            return

        res = redemption_workflow.select_device(s_id, manual_model=model)
        buttons = [
            [InlineKeyboardButton("🇺🇸 United States", callback_data="claim_ctry_US"), InlineKeyboardButton("🇬🇧 United Kingdom", callback_data="claim_ctry_GB")],
            [InlineKeyboardButton("🇩🇪 Germany", callback_data="claim_ctry_DE"), InlineKeyboardButton("🇯🇵 Japan", callback_data="claim_ctry_JP")],
            [InlineKeyboardButton("🇹🇭 Thailand", callback_data="claim_ctry_TH"), InlineKeyboardButton("🇻🇳 Vietnam", callback_data="claim_ctry_VN")],
            [InlineKeyboardButton("🇮🇳 India", callback_data="claim_ctry_IN")],
            [InlineKeyboardButton("🔄 Start Over", callback_data="claim_restart"), InlineKeyboardButton("❌ Cancel", callback_data="claim_cancel")],
        ]
        await safe_reply(query.message, res.message, reply_markup=InlineKeyboardMarkup(buttons))

    elif data.startswith("claim_ctry_"):
        c_code = data.replace("claim_ctry_", "")
        s_id = context.user_data.get("active_session_id")
        if not s_id:
            await safe_reply(query.message, "Session expired. Please type /claim.")
            return

        res = redemption_workflow.select_country(s_id, c_code)
        buttons = [
            [InlineKeyboardButton("🔬 Run Eligibility Evaluation", callback_data=f"claim_eval_{s_id}")],
            [InlineKeyboardButton("🔄 Start Over", callback_data="claim_restart"), InlineKeyboardButton("❌ Cancel", callback_data="claim_cancel")],
        ]
        await safe_reply(query.message, res.message, reply_markup=InlineKeyboardMarkup(buttons))

    elif data.startswith("claim_eval_"):
        s_id = int(data.replace("claim_eval_", ""))
        res = redemption_workflow.run_eligibility_evaluation(s_id)
        if res.can_proceed:
            buttons = [
                [InlineKeyboardButton("📖 Generate Redemption Instructions", callback_data=f"claim_guide_{s_id}")],
                [InlineKeyboardButton("🔄 Start Over", callback_data="claim_restart"), InlineKeyboardButton("❌ Cancel", callback_data="claim_cancel")],
            ]
            await safe_reply(query.message, res.message, reply_markup=InlineKeyboardMarkup(buttons))
        else:
            buttons = [
                [InlineKeyboardButton("🔄 Start Over", callback_data="claim_restart"), InlineKeyboardButton("❌ Cancel", callback_data="claim_cancel")],
            ]
            await safe_reply(query.message, res.message, reply_markup=InlineKeyboardMarkup(buttons))

    elif data.startswith("claim_guide_"):
        s_id = int(data.replace("claim_guide_", ""))
        res = redemption_workflow.generate_redemption_guide(s_id)
        buttons = [
            [InlineKeyboardButton("🎉 I Successfully Claimed It", callback_data=f"claim_rep_success_{s_id}")],
            [InlineKeyboardButton("💳 Payment Method Required", callback_data=f"claim_rep_payment_{s_id}")],
            [InlineKeyboardButton("❌ Claim Failed / Ineligible", callback_data=f"claim_rep_failed_{s_id}")],
            [InlineKeyboardButton("🔄 Start Over", callback_data="claim_restart"), InlineKeyboardButton("❌ Cancel", callback_data="claim_cancel")],
        ]
        await safe_reply(query.message, res.message, reply_markup=InlineKeyboardMarkup(buttons))

    elif data.startswith("claim_rep_"):
        parts = data.split("_")
        outcome = parts[2]
        s_id = int(parts[3])

        report_map = {
            "success": "I successfully activated the offer in Google One.",
            "payment": "Google asks to add a payment method.",
            "failed": "Claim failed with error message.",
        }
        user_msg = report_map.get(outcome, "Status reported")
        res = redemption_workflow.submit_redemption_result(s_id, user_msg)
        await safe_reply(query.message, res.message)

    elif data == "claim_cancel":
        active = session_manager.get_active_session(user.id)
        if active:
            session_manager.cancel_session(active.id, "Cancelled by user")
        await safe_reply(query.message, "❌ Claim workflow cancelled.")

    elif data == "show_promotions":
        await promotions_cmd(update, context)

    elif data == "run_device_check":
        await device_cmd(update, context)

    elif data == "run_region_menu":
        await eligibility_cmd(update, context)

    elif data == "run_full_diagnose":
        await diagnose_cmd(update, context)

    elif data == "show_history":
        await history_cmd(update, context)

    elif data.startswith("set_country_"):
        c_code = data.replace("set_country_", "")
        with get_db() as db:
            db_user = get_or_create_user(db, user.id)
            db_user.selected_country_code = c_code
        await safe_reply(query.message, f"✅ Your default Google Play Store country updated to: `{c_code}`")

    elif data == "gdpr_delete_data":
        success = audit_service.delete_all_user_records(user.id)
        if success:
            await safe_reply(query.message, "🗑️ All your user data, claim sessions, and audit history have been completely erased.")
        else:
            await safe_reply(query.message, "ℹ️ No records found to delete.")

    elif data.startswith("check_country_"):
        code = data.replace("check_country_", "")
        res = country_service.check_region_eligibility(code)
        emoji = "✅" if res["status"] == "ELIGIBLE" else "❌"
        await safe_reply(
            query.message,
            f"{emoji} *Country Eligibility Report for {res.get('country_name', code)} ({code})*\n\n"
            f"• **Pixel Promotion Support:** `{res['status']}`\n"
            f"• **Google AI Pro Available:** `{res['google_ai_pro_available']}`\n"
            f"• **Evidence:** {res['evidence']}\n"
            f"• **Official Source:** {res.get('official_source', 'N/A')}",
        )


# ── Photo & Text Handlers ────────────────────────────────────────────────────

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle screenshot uploads during claim verification."""
    user = update.effective_user
    audit_service.record_event(user.id, "UPLOAD_PHOTO")
    active_session = session_manager.get_active_session(user.id)

    target_msg = update.message if update.message is not None else update.effective_message
    if not active_session:
        await safe_reply(
            target_msg,
            "📸 Screenshot received, but you do not have an active claim session.\n"
            "Use /claim to begin a guided claim workflow.",
        )
        return

    photo = update.message.photo[-1]
    file_id = photo.file_id

    from redemption_verification import redemption_verification_service
    assessment = redemption_verification_service.classify_redemption_evidence(
        session_id=active_session.id,
        evidence_type="SCREENSHOT",
        payload=f"telegram_file_id:{file_id}",
    )

    text = (
        "📸 *Screenshot Received & Classified*\n\n"
        f"• **Session:** `{active_session.session_uuid[:8]}…`\n"
        f"• **Evidence Status:** `[{assessment.status.value}]`\n"
        f"• **Confidence:** `{int(assessment.confidence * 100)}%`\n"
        f"• **Analysis:** {assessment.notes}\n\n"
        f"📌 *Next Step:* {assessment.next_recommended_step}"
    )
    await safe_reply(target_msg, text)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle plain text feedback from user during claim workflow."""
    user = update.effective_user
    msg_text = update.message.text.strip() if update.message and update.message.text else ""
    active_session = session_manager.get_active_session(user.id)

    target_msg = update.message if update.message is not None else update.effective_message

    if active_session and active_session.current_state in (
        ClaimState.USER_ACTION_REQUIRED.value,
        ClaimState.CLAIM_IN_PROGRESS.value,
    ):
        res = redemption_workflow.submit_redemption_result(active_session.id, msg_text)
        await safe_reply(target_msg, res.message)
        return

    await safe_reply(
        target_msg,
        "👋 Need assistance? Use these quick commands:\n"
        "• `/claim` — Start or resume your Pixel offer claim\n"
        "• `/promotions` — View available Pixel promotions\n"
        "• `/device` — Check your device compatibility\n"
        "• `/help` — View the complete command manual",
    )


# ── Global Error Handler ─────────────────────────────────────────────────────

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and inform the user safely."""
    logger.error("Exception while handling update: %s", context.error, exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        try:
            await safe_reply(
                update.effective_message,
                "⚠️ An unexpected state error occurred. "
                "You can use /claim to resume or /cancel to start a fresh claim workflow.",
            )
        except Exception:
            pass


# ── Application Main ──────────────────────────────────────────────────────────

def main() -> None:
    """Initialize database and start Telegram bot polling."""
    init_db()

    token = config.TELEGRAM_BOT_TOKEN
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN is not configured.")
        return

    app = Application.builder().token(token).build()

    # Register error handler
    app.add_error_handler(error_handler)

    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("claim", claim))
    app.add_handler(CommandHandler("promotions", promotions_cmd))
    app.add_handler(CommandHandler("account", account_cmd))
    app.add_handler(CommandHandler("device", device_cmd))
    app.add_handler(CommandHandler("eligibility", eligibility_cmd))
    app.add_handler(CommandHandler("diagnose", diagnose_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("history", history_cmd))
    app.add_handler(CommandHandler("cancel", cancel_cmd))
    app.add_handler(CommandHandler("help", help_cmd))

    # Inline callbacks
    app.add_handler(CallbackQueryHandler(handle_callback_query))

    # Media and Text
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("Pixel Promotion Claim Assistant is running.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
