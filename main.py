#!/usr/bin/env python

# pylint: disable=unused-argument

# This program is dedicated to the public domain under the CC0 license.


"""

Simple Bot to send nearest cycle parks based on user's location.
Then, the bot is started and runs until we press Ctrl-C on the command line.

Usage:
Press Ctrl-C on the command line or send a signal to the process to stop the bot.

"""

import asyncio
import logging
import yaml

from asyncio import Queue
from functools import partial
from typing import Dict

from telegram import BotCommand, Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackQueryHandler,
)

from cycleparks.analytics import flush_logs, flush_failures_to_postgres
from cycleparks.db import init_db
from cycleparks.handlers import (
    start,
    help_command,
    limit_locations,
    show_nearest_cycleparks,
    error_handler,
    add_cyclepark,
    add_cyclepark_location,
    add_cyclepark_photo,
    handle_submission_approval,
    handle_submission_rejection,
    handle_location_message,
)
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
        BotCommand("add", "Add a new cycle park"),
        BotCommand("help", "Show help"),
    ]
    await app.bot.set_my_commands(commands)

    app.create_task(flush_logs())
    app.create_task(flush_failures_to_postgres(app.error_queue))
    app.create_task(message_sender(app.message_queue, app.bot))


def main() -> None:
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )
    logging.getLogger("httpx").setLevel(logging.WARN)

    with open("config.yml") as f:
        config = yaml.load(f, Loader=yaml.SafeLoader)

    # Create event loop that persists for the entire application
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        init_db(config["postgres"])
        loop.run_until_complete(LocationsInfo.read_cycle_parks())
        logger.info(
            "Read cycle parks data: %d entries", len(LocationsInfo.location_data)
        )

        # Create the Application and pass it your bot's token.
        application = (
            MyApplication.builder()
            .token(config["token"])
            .post_init(partial(setup_commands, postgres_config=config["postgres"]))
            .build()
        )

        # Set admin IDs for approval workflow
        application.admin_ids = config.get("admin_ids", [])

        # on different commands - answer in Telegram
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("limit", limit_locations))
        application.add_handler(CommandHandler("add", add_cyclepark))
        application.add_handler(CommandHandler("help", help_command))

        # Unified location handler that routes based on user state
        application.add_handler(
            MessageHandler(filters.LOCATION & ~filters.COMMAND, handle_location_message)
        )
        application.add_handler(MessageHandler(filters.PHOTO, add_cyclepark_photo))

        # Callback handlers for admin approval/rejection
        application.add_handler(
            CallbackQueryHandler(
                handle_submission_approval, pattern="^approve_submission_"
            )
        )
        application.add_handler(
            CallbackQueryHandler(
                handle_submission_rejection, pattern="^reject_submission_"
            )
        )

        # Run the bot until the user presses Ctrl-C
        application.add_error_handler(error_handler)
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    finally:
        loop.close()


if __name__ == "__main__":
    main()
