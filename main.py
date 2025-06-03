#!/usr/bin/env python

# pylint: disable=unused-argument

# This program is dedicated to the public domain under the CC0 license.


"""

Simple Bot to send nearest cycle parks based on user's location.
Then, the bot is started and runs until we press Ctrl-C on the command line.

Usage:
Press Ctrl-C on the command line or send a signal to the process to stop the bot.

"""

import json
import logging
import numpy as np
import os
import urllib.request
import yaml
from functools import partial
from typing import List, Dict

from sklearn.neighbors import BallTree

from telegram import BotCommand, Update, KeyboardButton, ReplyKeyboardMarkup, InputMediaPhoto
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from analytics import flush_logs, log_command


class LocationsInfo:
    location_data: List
    location_tree: BallTree
    DEFAULT_LOCATIONS_LIMIT = 3
    MAX_LOCATIONS_LIMIT = 10

    @classmethod
    def read_cycle_parks(cls, cycleparks_url: str):
        cache_file_name = 'cycleparks.json'
        if not os.path.exists(cache_file_name):
            logger.info(
                'Cycle park json is not cached; loading from %s',
                cycleparks_url)
            req = urllib.request.Request(
                cycleparks_url, headers={
                    'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as url:
                data = json.load(url)
                cls.location_data = data['features']
                logger.info(
                    'Loaded cycle parks data from %s; Saving to %s',
                    cycleparks_url,
                    cache_file_name)
                with open(cache_file_name, 'w') as f:
                    json.dump(data, f, indent=2)

        else:
            with open(cache_file_name) as f:
                cls.location_data = json.load(f)['features']
        cls.location_data = [
            entry for entry in cls.location_data if entry['properties']['PRK_HANGAR'] != 'TRUE']
        coords = np.radians(
            [list(reversed(entry["geometry"]['coordinates'])) for entry in cls.location_data])
        cls.location_tree = BallTree(coords, metric="haversine")

    @classmethod
    def get_nearest_cycleparks(cls, lat, lon, k=DEFAULT_LOCATIONS_LIMIT):
        target_rad = np.radians([lat, lon]).reshape(1, -1)
        distances, indices = cls.location_tree.query(target_rad, k=k)
        distances_meters = distances[0] * 6371000  # Convert to meters
        closest_entries = [cls.location_data[i] for i in indices[0]]
        return closest_entries, distances_meters


# Enable logging

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# set higher logging level for httpx to avoid all GET and POST requests
# being logged

logging.getLogger("httpx").setLevel(logging.INFO)
logger = logging.getLogger(__name__)


# Define a few command handlers. These usually take the two arguments update and
# context.

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    button = KeyboardButton(text="Share Location 📍", request_location=True)
    keyboard = ReplyKeyboardMarkup(
        [[button]], resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text(f"Hi {user.name} Please share your location:",
                                    reply_markup=keyboard)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "🤖 *Available Commands:*\n"
        "/start - Start the bot\n"
        "/limit <number> - Set number of returned closest parking locations\n"
        "/help - Show this help message\n"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Echo the user message."""
    await update.message.reply_text(update.message.text)


async def limit_locations(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args  # This gives you the list of arguments after the command
    current_limit = context.user_data.get(
        "locations_limit", LocationsInfo.DEFAULT_LOCATIONS_LIMIT)
    if not args:
        await update.message.reply_text(f"Send me preferred number of closest locations to show, e.g. /limit 3. Current limit is {current_limit}.")
        return
    try:
        locations_limit = int(args[0])
        if locations_limit > LocationsInfo.MAX_LOCATIONS_LIMIT:
            context.user_data["locations_limit"] = LocationsInfo.MAX_LOCATIONS_LIMIT
            await update.message.reply_text(f"✅ Location limit is set to {LocationsInfo.MAX_LOCATIONS_LIMIT} - this is maximum!")
        elif locations_limit < 1:
            context.user_data["locations_limit"] = 1
            await update.message.reply_text(f"✅ Location limit is set to 1 - this is minimum!")
        else:
            context.user_data["locations_limit"] = locations_limit
            await update.message.reply_text(f"✅ You set locations limit to {locations_limit}")
    except ValueError:
        await update.message.reply_text(f"❌ That doesn't look like a valid number. Locations limit is {current_limit}.")


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
    for i, (distance, parking_info) in enumerate(
            zip(distances, nearest_parkings)):
        await update.message.reply_text(f"{i+1}st nearest cycle parking is within {distance:.0f} meters:\n")
        coords = parking_info["geometry"]["coordinates"]
        await context.bot.send_location(
            chat_id=update.effective_chat.id,
            latitude=coords[1],
            longitude=coords[0]
        )
        props = parking_info['properties']
        media = [InputMediaPhoto(media=url)
                 for url in [props.get('PHOTO1_URL'), props.get('PHOTO2_URL')]
                 if url is not None]
        if media:
            await context.bot.send_media_group(chat_id=update.effective_chat.id, media=media)


async def setup_commands(app, postgres_config: Dict):
    commands = [
        BotCommand("start", "Start the bot"),
        BotCommand("limit", "Set limit of locations to show"),
        BotCommand("help", "Show help"),
    ]
    await app.bot.set_my_commands(commands)
    app.create_task(flush_logs(postgres_config))


def main() -> None:
    with open("config.yml") as f:
        config = yaml.load(f, Loader=yaml.SafeLoader)

    LocationsInfo.read_cycle_parks(config['cycleparks_url'])
    logger.info('Read cycle parks data: %d entries',
                len(LocationsInfo.location_data))

    # Create the Application and pass it your bot's token.
    application = Application.builder() \
        .token(config['token']) \
        .post_init(partial(setup_commands, postgres_config=config['postgres'])) \
        .build()
    # on different commands - answer in Telegram
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("limit", limit_locations))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(
        MessageHandler(
            filters.LOCATION,
            show_nearest_cycleparks))
    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
