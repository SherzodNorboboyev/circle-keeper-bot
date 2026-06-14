from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any

from aiogram import Bot
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.backup_service import BackupService


class BackupDebounceQueue:
    def __init__(
        self,
        session_maker: async_sessionmaker[AsyncSession],
        bot: Bot,
        debounce_seconds: int = 45,
        default_language: str = "uz",
    ) -> None:
        self.session_maker = session_maker
        self.bot = bot
        self.debounce_seconds = max(1, debounce_seconds)
        self.default_language = default_language
        self._tasks: dict[int, asyncio.Task[None]] = {}
        self._reasons: dict[int, set[str]] = defaultdict(set)
        self._metadata: dict[int, list[dict[str, Any]]] = defaultdict(list)

    def enqueue(
        self,
        user_id: int,
        reason: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._reasons[user_id].add(reason)

        if metadata:
            self._metadata[user_id].append(metadata)

        existing_task = self._tasks.get(user_id)

        if existing_task is not None and not existing_task.done():
            existing_task.cancel()

        self._tasks[user_id] = asyncio.create_task(
            self._run_after_delay(user_id=user_id),
        )

        logger.bind(
            user_id=user_id,
            reason=reason,
            debounce_seconds=self.debounce_seconds,
        ).info("backup_enqueued")

    async def shutdown(self) -> None:
        tasks = [
            task
            for task in self._tasks.values()
            if not task.done()
        ]

        for task in tasks:
            task.cancel()

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        self._tasks.clear()
        self._reasons.clear()
        self._metadata.clear()

    async def _run_after_delay(self, user_id: int) -> None:
        try:
            await asyncio.sleep(self.debounce_seconds)

            reasons = sorted(self._reasons.pop(user_id, set()))
            metadata = self._metadata.pop(user_id, [])

            async with self.session_maker() as session:
                service = BackupService(
                    session=session,
                    bot=self.bot,
                    default_language=self.default_language,
                )

                await service.create_and_send_json_backup(
                    user_id=user_id,
                    backup_type="auto",
                    reason=", ".join(reasons) if reasons else "auto",
                    notify_on_failure=True,
                )

                await session.commit()

            logger.bind(
                user_id=user_id,
                reasons=reasons,
                metadata=metadata,
            ).info("backup_queue_processed")
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("backup_queue_processing_failed", user_id=user_id)
        finally:
            task = self._tasks.get(user_id)

            if task is not None and task.done():
                self._tasks.pop(user_id, None)


_backup_queue: BackupDebounceQueue | None = None


def configure_backup_trigger(
    session_maker: async_sessionmaker[AsyncSession],
    bot: Bot,
    debounce_seconds: int = 45,
    default_language: str = "uz",
) -> None:
    global _backup_queue

    _backup_queue = BackupDebounceQueue(
        session_maker=session_maker,
        bot=bot,
        debounce_seconds=debounce_seconds,
        default_language=default_language,
    )


async def shutdown_backup_trigger() -> None:
    global _backup_queue

    if _backup_queue is not None:
        await _backup_queue.shutdown()
        _backup_queue = None


class BackupTriggerService:
    async def trigger_user_backup(
        self,
        user_id: int,
        reason: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if _backup_queue is None:
            logger.bind(
                user_id=user_id,
                reason=reason,
                metadata=metadata or {},
            ).warning("backup_trigger_not_configured")
            return

        _backup_queue.enqueue(
            user_id=user_id,
            reason=reason,
            metadata=metadata,
        )