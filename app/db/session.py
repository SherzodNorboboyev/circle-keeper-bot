from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine


_engine: AsyncEngine | None = None
_session_maker: async_sessionmaker[AsyncSession] | None = None


def is_sqlite_url(database_url: str) -> bool:
    return database_url.startswith("sqlite")


def create_engine(database_url: str, echo: bool = False) -> AsyncEngine:
    connect_args: dict[str, object] = {}

    if is_sqlite_url(database_url):
        connect_args["check_same_thread"] = False

    return create_async_engine(
        database_url,
        echo=echo,
        pool_pre_ping=not is_sqlite_url(database_url),
        connect_args=connect_args,
    )


def build_session_maker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


def init_db(database_url: str, echo: bool = False) -> async_sessionmaker[AsyncSession]:
    global _engine, _session_maker

    if _engine is None:
        _engine = create_engine(database_url=database_url, echo=echo)
        _session_maker = build_session_maker(_engine)

    if _session_maker is None:
        raise RuntimeError("Session maker was not initialized.")

    return _session_maker


def get_session_maker() -> async_sessionmaker[AsyncSession]:
    if _session_maker is None:
        raise RuntimeError("Database is not initialized. Call init_db first.")
    return _session_maker


async def close_engine() -> None:
    global _engine, _session_maker

    if _engine is not None:
        await _engine.dispose()

    _engine = None
    _session_maker = None


async def get_session() -> AsyncIterator[AsyncSession]:
    session_maker = get_session_maker()

    async with session_maker() as session:
        yield session


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    session_maker = get_session_maker()

    async with session_maker() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        else:
            await session.commit()


@asynccontextmanager
async def transaction(session: AsyncSession | None = None) -> AsyncIterator[AsyncSession]:
    owns_session = session is None

    if session is None:
        session = get_session_maker()()

    try:
        if session.in_transaction():
            yield session
        else:
            async with session.begin():
                yield session
    finally:
        if owns_session:
            await session.close()