from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from html import escape
from typing import Any
from zoneinfo import ZoneInfo

from aiogram import Bot
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Person, Reminder, User
from app.db.repositories.reminders import DueBirthdayReminder, RemindersRepository
from app.db.repositories.users import UserRepository
from app.services.i18n import I18nService
from app.services.people_service import PeopleService
from app.services.settings_service import SettingsService


@dataclass(frozen=True)
class ReminderSendResult:
    due_count: int
    sent_count: int
    failed_count: int
    skipped_count: int


@dataclass(frozen=True)
class UpcomingBirthday:
    person: Person
    birthday_date: date
    days_until: int
    age: int | None


class ReminderService:
    def __init__(
        self,
        i18n: I18nService | None = None,
        default_language: str = "uz",
    ) -> None:
        self.i18n = i18n or I18nService(default_lang=default_language)
        self.default_language = default_language
        self.people_service = PeopleService()

    async def ensure_default_birthday_reminders_for_person(
        self,
        session: AsyncSession,
        user_id: int,
        person: Person,
    ) -> list[Reminder]:
        if not person.birth_month or not person.birth_day:
            return []

        settings = await SettingsService(session).get_effective_settings(user_id=user_id)
        repository = RemindersRepository(session)

        reminders: list[Reminder] = []

        reminders.append(
            await repository.create_birthday_reminder(
                user_id=user_id,
                person_id=person.id,
                days_before=settings.birthday_days_before,
                remind_time_local=settings.reminder_time,
                enabled=True,
            ),
        )

        if settings.birthday_on_day_enabled and settings.birthday_days_before != 0:
            reminders.append(
                await repository.create_birthday_reminder(
                    user_id=user_id,
                    person_id=person.id,
                    days_before=0,
                    remind_time_local=settings.reminder_time,
                    enabled=True,
                ),
            )

        return reminders

    async def send_due_reminders(
        self,
        session: AsyncSession,
        bot: Bot,
        now_utc: datetime | None = None,
        lookback_minutes: int = 5,
        user_id: int | None = None,
    ) -> ReminderSendResult:
        now_utc = self.ensure_utc(now_utc or datetime.now(UTC))
        repository = RemindersRepository(session)

        due_reminders = await repository.find_due_birthday_reminders(
            now_utc=now_utc,
            lookback_minutes=lookback_minutes,
            user_id=user_id,
        )

        sent_count = 0
        failed_count = 0
        skipped_count = 0

        for due in due_reminders:
            reminder_log = await repository.create_reminder_log(
                user_id=due.user.id,
                person_id=due.person.id,
                event_date=due.target_date,
                reminder_type="birthday",
                days_before=due.reminder.days_before,
                status="pending",
            )

            if reminder_log is None:
                skipped_count += 1
                continue

            text = self.build_birthday_message(
                due=due,
                lang=due.user.language_code or self.default_language,
            )

            try:
                sent_message = await bot.send_message(
                    chat_id=due.user.chat_id,
                    text=text,
                )
            except Exception as exc:
                failed_count += 1
                await repository.mark_log_failed(
                    user_id=due.user.id,
                    log_id=reminder_log.id,
                    error_message=str(exc),
                )
                logger.exception(
                    "birthday_reminder_send_failed",
                    user_id=due.user.id,
                    person_id=due.person.id,
                    reminder_id=due.reminder.id,
                )
                continue

            sent_count += 1
            await repository.mark_log_sent(
                user_id=due.user.id,
                log_id=reminder_log.id,
                telegram_message_id=sent_message.message_id,
            )

        return ReminderSendResult(
            due_count=len(due_reminders),
            sent_count=sent_count,
            failed_count=failed_count,
            skipped_count=skipped_count,
        )

    async def get_upcoming_birthdays(
        self,
        session: AsyncSession,
        user_id: int,
        days_ahead: int,
        now_utc: datetime | None = None,
    ) -> list[UpcomingBirthday]:
        days_ahead = max(0, min(days_ahead, 366))
        user = await UserRepository(session).get_by_id(user_id=user_id)

        if user is None:
            return []

        settings = await SettingsService(session).get_effective_settings(user_id=user_id)
        timezone = ZoneInfo(settings.timezone)

        now_utc = self.ensure_utc(now_utc or datetime.now(UTC))
        today_local = now_utc.astimezone(timezone).date()

        result = await session.execute(
            select(Person).where(
                Person.user_id == user_id,
                Person.deleted_at.is_(None),
                Person.birth_month.is_not(None),
                Person.birth_day.is_not(None),
            ),
        )

        people = list(result.scalars().all())
        items: list[UpcomingBirthday] = []

        for offset in range(days_ahead + 1):
            target_date = today_local + timedelta(days=offset)

            for person in people:
                if not self.birthday_matches_date(person=person, target_date=target_date):
                    continue

                items.append(
                    UpcomingBirthday(
                        person=person,
                        birthday_date=target_date,
                        days_until=offset,
                        age=self.calculate_birthday_age(person=person, target_date=target_date),
                    ),
                )

        return sorted(
            items,
            key=lambda item: (
                item.days_until,
                self.people_service.format_full_name(item.person).lower(),
                item.person.id,
            ),
        )

    async def get_birthdays_for_exact_offset(
        self,
        session: AsyncSession,
        user_id: int,
        offset_days: int,
        now_utc: datetime | None = None,
    ) -> list[UpcomingBirthday]:
        items = await self.get_upcoming_birthdays(
            session=session,
            user_id=user_id,
            days_ahead=max(0, offset_days),
            now_utc=now_utc,
        )

        return [
            item
            for item in items
            if item.days_until == offset_days
        ]

    def build_birthday_message(
        self,
        due: DueBirthdayReminder,
        lang: str,
    ) -> str:
        full_name = escape(self.people_service.format_full_name(due.person))
        age = self.calculate_birthday_age(
            person=due.person,
            target_date=due.target_date,
        )

        if due.reminder.days_before == 0:
            if age is not None:
                return self.i18n.t(
                    "reminder.birthday_today_with_age",
                    lang=lang,
                    full_name=full_name,
                    age=age,
                )

            return self.i18n.t(
                "reminder.birthday_today",
                lang=lang,
                full_name=full_name,
            )

        if due.reminder.days_before == 1:
            if age is not None:
                return self.i18n.t(
                    "reminder.birthday_tomorrow_with_age",
                    lang=lang,
                    full_name=full_name,
                    age=age,
                )

            return self.i18n.t(
                "reminder.birthday_tomorrow",
                lang=lang,
                full_name=full_name,
            )

        if age is not None:
            return self.i18n.t(
                "reminder.birthday_upcoming_with_age",
                lang=lang,
                full_name=full_name,
                age=age,
                days=due.reminder.days_before,
            )

        return self.i18n.t(
            "reminder.birthday_upcoming",
            lang=lang,
            full_name=full_name,
            days=due.reminder.days_before,
        )

    def calculate_birthday_age(
        self,
        person: Person,
        target_date: date,
    ) -> int | None:
        if not person.birth_year_known or person.birth_date is None:
            return None

        birthday = person.birth_date
        age = target_date.year - birthday.year

        if birthday.month == 2 and birthday.day == 29:
            if not self.is_leap_year(target_date.year) and target_date.month == 2 and target_date.day == 28:
                return max(0, age)

        if (target_date.month, target_date.day) < (birthday.month, birthday.day):
            age -= 1

        return max(0, age)

    def birthday_matches_date(
        self,
        person: Person,
        target_date: date,
    ) -> bool:
        return RemindersRepository.birthday_matches_date(
            birth_month=person.birth_month,
            birth_day=person.birth_day,
            target_date=target_date,
        )

    @staticmethod
    def is_leap_year(year: int) -> bool:
        return RemindersRepository.is_leap_year(year)

    @staticmethod
    def ensure_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)

        return value.astimezone(UTC)