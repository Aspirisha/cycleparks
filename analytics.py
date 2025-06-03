import asyncio
import asyncpg
import redis.asyncio as redis
from datetime import datetime
from typing import Dict

r = redis.Redis()

DUMP_FREQUENCY = 10  # seconds, how often to flush logs to the database
TIME_FORMAT = "%Y-%m-%d %H:%M:%S"


async def log_command(user_id: int, command: str):
    now = datetime.now().strftime(TIME_FORMAT)
    await r.incr(f"command_usage:{command}")
    await r.sadd(f"unique_users:{datetime.now().date()}", user_id)
    await r.rpush("request_log_queue", f"{now}|{user_id}|{command}")


async def flush_logs(postgres_config: Dict):
    conn = await asyncpg.connect(
        user=postgres_config['user'],
        password=postgres_config['password'],
        database=postgres_config['database'],
        host=postgres_config['host'])
    while True:
        log = await r.lpop("request_log_queue")
        if log:
            ts, user_id, cmd = log.decode().split("|")
            ts = datetime.strptime(ts, TIME_FORMAT)
            await conn.execute(
                "INSERT INTO requests (timestamp, user_id, command) VALUES ($1, $2, $3)",
                ts, int(user_id), cmd
            )
        else:
            await asyncio.sleep(DUMP_FREQUENCY)
