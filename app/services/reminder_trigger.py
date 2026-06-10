from __future__ import annotations

from typing import Any

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Person
from app.services.reminder_service import ReminderService


class ReminderTriggerService:
    async def trigger_default_birthday_reminder(
        self,
        session: AsyncSession,
        user_id: int,
        person: Person,
        reason: str,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        reminders = await ReminderService().ensure_default_birthday_reminders_for_person(
            session=session,
            user_id=user_id,
            person=person,
        )

        logger.bind(
            user_id=user_id,
            person_id=person.id,
            reason=reason,
            metadata=metadata or {},
            reminders_created_or_updated=len(reminders),
        ).info("birthday_reminder_trigger_completed")

        return len(reminders)