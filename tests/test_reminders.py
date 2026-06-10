from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.people import PeopleRepository
from app.db.repositories.reminders import RemindersRepository
from app.db.repositories.users import UserRepository
from app.services.people_service import PeopleService
from app.services.reminder_service import ReminderService


async def create_test_user(
    sqlite_session: AsyncSession,
    telegram_user_id: int = 40001,
    timezone: str = "Asia/Tashkent",
) -> int:
    user = await UserRepository(sqlite_session).upsert_from_telegram(
        telegram_user_id=telegram_user_id,
        chat_id=telegram_user_id,
        username=f"user_{telegram_user_id}",
        first_name="Test",
        last_name="User",
        language_code="uz",
        is_admin=False,
        default_timezone=timezone,
    )
    user.timezone = timezone
    await sqlite_session.flush()

    return user.id


async def create_person_with_birth_date(
    sqlite_session: AsyncSession,
    user_id: int,
    first_name: str,
    birth_date_value: str,
):
    data = PeopleService().prepare_create_data(
        {
            "first_name": first_name,
            "birth_date": birth_date_value,
            "category": "friend",
        },
    )

    return await PeopleRepository(sqlite_session).create_person(
        user_id=user_id,
        data=data,
    )


async def test_due_reminder_calculation_asia_tashkent_days_before_one(sqlite_session: AsyncSession) -> None:
    user_id = await create_test_user(sqlite_session, telegram_user_id=41001)
    person = await create_person_with_birth_date(
        sqlite_session,
        user_id=user_id,
        first_name="Ali",
        birth_date_value="1995-04-21",
    )

    reminders_repository = RemindersRepository(sqlite_session)
    await reminders_repository.create_birthday_reminder(
        user_id=user_id,
        person_id=person.id,
        days_before=1,
        remind_time_local="09:00",
        enabled=True,
    )

    now_utc = datetime(2026, 4, 20, 4, 5, tzinfo=UTC)
    due = await reminders_repository.find_due_birthday_reminders(
        now_utc=now_utc,
        lookback_minutes=10,
    )

    assert len(due) == 1
    assert due[0].timezone == "Asia/Tashkent"
    assert due[0].scheduled_at_local.hour == 9
    assert due[0].scheduled_at_local.minute == 0
    assert due[0].target_date == date(2026, 4, 21)
    assert due[0].person.id == person.id


async def test_age_calculation_with_known_year(sqlite_session: AsyncSession) -> None:
    user_id = await create_test_user(sqlite_session, telegram_user_id=41002)
    person = await create_person_with_birth_date(
        sqlite_session,
        user_id=user_id,
        first_name="Ali",
        birth_date_value="1995-04-21",
    )

    age = ReminderService().calculate_birthday_age(
        person=person,
        target_date=date(2026, 4, 21),
    )

    assert age == 31


async def test_year_unknown_age_not_shown(sqlite_session: AsyncSession) -> None:
    user_id = await create_test_user(sqlite_session, telegram_user_id=41003)
    person = await create_person_with_birth_date(
        sqlite_session,
        user_id=user_id,
        first_name="Ali",
        birth_date_value="04-21",
    )

    age = ReminderService().calculate_birthday_age(
        person=person,
        target_date=date(2026, 4, 21),
    )

    assert age is None


async def test_feb_29_policy_leap_and_non_leap(sqlite_session: AsyncSession) -> None:
    user_id = await create_test_user(sqlite_session, telegram_user_id=41004)
    person = await create_person_with_birth_date(
        sqlite_session,
        user_id=user_id,
        first_name="Leap",
        birth_date_value="2000-02-29",
    )

    service = ReminderService()

    assert service.birthday_matches_date(person=person, target_date=date(2024, 2, 29)) is True
    assert service.birthday_matches_date(person=person, target_date=date(2025, 2, 28)) is True
    assert service.birthday_matches_date(person=person, target_date=date(2025, 3, 1)) is False

    assert service.calculate_birthday_age(person=person, target_date=date(2025, 2, 28)) == 25


async def test_duplicate_reminder_log_idempotency(sqlite_session: AsyncSession) -> None:
    user_id = await create_test_user(sqlite_session, telegram_user_id=41005)
    person = await create_person_with_birth_date(
        sqlite_session,
        user_id=user_id,
        first_name="Ali",
        birth_date_value="1995-04-21",
    )

    repository = RemindersRepository(sqlite_session)

    first_log = await repository.create_reminder_log(
        user_id=user_id,
        person_id=person.id,
        event_date=date(2026, 4, 21),
        reminder_type="birthday",
        days_before=1,
    )

    second_log = await repository.create_reminder_log(
        user_id=user_id,
        person_id=person.id,
        event_date=date(2026, 4, 21),
        reminder_type="birthday",
        days_before=1,
    )

    assert first_log is not None
    assert second_log is None
    assert await repository.log_exists(
        user_id=user_id,
        person_id=person.id,
        event_date=date(2026, 4, 21),
        reminder_type="birthday",
        days_before=1,
    ) is True


async def test_person_soft_delete_reminder_disable(sqlite_session: AsyncSession) -> None:
    user_id = await create_test_user(sqlite_session, telegram_user_id=41006)
    person = await create_person_with_birth_date(
        sqlite_session,
        user_id=user_id,
        first_name="Ali",
        birth_date_value="1995-04-21",
    )

    reminders_repository = RemindersRepository(sqlite_session)

    reminder = await reminders_repository.create_birthday_reminder(
        user_id=user_id,
        person_id=person.id,
        days_before=1,
        remind_time_local="09:00",
        enabled=True,
    )

    deleted_person = await PeopleRepository(sqlite_session).soft_delete_person(
        user_id=user_id,
        person_id=person.id,
    )
    disabled_count = await reminders_repository.disable_reminders_for_person(
        user_id=user_id,
        person_id=person.id,
    )

    refreshed_reminders = await reminders_repository.list_reminders_for_person(
        user_id=user_id,
        person_id=person.id,
    )

    assert deleted_person is not None
    assert deleted_person.deleted_at is not None
    assert disabled_count == 1
    assert refreshed_reminders[0].id == reminder.id
    assert refreshed_reminders[0].enabled is False