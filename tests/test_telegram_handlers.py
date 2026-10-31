"""
Unit tests for Telegram Command Handlers logic and formatting.
Covers requirement 19: Telegram handler behavior across claim workflow commands.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock
import pytest
from telegram import Update, User as TgUser, Chat, Message
from database import init_db
from main import start, claim, promotions_cmd, account_cmd, cancel_cmd, help_cmd


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
