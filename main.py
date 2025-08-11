#!/usr/bin/env python

# pylint: disable=unused-argument

# This program is dedicated to the public domain under the CC0 license.


"""

Simple Bot to send nearest cycle parks based on user's location.
Then, the bot is started and runs until we press Ctrl-C on the command line.

Usage:
Press Ctrl-C on the command line or send a signal to the process to stop the bot.

"""

import asyncpg
import logging
import yaml

from asyncio import Queue
from functools import partial
from typing import Dict


from telegram import BotCommand, Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from cycleparks.analytics import flush_logs, flush_failures_to_postgres
from cycleparks.handlers import start, help_command, limit_locations, show_nearest_cycleparks, error_handler
from cycleparks.locations_info import LocationsInfo
from cycleparks.message_queue import message_sender

# set higher logging level for httpx to avoid all GET and POST requests
# being logged

logger = logging.getLogger(__name__)


class MyApplication(Application):
    """
    Custom Application class to add custom attributes.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.message_queue = Queue()
        self.error_queue = Queue()

    @classmethod
    def builder(cls):
        return super().builder().application_class(cls)


async def setup_commands(app: MyApplication, postgres_config: Dict):
    commands = [
        BotCommand("start", "Start the bot"),
        BotCommand("limit", "Set limit of locations to show"),
        BotCommand("help", "Show help"),
    ]
    await app.bot.set_my_commands(commands)
    db_pool = await asyncpg.create_pool(
        user=postgres_config['user'],
        password=postgres_config['password'],
        database=postgres_config['database'],
        host=postgres_config['host'])
    app.create_task(flush_logs(db_pool))
    app.create_task(flush_failures_to_postgres(db_pool, app.error_queue))
    app.create_task(message_sender(app.message_queue, app.bot))


def main() -> None:
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
    )
    logging.getLogger("httpx").setLevel(logging.WARN)

    with open("config.yml") as f:
        config = yaml.load(f, Loader=yaml.SafeLoader)

    LocationsInfo.read_cycle_parks(config['cycleparks_url'])
    logger.info('Read cycle parks data: %d entries',
                len(LocationsInfo.location_data))

    # Create the Application and pass it your bot's token.
    application = MyApplication.builder() \
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
    application.add_error_handler(error_handler)
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
