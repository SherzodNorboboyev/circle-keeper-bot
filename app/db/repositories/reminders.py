from __future__ import annotations

from datetime import time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Reminder


class RemindersRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_person_birthday_reminder(
        self,
        user_id: int,
        person_id: int,
        days_before: int = 1,
    ) -> Reminder | None:
        result = await self.session.execute(
            select(Reminder).where(
                Reminder.user_id == user_id,
                Reminder.person_id == person_id,
                Reminder.reminder_type == "birthday",
                Reminder.days_before == days_before,
            ),
        )
        return result.scalar_one_or_none()

    async def ensure_birthday_reminder(
        self,
        user_id: int,
        person_id: int,
        days_before: int = 1,
        remind_time_local: time = time(hour=9, minute=0),
        enabled: bool = True,
    ) -> Reminder:
        existing_reminder = await self.get_person_birthday_reminder(
            user_id=user_id,
            person_id=person_id,
            days_before=days_before,
        )

        if existing_reminder is not None:
            existing_reminder.remind_time_local = remind_time_local
            existing_reminder.enabled = enabled
            await self.session.flush()
            return existing_reminder

        reminder = Reminder(
            user_id=user_id,
            person_id=person_id,
            reminder_type="birthday",
            days_before=days_before,
            remind_time_local=remind_time_local,
            enabled=enabled,
        )

        self.session.add(reminder)
        await self.session.flush()
        return reminder

    async def disable_for_person(self, user_id: int, person_id: int) -> int:
        result = await self.session.execute(
            select(Reminder).where(
                Reminder.user_id == user_id,
                Reminder.person_id == person_id,
                Reminder.enabled.is_(True),
            ),
        )

        reminders = list(result.scalars().all())

        for reminder in reminders:
            reminder.enabled = False

        await self.session.flush()
        return len(reminders)