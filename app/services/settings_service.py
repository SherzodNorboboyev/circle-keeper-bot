from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Person, Reminder
from app.db.repositories.reminders import RemindersRepository
from app.db.repositories.settings import SettingsRepository
from app.db.repositories.users import UserRepository


@dataclass(frozen=True)
class EffectiveUserSettings:
    timezone: str
    reminder_time: time
    birthday_days_before: int
    birthday_on_day_enabled: bool


class SettingsValidationError(ValueError):
    def __init__(self, message_key: str, detail: str | None = None) -> None:
        self.message_key = message_key
        self.detail = detail

        super().__init__(message_key)


class SettingsService:
    DEFAULT_TIMEZONE = "Asia/Tashkent"
    DEFAULT_REMINDER_TIME = time(hour=9, minute=0)
    DEFAULT_DAYS_BEFORE = 1
    DEFAULT_ON_DAY_ENABLED = False

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = SettingsRepository(session)

    async def get_effective_settings(self, user_id: int) -> EffectiveUserSettings:
        user = await UserRepository(self.session).get_by_id(user_id=user_id)
        values = await self.repository.get_settings(user_id=user_id)

        timezone = str(
            values.get("timezone")
            or (user.timezone if user is not None else None)
            or self.DEFAULT_TIMEZONE
        )

        try:
            self.validate_timezone(timezone)
        except SettingsValidationError:
            timezone = self.DEFAULT_TIMEZONE

        reminder_time = self.parse_time(
            values.get("reminder_time") or self.DEFAULT_REMINDER_TIME.strftime("%H:%M"),
        )
        birthday_days_before = self.parse_days_before(
            values.get("birthday_days_before", self.DEFAULT_DAYS_BEFORE),
        )
        birthday_on_day_enabled = self.parse_bool(
            values.get("birthday_on_day_enabled", self.DEFAULT_ON_DAY_ENABLED),
        )

        return EffectiveUserSettings(
            timezone=timezone,
            reminder_time=reminder_time,
            birthday_days_before=birthday_days_before,
            birthday_on_day_enabled=birthday_on_day_enabled,
        )

    async def update_timezone(self, user_id: int, timezone: str) -> str:
        timezone = self.validate_timezone(timezone)

        await self.repository.set_setting(
            user_id=user_id,
            key="timezone",
            value=timezone,
        )

        user = await UserRepository(self.session).get_by_id(user_id=user_id)

        if user is not None:
            user.timezone = timezone
            await self.session.flush()

        return timezone

    async def update_reminder_time(self, user_id: int, reminder_time: str | time) -> time:
        parsed_time = self.parse_time(reminder_time)

        await self.repository.set_setting(
            user_id=user_id,
            key="reminder_time",
            value=parsed_time.strftime("%H:%M"),
        )

        result = await self.session.execute(
            select(Reminder).where(
                Reminder.user_id == user_id,
                Reminder.reminder_type == "birthday",
                Reminder.enabled.is_(True),
            ),
        )

        for reminder in result.scalars().all():
            reminder.remind_time_local = parsed_time

        await self.session.flush()

        return parsed_time

    async def update_days_before(self, user_id: int, days_before: int | str) -> int:
        parsed_days = self.parse_days_before(days_before)

        await self.repository.set_setting(
            user_id=user_id,
            key="birthday_days_before",
            value=parsed_days,
        )

        result = await self.session.execute(
            select(Reminder).where(
                Reminder.user_id == user_id,
                Reminder.reminder_type == "birthday",
                Reminder.enabled.is_(True),
                Reminder.days_before != 0,
            ),
        )

        reminders = list(result.scalars().all())
        existing_pairs = {(reminder.person_id, reminder.days_before) for reminder in reminders}

        for reminder in reminders:
            if (reminder.person_id, parsed_days) in existing_pairs and reminder.days_before != parsed_days:
                reminder.enabled = False
            else:
                reminder.days_before = parsed_days

        await self.session.flush()

        return parsed_days

    async def update_birthday_on_day_enabled(self, user_id: int, enabled: bool) -> bool:
        enabled = bool(enabled)

        await self.repository.set_setting(
            user_id=user_id,
            key="birthday_on_day_enabled",
            value=enabled,
        )

        effective_settings = await self.get_effective_settings(user_id=user_id)
        reminders_repository = RemindersRepository(self.session)

        if enabled:
            result = await self.session.execute(
                select(Person).where(
                    Person.user_id == user_id,
                    Person.deleted_at.is_(None),
                    Person.birth_month.is_not(None),
                    Person.birth_day.is_not(None),
                ),
            )

            for person in result.scalars().all():
                await reminders_repository.create_birthday_reminder(
                    user_id=user_id,
                    person_id=person.id,
                    days_before=0,
                    remind_time_local=effective_settings.reminder_time,
                    enabled=True,
                )
        else:
            result = await self.session.execute(
                select(Reminder).where(
                    Reminder.user_id == user_id,
                    Reminder.reminder_type == "birthday",
                    Reminder.days_before == 0,
                    Reminder.enabled.is_(True),
                ),
            )

            for reminder in result.scalars().all():
                reminder.enabled = False

            await self.session.flush()

        return enabled

    @classmethod
    def validate_timezone(cls, value: str) -> str:
        timezone = str(value).strip()

        if not timezone:
            raise SettingsValidationError("settings.invalid_timezone")

        try:
            ZoneInfo(timezone)
        except ZoneInfoNotFoundError as exc:
            raise SettingsValidationError("settings.invalid_timezone", detail=timezone) from exc

        return timezone

    @classmethod
    def parse_time(cls, value: str | time) -> time:
        if isinstance(value, time):
            return value.replace(second=0, microsecond=0)

        raw_value = str(value).strip()

        if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", raw_value):
            raise SettingsValidationError("settings.invalid_time", detail=raw_value)

        return time(
            hour=int(raw_value[:2]),
            minute=int(raw_value[3:]),
        )

    @classmethod
    def parse_days_before(cls, value: int | str) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError) as exc:
            raise SettingsValidationError("settings.invalid_days_before") from exc

        if parsed < 0 or parsed > 30:
            raise SettingsValidationError("settings.invalid_days_before")

        return parsed

    @staticmethod
    def parse_bool(value: object) -> bool:
        if isinstance(value, bool):
            return value

        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "ha", "да", "on"}

        return bool(value)