import asyncio
import logging
from dataclasses import dataclass

from asyncio import Queue
from telegram import Bot, InputMediaPhoto, ReplyKeyboardMarkup

from .analytics import log_send_failure


logger = logging.getLogger(__name__)


@dataclass
class OutgoingMessage:
    chat_id: int


@dataclass
class TextMessage(OutgoingMessage):
    text: str
    reply_markup: ReplyKeyboardMarkup | None = None


@dataclass
class LocationMessage(OutgoingMessage):
    latitude: float
    longitude: float


@dataclass
class MediaGroupMessage(OutgoingMessage):
    media: list[InputMediaPhoto]


async def message_sender(message_queue: Queue, bot: Bot):
    while True:
        msg = await message_queue.get()
        try:
            if isinstance(msg, TextMessage):
                await bot.send_message(chat_id=msg.chat_id, 
                                       text=msg.text, 
                                       reply_markup=msg.reply_markup)
            elif isinstance(msg, MediaGroupMessage):
                await bot.send_media_group(chat_id=msg.chat_id, 
                                           media=msg.media)
            elif isinstance(msg, LocationMessage):
                await bot.send_location(chat_id=msg.chat_id, 
                                        latitude=msg.latitude, 
                                        longitude=msg.longitude)
        except Exception as e:
            logger.error("Send failed: %s", e)
            await log_send_failure(type(msg).__name__, str(e))
        finally:
            await asyncio.sleep(1 / 30)  # avoid rate limit
