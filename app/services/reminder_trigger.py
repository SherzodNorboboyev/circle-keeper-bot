from __future__ import annotations

from typing import Any

from loguru import logger


class ReminderTriggerService:
    async def trigger_default_birthday_reminder(
        self,
        user_id: int,
        person_id: int,
        reason: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        logger.bind(
            user_id=user_id,
            person_id=person_id,
            reason=reason,
            metadata=metadata or {},
        ).info("birthday_reminder_trigger_registered")