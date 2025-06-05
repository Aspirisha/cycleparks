import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from telegram import Update, Message, User, Chat
from cycleparks.handlers import start  # Import your handler directly


@pytest.mark.asyncio
async def test_start_handler():
    # Create a fake message and user
    queue = asyncio.Queue()
    user = User(id=123, first_name="Test", is_bot=False)
    chat = Chat(id=456, type="private")
    message = Message(message_id=1, date=None, chat=chat, text="/start", from_user=user)

    # Patch the reply method
    # message.reply_text = AsyncMock()

    # Build a fake update and context
    update = MagicMock(spec=Update)
    update.message = message

    context = MagicMock()
    context.bot = MagicMock()
    context.bot.send_message = AsyncMock()
    context.application.message_queue = queue  # assuming this is how it's used in your app


    # Call the handler
    await start(update, context)
    msg = await queue.get()
    assert msg.text.startswith("Hi")  # or any expected logic  