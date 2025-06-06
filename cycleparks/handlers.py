import json
import logging
import traceback
from asyncio import Queue
from datetime import datetime
from dataclasses import dataclass
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, InputMediaPhoto
from telegram.ext import ContextTypes

from cycleparks.analytics import log_command
from cycleparks.locations_info import LocationsInfo
from cycleparks.message_queue import TextMessage, LocationMessage, MediaGroupMessage


logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    context.application
    button = KeyboardButton(text="Share Location 📍", request_location=True)
    keyboard = ReplyKeyboardMarkup(
        [[button]], resize_keyboard=True, one_time_keyboard=True)
    context.application.message_queue.put_nowait(
        TextMessage(chat_id=update.effective_chat.id,
                    text=f"Hi {user.name}! I can help you find the nearest cycle parks. "
                         f"Please share your location to get started.",
                    reply_markup=keyboard))


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "🤖 *Available Commands:*\n"
        "/start - Start the bot\n"
        "/limit <number> - Set number of returned closest parking locations\n"
        "/help - Show this help message\n"
    )
    context.application.message_queue.put_nowait(
        TextMessage(chat_id=update.effective_chat.id,
                    text=help_text))


async def limit_locations(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args  # This gives you the list of arguments after the command
    current_limit = context.user_data.get(
        "locations_limit", LocationsInfo.DEFAULT_LOCATIONS_LIMIT)
    if not args:
        context.application.message_queue.put_nowait(
            TextMessage(chat_id=update.effective_chat.id,
                        text=f"Send me preferred number of closest locations to show, e.g. /limit 3. Current limit is {current_limit}."))
        return
    try:
        locations_limit = int(args[0])
        if locations_limit > LocationsInfo.MAX_LOCATIONS_LIMIT:
            context.user_data["locations_limit"] = LocationsInfo.MAX_LOCATIONS_LIMIT
            context.application.message_queue.put_nowait(
                TextMessage(chat_id=update.effective_chat.id,
                            text=f"❌ Location limit is set to {LocationsInfo.MAX_LOCATIONS_LIMIT} - this is maximum!"))
        elif locations_limit < 1:
            context.user_data["locations_limit"] = 1
            context.application.message_queue.put_nowait(
                TextMessage(chat_id=update.effective_chat.id,
                            text=f"✅ Location limit is set to 1 - this is minimum!"))
        else:
            context.user_data["locations_limit"] = locations_limit
            context.application.message_queue.put_nowait(
                TextMessage(chat_id=update.effective_chat.id,
                            text=f"✅ You set locations limit to {locations_limit}"))
    except ValueError:
        context.application.message_queue.put_nowait(
            TextMessage(chat_id=update.effective_chat.id,
                        text=f"❌ That doesn't look like a valid number. Locations limit is {current_limit}."))

def ordinal(n):
    if str(n)[-1] == '1':
        return str(n) + 'st'
    elif str(n)[-1] == '2':
        return str(n) + 'nd'
    elif str(n)[-1] == '3':
        return str(n) + 'rd'
    else:
        return str(n) + 'th'


async def show_nearest_cycleparks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.application.create_task(
        log_command(
            update.effective_user.id,
            "show_nearest_cycleparks"))
    user_location = update.message.location
    if not user_location:
        logger.info('Received no user location: %s', user_location)
        return
    logger.info('Received user location %s', user_location)
    lat = user_location.latitude
    lon = user_location.longitude

    locations_limit = context.user_data.get(
        "locations_limit", LocationsInfo.DEFAULT_LOCATIONS_LIMIT)
    nearest_parkings, distances = LocationsInfo.get_nearest_cycleparks(
        lat, lon, k=locations_limit)

    logger.info(
        'Retrieved %d nearest cycle parks within distances %r',
        len(nearest_parkings),
        distances)

    if distances[0] > 1000:
        context.application.message_queue.put_nowait(
            TextMessage(
                chat_id=update.effective_chat.id,
                text=f"❗️ No cycle parks found within 1 km of your location."
                     f" For now, only London cycle parks are supported. "
            )
        )
        return
    for i, (distance, parking_info) in enumerate(
            zip(distances, nearest_parkings)):
        context.application.message_queue.put_nowait(
            TextMessage(
                chat_id=update.effective_chat.id,
                text=f"{ordinal(i+1)} nearest cycle parking is within {distance:.0f} meters:\n"))
        coords = parking_info["geometry"]["coordinates"]
        context.application.message_queue.put_nowait(
            LocationMessage(
                chat_id=update.effective_chat.id,
                latitude=coords[1],
                longitude=coords[0]
            )
        )
        props = parking_info['properties']
        media = [InputMediaPhoto(media=url)
                 for url in [props.get('PHOTO1_URL'), props.get('PHOTO2_URL')]
                 if url is not None]
        if media:
            context.application.message_queue.put_nowait(
                MediaGroupMessage(
                    chat_id=update.effective_chat.id,
                    media=media
                )
            )


@dataclass
class ErrorInfo:
    timestamp: datetime
    exception_type: str
    error_message: str
    update_str: str


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a telegram message to notify the developer."""
    # Log the error before we do anything else, so we can see it even if something breaks.
    logger.error("Exception while handling an update:", exc_info=context.error)

    # Build the message with some markup and additional information about what happened.
    # You might need to add some logic to deal with messages longer than the 4096 character limit.
    update_str = json.dumps(update.to_dict()) if isinstance(update, Update) else str(update)

    context.application.error_queue.put_nowait(
        ErrorInfo(
            timestamp=datetime.now(),
            exception_type=type(context.error).__name__,
            error_message=str(context.error),
            update_str=update_str,
        )
    )
  