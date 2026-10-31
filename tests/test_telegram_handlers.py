"""
Unit tests for Telegram Command Handlers logic and formatting.
"""

from unittest.mock import AsyncMock, MagicMock
import pytest
from telegram import Update, User as TgUser, Chat, Message
from main import start, status, help_cmd, eligibility


@pytest.mark.asyncio
async def test_start_command():
    update = MagicMock(spec=Update)
    update.effective_user = MagicMock(spec=TgUser, id=1111, first_name="Alex", username="alex")
    update.effective_chat = MagicMock(spec=Chat, id=1111)
    update.message = MagicMock(spec=Message)
    update.message.reply_text = AsyncMock()

    context = MagicMock()

    await start(update, context)
    update.message.reply_text.assert_called_once()
    call_args = update.message.reply_text.call_args[0][0]
    assert "Pixel Promotion Diagnostic Platform" in call_args
    assert "Alex" in call_args


@pytest.mark.asyncio
async def test_help_command():
    update = MagicMock(spec=Update)
    update.effective_user = MagicMock(spec=TgUser, id=2222, first_name="Bob", username="bob")
    update.message = MagicMock(spec=Message)
    update.message.reply_text = AsyncMock()

    context = MagicMock()

    await help_cmd(update, context)
    update.message.reply_text.assert_called_once()
    call_args = update.message.reply_text.call_args[0][0]
    assert "OFFER_VISIBLE" in call_args
    assert "DEVICE_NOT_VERIFIED" in call_args
