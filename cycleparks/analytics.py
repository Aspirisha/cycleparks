import asyncio
import asyncpg
import logging
import redis.asyncio as redis
from dataclasses import astuple
from datetime import datetime

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


async def _flush_failures_to_postgres(
    db_pool: asyncpg.Pool, error_queue: asyncio.Queue
):
    keys = await r.keys("failures|*")
    async with db_pool.acquire() as conn:
        results = []
        for key in keys:
            count = int(await r.get(key))
            # Parse key: failures|2025-06-04-17:30|photo|RateLimitExceeded
            parts = key.decode().split("|")
            timestamp = datetime.strptime(parts[1], SEND_FAILURE_TIME_FORMAT)
            msg_type = parts[2]
            error = parts[3]
            results.append((timestamp, msg_type, error, count))
            await r.delete(key)
        logger.info("Flushing %d send failures to Postgres", len(results))
        await conn.executemany(
            "INSERT INTO send_failures (timestamp, message_type, error_message, count) VALUES ($1, $2, $3, $4)",
            results,
        )

        results = []
        while not error_queue.empty():
            try:
                item = error_queue.get_nowait()
                results.append(astuple(item))
            except asyncio.QueueEmpty:
                break
        logger.info("Flushing %d unhandled errors to Postgres", len(results))
        await conn.executemany(
            "INSERT INTO errors (timestamp, exception_type, error_message, update_str) VALUES ($1, $2, $3, $4)",
            results,
        )


async def flush_failures_to_postgres(db_pool: asyncpg.Pool, error_queue: asyncio.Queue):
    while True:
        try:
            await _flush_failures_to_postgres(db_pool, error_queue)
        except Exception as e:
            logger.error("Flushing failed: %s", e)
        await asyncio.sleep(60)  # every minute


async def flush_logs(db_pool: asyncpg.Pool):
    while True:
        log = await r.lpop("request_log_queue")
        if not log:
            await asyncio.sleep(DUMP_FREQUENCY)
            continue
        async with db_pool.acquire() as conn:
            ts, user_id, cmd = log.decode().split("|")
            ts = datetime.strptime(ts, TIME_FORMAT)
            await conn.execute(
                "INSERT INTO requests (timestamp, user_id, command) VALUES ($1, $2, $3)",
                ts,
                int(user_id),
                cmd,
            )
