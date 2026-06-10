from __future__ import annotations

from datetime import UTC, datetime

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.reminder_service import ReminderService


class SchedulerService:
    def __init__(
        self,
        bot: Bot,
        session_maker: async_sessionmaker[AsyncSession],
        interval_minutes: int = 5,
        lookback_minutes: int = 10,
    ) -> None:
        self.bot = bot
        self.session_maker = session_maker
        self.interval_minutes = max(1, interval_minutes)
        self.lookback_minutes = max(1, lookback_minutes)
        self.scheduler = AsyncIOScheduler(timezone="UTC")

    def start(self) -> None:
        self.scheduler.add_job(
            self.process_due_reminders,
            trigger=IntervalTrigger(minutes=self.interval_minutes),
            id="send_due_birthday_reminders",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        self.scheduler.start()

        logger.info(
            "Reminder scheduler started.",
            interval_minutes=self.interval_minutes,
            lookback_minutes=self.lookback_minutes,
        )

    def shutdown(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("Reminder scheduler stopped.")

    async def process_due_reminders(self) -> None:
        service = ReminderService()

        async with self.session_maker() as session:
            try:
                result = await service.send_due_reminders(
                    session=session,
                    bot=self.bot,
                    now_utc=datetime.now(UTC),
                    lookback_minutes=self.lookback_minutes,
                )
            except Exception:
                await session.rollback()
                logger.exception("Reminder scheduler job failed.")
                return

            await session.commit()

        logger.info(
            "Reminder scheduler job completed.",
            due_count=result.due_count,
            sent_count=result.sent_count,
            failed_count=result.failed_count,
            skipped_count=result.skipped_count,
        )