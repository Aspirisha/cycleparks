import json
import logging
import traceback
import uuid
from asyncio import Queue
from datetime import datetime
from dataclasses import dataclass
from telegram import (
    Update,
    KeyboardButton,
    ReplyKeyboardMarkup,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
)
from telegram.ext import ContextTypes

from cycleparks.analytics import log_command
from cycleparks.locations_info import LocationsInfo
from cycleparks.message_queue import TextMessage, LocationMessage, MediaGroupMessage
from cycleparks.db import get_session
from cycleparks.models import CycleParkSubmission, CyclePark
from sqlalchemy import select


logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    context.application
    button = KeyboardButton(text="Share Location 📍", request_location=True)
    keyboard = ReplyKeyboardMarkup(
        [[button]], resize_keyboard=True, one_time_keyboard=True
    )
    context.application.message_queue.put_nowait(
        TextMessage(
            chat_id=update.effective_chat.id,
            text=f"Hi {user.name}! I can help you find the nearest cycle parks. "
            f"Please share your location to get started.",
            reply_markup=keyboard,
        )
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "🤖 *Available Commands:*\n"
        "/start - Start the bot\n"
        "/limit <number> - Set number of returned closest parking locations\n"
        "/add - Add a new cycle park for review\n"
        "/help - Show this help message\n"
    )
    context.application.message_queue.put_nowait(
        TextMessage(chat_id=update.effective_chat.id, text=help_text)
    )


async def limit_locations(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args  # This gives you the list of arguments after the command
    current_limit = context.user_data.get(
        "locations_limit", LocationsInfo.DEFAULT_LOCATIONS_LIMIT
    )
    if not args:
        context.application.message_queue.put_nowait(
            TextMessage(
                chat_id=update.effective_chat.id,
                text=f"Send me preferred number of closest locations to show, e.g. /limit 3. Current limit is {current_limit}.",
            )
        )
        return
    try:
        locations_limit = int(args[0])
        if locations_limit > LocationsInfo.MAX_LOCATIONS_LIMIT:
            context.user_data["locations_limit"] = LocationsInfo.MAX_LOCATIONS_LIMIT
            context.application.message_queue.put_nowait(
                TextMessage(
                    chat_id=update.effective_chat.id,
                    text=f"❌ Location limit is set to {LocationsInfo.MAX_LOCATIONS_LIMIT} - this is maximum!",
                )
            )
        elif locations_limit < 1:
            context.user_data["locations_limit"] = 1
            context.application.message_queue.put_nowait(
                TextMessage(
                    chat_id=update.effective_chat.id,
                    text=f"✅ Location limit is set to 1 - this is minimum!",
                )
            )
        else:
            context.user_data["locations_limit"] = locations_limit
            context.application.message_queue.put_nowait(
                TextMessage(
                    chat_id=update.effective_chat.id,
                    text=f"✅ You set locations limit to {locations_limit}",
                )
            )
    except ValueError:
        context.application.message_queue.put_nowait(
            TextMessage(
                chat_id=update.effective_chat.id,
                text=f"❌ That doesn't look like a valid number. Locations limit is {current_limit}.",
            )
        )


def ordinal(n):
    if str(n)[-1] == "1":
        return str(n) + "st"
    elif str(n)[-1] == "2":
        return str(n) + "nd"
    elif str(n)[-1] == "3":
        return str(n) + "rd"
    else:
        return str(n) + "th"


async def show_nearest_cycleparks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.application.create_task(
        log_command(update.effective_user.id, "show_nearest_cycleparks")
    )
    user_location = update.message.location
    if not user_location:
        logger.info("Received no user location: %s", user_location)
        return
    logger.info("Received user location %s", user_location)
    lat = user_location.latitude
    lon = user_location.longitude

    locations_limit = context.user_data.get(
        "locations_limit", LocationsInfo.DEFAULT_LOCATIONS_LIMIT
    )
    nearest_parkings, distances = LocationsInfo.get_nearest_cycleparks(
        lat, lon, k=locations_limit
    )

    logger.info(
        "Retrieved %d nearest cycle parks within distances %r",
        len(nearest_parkings),
        distances,
    )

    if distances[0] > 1000:
        context.application.message_queue.put_nowait(
            TextMessage(
                chat_id=update.effective_chat.id,
                text=f"❗️ No cycle parks found within 1 km of your location."
                f" For now, only London cycle parks are supported. ",
            )
        )
        return
    for i, (distance, parking_info) in enumerate(zip(distances, nearest_parkings)):
        context.application.message_queue.put_nowait(
            TextMessage(
                chat_id=update.effective_chat.id,
                text=f"{ordinal(i+1)} nearest cycle parking is within {distance:.0f} meters:\n",
            )
        )
        coords = [parking_info["longitude"], parking_info["latitude"]]
        context.application.message_queue.put_nowait(
            LocationMessage(
                chat_id=update.effective_chat.id,
                latitude=coords[1],
                longitude=coords[0],
            )
        )
        media = [
            InputMediaPhoto(media=url)
            for url in [parking_info.get("photo1_url"), parking_info.get("photo2_url")]
            if url is not None
        ]
        if media:
            context.application.message_queue.put_nowait(
                MediaGroupMessage(chat_id=update.effective_chat.id, media=media)
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
    update_str = (
        json.dumps(update.to_dict()) if isinstance(update, Update) else str(update)
    )

    context.application.error_queue.put_nowait(
        ErrorInfo(
            timestamp=datetime.now(),
            exception_type=type(context.error).__name__,
            error_message=str(context.error),
            update_str=update_str,
        )
    )


async def add_cyclepark(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start the process to add a new cycle park."""
    user_id = update.effective_user.id
    context.application.create_task(log_command(user_id, "add_cyclepark"))

    # Initialize user state for this process
    if "add_cyclepark_state" not in context.user_data:
        context.user_data["add_cyclepark_state"] = {}

    # Ask for location
    button = KeyboardButton(text="Share Location 📍", request_location=True)
    keyboard = ReplyKeyboardMarkup(
        [[button]], resize_keyboard=True, one_time_keyboard=True
    )
    context.application.message_queue.put_nowait(
        TextMessage(
            chat_id=update.effective_chat.id,
            text="Thank you for helping improve our cycle park map! Please share the location of the new cycle park.",
            reply_markup=keyboard,
        )
    )


async def add_cyclepark_location(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle location input for new cycle park."""
    user_id = update.effective_user.id

    if "add_cyclepark_state" not in context.user_data:
        return

    user_location = update.message.location
    if not user_location:
        return

    # Store location
    context.user_data["add_cyclepark_state"]["latitude"] = user_location.latitude
    context.user_data["add_cyclepark_state"]["longitude"] = user_location.longitude
    context.user_data["add_cyclepark_state"]["photos"] = []

    context.application.message_queue.put_nowait(
        TextMessage(
            chat_id=update.effective_chat.id,
            text="Great! Now please send me 2 photos of the cycle park. Send them one by one.",
        )
    )


async def handle_location_message(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Route location messages to appropriate handler based on user state."""
    # Check if user is in add cyclepark mode and has NOT yet provided location
    if (
        "add_cyclepark_state" in context.user_data
        and "latitude" not in context.user_data.get("add_cyclepark_state", {})
    ):
        await add_cyclepark_location(update, context)
    else:
        await show_nearest_cycleparks(update, context)


async def add_cyclepark_photo(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle photo input for new cycle park."""
    user_id = update.effective_user.id

    if "add_cyclepark_state" not in context.user_data:
        return

    state = context.user_data["add_cyclepark_state"]

    # Check if location was provided
    if "latitude" not in state:
        context.application.message_queue.put_nowait(
            TextMessage(
                chat_id=update.effective_chat.id,
                text="Please share your location first using /add command.",
            )
        )
        return

    if not update.message.photo:
        return

    # Get the largest photo file
    photo = update.message.photo[-1]

    # Store file_id
    state["photos"].append(photo.file_id)

    if len(state["photos"]) < 2:
        context.application.message_queue.put_nowait(
            TextMessage(
                chat_id=update.effective_chat.id,
                text=f"Photo {len(state['photos'])}/2 received. Please send the second photo.",
            )
        )
    else:
        # We have 2 photos, save submission
        await save_cyclepark_submission(update, context, state)


async def save_cyclepark_submission(
    update: Update, context: ContextTypes.DEFAULT_TYPE, state: dict
) -> None:
    """Save the cyclepark submission to database and notify admin."""
    user_id = update.effective_user.id

    try:
        async with get_session() as session:
            submission = CycleParkSubmission(
                user_id=user_id,
                latitude=state["latitude"],
                longitude=state["longitude"],
                photo1_file_id=state["photos"][0],
                photo2_file_id=state["photos"][1],
                status="pending",
            )
            session.add(submission)
            await session.commit()

            # Send confirmation to user
            context.application.message_queue.put_nowait(
                TextMessage(
                    chat_id=update.effective_chat.id,
                    text="✅ Thank you! Your submission has been sent to our admins for review. You'll be notified once it's approved.",
                )
            )

            # Notify admins
            await notify_admins_of_submission(context, submission, user_id)

            # Clear state
            context.user_data["add_cyclepark_state"] = {}

    except Exception as e:
        logger.error(f"Error saving cyclepark submission: {e}")
        context.application.message_queue.put_nowait(
            TextMessage(
                chat_id=update.effective_chat.id,
                text="❌ An error occurred while saving your submission. Please try again.",
            )
        )


async def notify_admins_of_submission(
    context: ContextTypes.DEFAULT_TYPE, submission: CycleParkSubmission, user_id: int
) -> None:
    """Send submission to admins for approval."""
    # Get admin IDs from application context
    admin_ids = getattr(context.application, "admin_ids", [])

    if not admin_ids:
        logger.warning("No admin IDs configured")
        return

    for admin_id in admin_ids:
        # Send location
        context.application.message_queue.put_nowait(
            LocationMessage(
                chat_id=admin_id,
                latitude=submission.latitude,
                longitude=submission.longitude,
            )
        )

        # Send photos
        media = [
            InputMediaPhoto(media=submission.photo1_file_id),
            InputMediaPhoto(media=submission.photo2_file_id),
        ]
        context.application.message_queue.put_nowait(
            MediaGroupMessage(chat_id=admin_id, media=media)
        )

        # Send approval buttons
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "✅ Approve",
                        callback_data=f"approve_submission_{submission.id}",
                    ),
                    InlineKeyboardButton(
                        "❌ Reject", callback_data=f"reject_submission_{submission.id}"
                    ),
                ]
            ]
        )
        context.application.message_queue.put_nowait(
            TextMessage(
                chat_id=admin_id,
                text=f"New cycle park submission from user {user_id}:\nLat: {submission.latitude}, Lon: {submission.longitude}\nSubmission ID: {submission.id}",
                reply_markup=keyboard,
            )
        )


async def handle_submission_approval(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle admin approval of cyclepark submission."""
    query = update.callback_query
    await query.answer()

    if not query.data.startswith("approve_submission_"):
        return

    submission_id = int(query.data.split("_")[-1])
    admin_id = update.effective_user.id

    try:
        async with get_session() as session:
            # Update submission status
            result = await session.execute(
                select(CycleParkSubmission).where(
                    CycleParkSubmission.id == submission_id
                )
            )
            submission = result.scalar_one_or_none()

            if not submission:
                await query.edit_message_text("Submission not found.")
                return

            submission.status = "approved"
            submission.reviewed_by = admin_id
            submission.reviewed_at = datetime.now()

            # Create a new CyclePark entry from the submission
            new_cyclepark = CyclePark(
                feature_id=str(uuid.uuid4()),
                photo1_url=submission.photo1_file_id,  # Store file_id as URL
                photo2_url=submission.photo2_file_id,  # Store file_id as URL
                longitude=submission.longitude,
                latitude=submission.latitude,
                # Set all facility flags to False by default (can be updated later)
                prk_carr=False,
                prk_cover=False,
                prk_secure=False,
                prk_locker=False,
                prk_sheff=False,
                prk_mstand=False,
                prk_pstand=False,
                prk_hoop=False,
                prk_post=False,
                prk_buterf=False,
                prk_wheel=False,
                prk_hangar=False,
                prk_tier=False,
                prk_other=False,
            )
            session.add(new_cyclepark)
            await session.commit()

            # Refresh the LocationsInfo cache (with throttling)
            await LocationsInfo.refresh_cycle_parks()

            # Notify the original user
            context.application.message_queue.put_nowait(
                TextMessage(
                    chat_id=submission.user_id,
                    text="✅ Great news! Your cycle park submission has been approved and added to our database!",
                )
            )

            await query.edit_message_text("✅ Submission approved! Cache refreshed.")

    except Exception as e:
        logger.error(f"Error approving submission: {e}")
        await query.edit_message_text("❌ Error approving submission.")


async def handle_submission_rejection(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle admin rejection of cyclepark submission."""
    query = update.callback_query
    await query.answer()

    if not query.data.startswith("reject_submission_"):
        return

    submission_id = int(query.data.split("_")[-1])
    admin_id = update.effective_user.id

    try:
        async with get_session() as session:
            # Update submission status
            result = await session.execute(
                select(CycleParkSubmission).where(
                    CycleParkSubmission.id == submission_id
                )
            )
            submission = result.scalar_one_or_none()

            if not submission:
                await query.edit_message_text("Submission not found.")
                return

            submission.status = "rejected"
            submission.reviewed_by = admin_id
            submission.reviewed_at = datetime.now()

            await session.commit()

            # Notify the original user
            context.application.message_queue.put_nowait(
                TextMessage(
                    chat_id=submission.user_id,
                    text="Thank you for your submission. Unfortunately, it didn't meet our criteria for addition.",
                )
            )

            await query.edit_message_text("✅ Submission rejected.")

    except Exception as e:
        logger.error(f"Error rejecting submission: {e}")
        await query.edit_message_text("❌ Error rejecting submission.")
