"""
Unit tests for Telegram Command Handlers logic and formatting.
Covers requirement 19: Telegram handler behavior across claim workflow commands.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock
import pytest
from telegram import Update, User as TgUser, Chat, Message
from database import init_db
from main import (
    start,
    claim,
    promotions_cmd,
    account_cmd,
    cancel_cmd,
    help_cmd,
    handle_callback_query,
    handle_photo,
    handle_text,
)


@pytest.fixture(autouse=True)
def setup_db():
    init_db()


@pytest.mark.asyncio
async def test_start_command():
    uid = uuid.uuid4().int % 10000000
    update = MagicMock(spec=Update)
    update.effective_user = MagicMock(spec=TgUser, id=uid, first_name="Alex", username="alex")
    update.effective_chat = MagicMock(spec=Chat, id=uid)
    update.message = MagicMock(spec=Message)
    update.message.reply_text = AsyncMock()

    context = MagicMock()
    context.user_data = {}

    await start(update, context)
    update.message.reply_text.assert_called_once()
    call_args = update.message.reply_text.call_args[0][0]
    assert "Pixel Promotion Claim Assistant" in call_args
    assert "Alex" in call_args


@pytest.mark.asyncio
async def test_claim_command_menu():
    uid = uuid.uuid4().int % 10000000
    update = MagicMock(spec=Update)
    update.effective_user = MagicMock(spec=TgUser, id=uid, first_name="Sam", username="sam")
    update.effective_chat = MagicMock(spec=Chat, id=uid)
    update.message = MagicMock(spec=Message)
    update.message.reply_text = AsyncMock()

    context = MagicMock()
    context.user_data = {}

    await claim(update, context)
    update.message.reply_text.assert_called_once()
    call_args = update.message.reply_text.call_args[0][0]
    assert "Claim Assistant" in call_args
    assert "Step 1" in call_args


@pytest.mark.asyncio
async def test_claim_command_resumed_eligibility_passed():
    """Verify /claim resumes session in ELIGIBILITY_PASSED with redemption instructions button instead of crashing."""
    from session_manager import session_manager
    from models import ClaimState
    uid = uuid.uuid4().int % 10000000
    session = session_manager.create_claim_session(telegram_id=uid)
    session_manager.transition_state(session.id, ClaimState.PROMOTION_SELECTED, "STEP_1")
    session_manager.transition_state(session.id, ClaimState.DEVICE_SELECTED, "STEP_2")
    session_manager.transition_state(session.id, ClaimState.COUNTRY_SELECTED, "STEP_3")
    session_manager.transition_state(session.id, ClaimState.ELIGIBILITY_CHECKING, "STEP_4")
    session_manager.transition_state(session.id, ClaimState.ELIGIBILITY_PASSED, "STEP_4_RESULT")

    update = MagicMock(spec=Update)
    update.effective_user = MagicMock(spec=TgUser, id=uid, first_name="Sam", username="sam")
    update.effective_chat = MagicMock(spec=Chat, id=uid)
    update.message = MagicMock(spec=Message)
    update.message.reply_text = AsyncMock()

    context = MagicMock()
    context.user_data = {}

    await claim(update, context)
    update.message.reply_text.assert_called_once()
    call_args = update.message.reply_text.call_args[0][0]
    assert "ELIGIBILITY_PASSED" in call_args
    assert "Eligibility confirmed" in call_args


@pytest.mark.asyncio
async def test_promotions_command():
    uid = uuid.uuid4().int % 10000000
    update = MagicMock(spec=Update)
    update.effective_user = MagicMock(spec=TgUser, id=uid, first_name="Charlie", username="charlie")
    update.message = MagicMock(spec=Message)
    update.message.reply_text = AsyncMock()

    context = MagicMock()

    await promotions_cmd(update, context)
    update.message.reply_text.assert_called_once()
    call_args = update.message.reply_text.call_args[0][0]
    assert "Promotional Catalog" in call_args
    assert "Pixel 9 Pro" in call_args


@pytest.mark.asyncio
async def test_cancel_command():
    uid = uuid.uuid4().int % 10000000
    update = MagicMock(spec=Update)
    update.effective_user = MagicMock(spec=TgUser, id=uid, first_name="David", username="david")
    update.message = MagicMock(spec=Message)
    update.message.reply_text = AsyncMock()

    context = MagicMock()

    await cancel_cmd(update, context)
    update.message.reply_text.assert_called_once()
    call_args = update.message.reply_text.call_args[0][0]
    assert "No active claim session to cancel" in call_args


@pytest.mark.asyncio
async def test_help_command():
    uid = uuid.uuid4().int % 10000000
    update = MagicMock(spec=Update)
    update.effective_user = MagicMock(spec=TgUser, id=uid, first_name="Eve", username="eve")
    update.message = MagicMock(spec=Message)
    update.message.reply_text = AsyncMock()

    context = MagicMock()

    await help_cmd(update, context)
    update.message.reply_text.assert_called_once()
    call_args = update.message.reply_text.call_args[0][0]
    assert "User Manual" in call_args
    assert "/claim" in call_args


@pytest.mark.asyncio
async def test_callback_query_show_promotions_without_update_message():
    """Verify inline button show_promotions works when update.message is None."""
    from telegram import CallbackQuery
    uid = uuid.uuid4().int % 10000000
    update = MagicMock(spec=Update)
    update.effective_user = MagicMock(spec=TgUser, id=uid, first_name="Frank", username="frank")
    update.message = None  # Crucial: in callback queries, update.message is None!

    query = MagicMock(spec=CallbackQuery)
    query.data = "show_promotions"
    query.from_user = update.effective_user
    query.answer = AsyncMock()
    query.message = MagicMock(spec=Message)
    query.message.reply_text = AsyncMock()

    update.callback_query = query
    update.effective_message = query.message

    context = MagicMock()
    context.user_data = {}

    await handle_callback_query(update, context)
    query.answer.assert_called_once()
    query.message.reply_text.assert_called_once()
    call_args = query.message.reply_text.call_args[0][0]
    assert "Promotional Catalog" in call_args


@pytest.mark.asyncio
async def test_callback_query_run_device_check():
    """Verify inline button run_device_check works without update.message."""
    from telegram import CallbackQuery
    uid = uuid.uuid4().int % 10000000
    update = MagicMock(spec=Update)
    update.effective_user = MagicMock(spec=TgUser, id=uid, first_name="Grace", username="grace")
    update.message = None

    query = MagicMock(spec=CallbackQuery)
    query.data = "run_device_check"
    query.from_user = update.effective_user
    query.answer = AsyncMock()
    query.message = MagicMock(spec=Message)
    query.message.reply_text = AsyncMock()

    update.callback_query = query
    update.effective_message = query.message

    context = MagicMock()
    context.user_data = {}

    await handle_callback_query(update, context)
    query.answer.assert_called_once()
    query.message.reply_text.assert_called_once()
    call_args = query.message.reply_text.call_args[0][0]
    assert "Device Environment Report" in call_args


@pytest.mark.asyncio
async def test_handle_text_default_help():
    """Verify text messages receive help guidance."""
    uid = uuid.uuid4().int % 10000000
    update = MagicMock(spec=Update)
    update.effective_user = MagicMock(spec=TgUser, id=uid, first_name="Helen")
    update.message = MagicMock(spec=Message)
    update.message.text = "Hello bot"
    update.message.reply_text = AsyncMock()
    update.effective_message = update.message

    context = MagicMock()
    await handle_text(update, context)
    update.message.reply_text.assert_called_once()
    assert "/claim" in update.message.reply_text.call_args[0][0]


@pytest.mark.asyncio
async def test_handle_photo_with_active_session():
    """Verify photo upload classifies screenshot evidence correctly."""
    from session_manager import session_manager
    uid = uuid.uuid4().int % 10000000
    session = session_manager.create_claim_session(telegram_id=uid)

    update = MagicMock(spec=Update)
    update.effective_user = MagicMock(spec=TgUser, id=uid, first_name="Ian")
    photo_mock = MagicMock(file_id="photo_test_123")
    update.message = MagicMock(spec=Message, photo=[photo_mock])
    update.message.reply_text = AsyncMock()
    update.effective_message = update.message

    context = MagicMock()
    await handle_photo(update, context)
    update.message.reply_text.assert_called_once()
    reply_content = update.message.reply_text.call_args[0][0]
    assert "Screenshot Received" in reply_content
    assert "CLAIM_REPORTED_SUCCESS" in reply_content
