from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.db.session import build_session_maker, create_engine
from app.logging import setup_logging
from app.services.reminder_service import ReminderService


def parse_lookback_minutes(settings: Settings) -> int:
    raw_value = os.getenv("REMINDER_SCRIPT_LOOKBACK_MINUTES")

    if raw_value is None or not raw_value.strip():
        return settings.REMINDER_SCRIPT_LOOKBACK_MINUTES

    try:
        value = int(raw_value)
    except ValueError:
        return settings.REMINDER_SCRIPT_LOOKBACK_MINUTES

    return max(1, value)


async def run() -> int:
    settings = Settings()
    setup_logging(env=settings.ENV, level=settings.LOG_LEVEL)

    lookback_minutes = parse_lookback_minutes(settings)

    engine = create_engine(
        database_url=settings.DATABASE_URL,
        echo=settings.DB_ECHO,
    )
    session_maker: async_sessionmaker[AsyncSession] = build_session_maker(engine)

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    try:
        async with session_maker() as session:
            service = ReminderService(default_language=settings.DEFAULT_LANGUAGE)

            result = await service.send_due_reminders(
                session=session,
                bot=bot,
                now_utc=datetime.now(UTC),
                lookback_minutes=lookback_minutes,
            )

            await session.commit()

        logger.info(
            "send_due_reminders_completed",
            due_count=result.due_count,
            sent_count=result.sent_count,
            failed_count=result.failed_count,
            skipped_count=result.skipped_count,
            lookback_minutes=lookback_minutes,
        )

        return 1 if result.failed_count > 0 else 0
    except Exception:
        logger.exception("send_due_reminders_failed")
        return 1
    finally:
        await bot.session.close()
        await engine.dispose()


def main() -> None:
    raise SystemExit(asyncio.run(run()))


if __name__ == "__main__":
    main()