from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

engine: Optional[AsyncEngine] = None
async_session: Optional[sessionmaker] = None


def init_db(postgres_config: dict):
    """Initialize the async SQLAlchemy engine and session factory."""
    global engine, async_session

    user = postgres_config.get("user", "postgres")
    password = postgres_config.get("password", "")
    host = postgres_config.get("host", "localhost")
    port = postgres_config.get("port", 5432)
    database = postgres_config.get("database", "cycleparks")

    database_url = f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}"
    engine = create_async_engine(database_url, future=True, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    return engine, async_session


@asynccontextmanager
async def get_session() -> AsyncSession:
    if async_session is None:
        raise RuntimeError(
            "SQLAlchemy async_session is not initialized; call init_db first"
        )
    async with async_session() as session:
        yield session
