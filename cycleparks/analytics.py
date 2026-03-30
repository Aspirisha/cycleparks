import asyncio
import logging
import redis.asyncio as redis
from dataclasses import astuple
from datetime import datetime

from cycleparks.db import get_session
from cycleparks.models import Error, Request, SendFailure

r = redis.Redis(host="redis")
logger = logging.getLogger(__name__)

DUMP_FREQUENCY = 10  # seconds, how often to flush logs to the database
TIME_FORMAT = "%Y-%m-%d %H:%M:%S"
SEND_FAILURE_TIME_FORMAT = "%Y-%m-%d-%H:%M"


async def log_command(user_id: int, command: str):
    now = datetime.now().strftime(TIME_FORMAT)
    await r.incr(f"command_usage:{command}")
    await r.sadd(f"unique_users:{datetime.now().date()}", user_id)
    await r.rpush("request_log_queue", f"{now}|{user_id}|{command}")


async def log_send_failure(msg_type, error_message):
    now = datetime.now()
    bucket = now.strftime(SEND_FAILURE_TIME_FORMAT)
    key = f"failures|{bucket}|{msg_type}|{error_message[:50]}"
    await r.incr(key)
    await r.expire(key, 86400)  # 24 hours


async def _flush_failures_to_postgres(error_queue: asyncio.Queue):
    keys = await r.keys("failures|*")
    send_failures = []
    async with get_session() as session:
        for key in keys:
            count = int(await r.get(key))
            parts = key.decode().split("|")
            timestamp = datetime.strptime(parts[1], SEND_FAILURE_TIME_FORMAT)
            msg_type = parts[2]
            error_message = parts[3]
            send_failures.append(
                SendFailure(
                    timestamp=timestamp,
                    message_type=msg_type,
                    error_message=error_message,
                    count=count,
                )
            )
            await r.delete(key)

        logger.info("Flushing %d send failures to Postgres", len(send_failures))
        if send_failures:
            session.add_all(send_failures)

        error_records = []
        while not error_queue.empty():
            try:
                item = error_queue.get_nowait()
                error_records.append(
                    Error(
                        timestamp=item.timestamp,
                        exception_type=item.exception_type,
                        error_message=item.error_message,
                        update_str=item.update_str,
                    )
                )
            except asyncio.QueueEmpty:
                break

        logger.info("Flushing %d unhandled errors to Postgres", len(error_records))
        if error_records:
            session.add_all(error_records)

        await session.commit()


async def flush_failures_to_postgres(error_queue: asyncio.Queue):
    while True:
        try:
            await _flush_failures_to_postgres(error_queue)
        except Exception as e:
            logger.error("Flushing failed: %s", e)
        await asyncio.sleep(60)


async def flush_logs():
    while True:
        log = await r.lpop("request_log_queue")
        if not log:
            await asyncio.sleep(DUMP_FREQUENCY)
            continue

        ts, user_id, cmd = log.decode().split("|")
        ts = datetime.strptime(ts, TIME_FORMAT)

        async with get_session() as session:
            session.add(
                Request(
                    timestamp=ts,
                    user_id=int(user_id),
                    command=cmd,
                )
            )
            await session.commit()
