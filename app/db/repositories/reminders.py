from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import sqlalchemy as sa
from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Person, Reminder, ReminderLog, User, UserSetting, utc_now


@dataclass(frozen=True)
class DueBirthdayReminder:
    reminder: Reminder
    person: Person
    user: User
    timezone: str
    scheduled_at_local: datetime
    target_date: date


class RemindersRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_birthday_reminder(
        self,
        user_id: int,
        person_id: int,
        days_before: int = 1,
        remind_time_local: str | time = "09:00",
        enabled: bool = True,
    ) -> Reminder:
        parsed_time = self.parse_time_value(remind_time_local)

        existing = await self.get_birthday_reminder_by_person_and_days(
            user_id=user_id,
            person_id=person_id,
            days_before=days_before,
        )

        if existing is not None:
            existing.remind_time_local = parsed_time
            existing.enabled = enabled
            await self.session.flush()
            await self.session.refresh(existing)
            return existing

        reminder = Reminder(
            user_id=user_id,
            person_id=person_id,
            reminder_type="birthday",
            days_before=days_before,
            remind_time_local=parsed_time,
            enabled=enabled,
        )

        self.session.add(reminder)
        await self.session.flush()
        await self.session.refresh(reminder)

        return reminder

    async def get_birthday_reminder_by_person_and_days(
        self,
        user_id: int,
        person_id: int,
        days_before: int,
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

    async def get_reminder(
        self,
        user_id: int,
        reminder_id: int,
    ) -> Reminder | None:
        result = await self.session.execute(
            select(Reminder).where(
                Reminder.id == reminder_id,
                Reminder.user_id == user_id,
            ),
        )

        return result.scalar_one_or_none()

    async def list_reminders_for_person(
        self,
        user_id: int,
        person_id: int,
    ) -> list[Reminder]:
        result = await self.session.execute(
            select(Reminder)
            .where(
                Reminder.user_id == user_id,
                Reminder.person_id == person_id,
            )
            .order_by(Reminder.days_before.asc(), Reminder.remind_time_local.asc()),
        )

        return list(result.scalars().all())

    async def list_enabled_birthday_reminders(
        self,
        user_id: int | None = None,
    ) -> list[tuple[Reminder, Person, User]]:
        statement = (
            select(Reminder, Person, User)
            .join(
                Person,
                and_(
                    Person.id == Reminder.person_id,
                    Person.user_id == Reminder.user_id,
                ),
            )
            .join(User, User.id == Reminder.user_id)
            .where(
                Reminder.reminder_type == "birthday",
                Reminder.enabled.is_(True),
                Person.deleted_at.is_(None),
                Person.birth_month.is_not(None),
                Person.birth_day.is_not(None),
                User.is_active.is_(True),
            )
        )

        if user_id is not None:
            statement = statement.where(Reminder.user_id == user_id)

        result = await self.session.execute(statement)
        return list(result.all())

    async def update_reminder(
        self,
        user_id: int,
        reminder_id: int,
        data: dict[str, Any],
    ) -> Reminder | None:
        reminder = await self.get_reminder(user_id=user_id, reminder_id=reminder_id)

        if reminder is None:
            return None

        allowed_fields = {
            "days_before",
            "remind_time_local",
            "enabled",
        }

        for field_name, value in data.items():
            if field_name not in allowed_fields:
                continue

            if field_name == "remind_time_local":
                value = self.parse_time_value(value)

            setattr(reminder, field_name, value)

        await self.session.flush()
        await self.session.refresh(reminder)

        return reminder

    async def disable_reminders_for_person(
        self,
        user_id: int,
        person_id: int,
    ) -> int:
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

    async def find_due_birthday_reminders(
        self,
        now_utc: datetime,
        lookback_minutes: int = 5,
        user_id: int | None = None,
    ) -> list[DueBirthdayReminder]:
        now_utc = self.ensure_aware_utc(now_utc)
        lookback_minutes = max(1, lookback_minutes)

        rows = await self.list_enabled_birthday_reminders(user_id=user_id)

        if not rows:
            return []

        timezone_by_user = await self.get_timezone_settings_for_users(
            user_ids={user.id for _, _, user in rows},
        )

        due: list[DueBirthdayReminder] = []

        for reminder, person, user in rows:
            timezone_name = timezone_by_user.get(user.id) or user.timezone or "Asia/Tashkent"

            try:
                timezone = ZoneInfo(timezone_name)
            except ZoneInfoNotFoundError:
                timezone_name = "Asia/Tashkent"
                timezone = ZoneInfo(timezone_name)

            now_local = now_utc.astimezone(timezone)
            window_start_local = now_local - timedelta(minutes=lookback_minutes)

            for scheduled_date in self.iter_dates(window_start_local.date(), now_local.date()):
                scheduled_at_local = datetime.combine(
                    scheduled_date,
                    reminder.remind_time_local,
                    tzinfo=timezone,
                )

                if not (window_start_local <= scheduled_at_local <= now_local):
                    continue

                target_date = scheduled_date + timedelta(days=reminder.days_before)

                if not self.birthday_matches_date(
                    birth_month=person.birth_month,
                    birth_day=person.birth_day,
                    target_date=target_date,
                ):
                    continue

                due.append(
                    DueBirthdayReminder(
                        reminder=reminder,
                        person=person,
                        user=user,
                        timezone=timezone_name,
                        scheduled_at_local=scheduled_at_local,
                        target_date=target_date,
                    ),
                )

        return due

    async def create_reminder_log(
        self,
        user_id: int,
        person_id: int,
        event_date: date,
        reminder_type: str = "birthday",
        days_before: int = 1,
        status: str = "pending",
        telegram_message_id: int | None = None,
        sent_at: datetime | None = None,
        error_message: str | None = None,
    ) -> ReminderLog | None:
        reminder_log = ReminderLog(
            user_id=user_id,
            person_id=person_id,
            event_date=event_date,
            reminder_type=reminder_type,
            days_before=days_before,
            status=status,
            telegram_message_id=telegram_message_id,
            sent_at=sent_at,
            error_message=error_message,
        )

        try:
            async with self.session.begin_nested():
                self.session.add(reminder_log)
                await self.session.flush()
        except IntegrityError:
            return None

        await self.session.refresh(reminder_log)
        return reminder_log

    async def mark_log_sent(
        self,
        user_id: int,
        log_id: int,
        telegram_message_id: int,
        sent_at: datetime | None = None,
    ) -> ReminderLog | None:
        result = await self.session.execute(
            select(ReminderLog).where(
                ReminderLog.id == log_id,
                ReminderLog.user_id == user_id,
            ),
        )

        reminder_log = result.scalar_one_or_none()

        if reminder_log is None:
            return None

        reminder_log.status = "sent"
        reminder_log.telegram_message_id = telegram_message_id
        reminder_log.sent_at = sent_at or utc_now()
        reminder_log.error_message = None

        await self.session.flush()
        await self.session.refresh(reminder_log)

        return reminder_log

    async def mark_log_failed(
        self,
        user_id: int,
        log_id: int,
        error_message: str,
    ) -> ReminderLog | None:
        result = await self.session.execute(
            select(ReminderLog).where(
                ReminderLog.id == log_id,
                ReminderLog.user_id == user_id,
            ),
        )

        reminder_log = result.scalar_one_or_none()

        if reminder_log is None:
            return None

        reminder_log.status = "failed"
        reminder_log.error_message = error_message[:5000]
        reminder_log.sent_at = None

        await self.session.flush()
        await self.session.refresh(reminder_log)

        return reminder_log

    async def log_exists(
        self,
        user_id: int,
        person_id: int,
        event_date: date,
        reminder_type: str = "birthday",
        days_before: int = 1,
    ) -> bool:
        result = await self.session.execute(
            select(ReminderLog.id)
            .where(
                ReminderLog.user_id == user_id,
                ReminderLog.person_id == person_id,
                ReminderLog.event_date == event_date,
                ReminderLog.reminder_type == reminder_type,
                ReminderLog.days_before == days_before,
            )
            .limit(1),
        )

        return result.scalar_one_or_none() is not None

    async def get_timezone_settings_for_users(self, user_ids: set[int]) -> dict[int, str]:
        if not user_ids:
            return {}

        result = await self.session.execute(
            select(UserSetting).where(
                UserSetting.user_id.in_(user_ids),
                UserSetting.key == "timezone",
            ),
        )

        settings = list(result.scalars().all())

        timezone_by_user: dict[int, str] = {}

        for setting in settings:
            value = self.extract_json_value(setting.value)

            if isinstance(value, str) and value.strip():
                timezone_by_user[setting.user_id] = value.strip()

        return timezone_by_user

    @staticmethod
    def parse_time_value(value: str | time) -> time:
        if isinstance(value, time):
            return value.replace(second=0, microsecond=0)

        raw_value = str(value).strip()

        try:
            parsed = datetime.strptime(raw_value, "%H:%M").time()
        except ValueError as exc:
            raise ValueError("Time must be in HH:MM format.") from exc

        return parsed.replace(second=0, microsecond=0)

    @staticmethod
    def ensure_aware_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)

        return value.astimezone(UTC)

    @staticmethod
    def extract_json_value(value: dict[str, Any]) -> Any:
        if isinstance(value, dict) and "value" in value:
            return value["value"]

        return value

    @staticmethod
    def iter_dates(start_date: date, end_date: date) -> list[date]:
        if end_date < start_date:
            return []

        days = (end_date - start_date).days

        return [
            start_date + timedelta(days=offset)
            for offset in range(days + 1)
        ]

    @staticmethod
    def birthday_matches_date(
        birth_month: int | None,
        birth_day: int | None,
        target_date: date,
    ) -> bool:
        if birth_month is None or birth_day is None:
            return False

        if birth_month == 2 and birth_day == 29:
            if RemindersRepository.is_leap_year(target_date.year):
                return target_date.month == 2 and target_date.day == 29

            return target_date.month == 2 and target_date.day == 28

        return birth_month == target_date.month and birth_day == target_date.day

    @staticmethod
    def is_leap_year(year: int) -> bool:
        return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)