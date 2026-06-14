from __future__ import annotations

from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ImportJob
from app.db.repositories.backups import BackupsRepository
from app.db.repositories.people import PeopleRepository
from app.db.repositories.reminders import RemindersRepository
from app.db.repositories.users import UserRepository
from app.services.admin_service import AdminService
from app.services.people_service import PeopleService
from app.services.relationship_service import RelationshipService


async def create_user(
    session: AsyncSession,
    telegram_user_id: int,
    is_admin: bool = False,
) -> int:
    user = await UserRepository(session).upsert_from_telegram(
        telegram_user_id=telegram_user_id,
        chat_id=telegram_user_id,
        username=f"user_{telegram_user_id}",
        first_name="Test",
        last_name="User",
        language_code="uz",
        is_admin=is_admin,
        default_timezone="Asia/Tashkent",
    )
    await session.flush()
    return user.id


async def create_person(
    session: AsyncSession,
    user_id: int,
    first_name: str,
):
    data = PeopleService().prepare_create_data(
        {
            "first_name": first_name,
            "category": "friend",
            "birth_date": "1995-04-21",
        },
    )

    return await PeopleRepository(session).create_person(user_id=user_id, data=data)


async def test_admin_stats_aggregate_only(sqlite_session: AsyncSession) -> None:
    admin_user_id = await create_user(sqlite_session, telegram_user_id=61001, is_admin=True)
    normal_user_id = await create_user(sqlite_session, telegram_user_id=61002, is_admin=False)

    first_person = await create_person(sqlite_session, admin_user_id, "Ali")
    second_person = await create_person(sqlite_session, admin_user_id, "Sardor")
    await create_person(sqlite_session, normal_user_id, "Other")

    await RelationshipService().create_relationship(
        session=sqlite_session,
        user_id=admin_user_id,
        from_person_id=first_person.id,
        to_person_id=second_person.id,
        relationship_type="friend",
    )

    await BackupsRepository(sqlite_session).create_backup_record(
        user_id=admin_user_id,
        backup_type="auto",
        storage_format="json",
        telegram_chat_id=61001,
        filename="networking_backup_failed.json",
        schema_version="1.0.0",
        status="failed",
        error_message="telegram failed",
    )

    import_job = ImportJob(
        user_id=admin_user_id,
        import_type="excel",
        filename="bad.xlsx",
        file_size=100,
        status="failed",
        total_errors=1,
    )
    sqlite_session.add(import_job)

    reminders_repository = RemindersRepository(sqlite_session)
    first_log = await reminders_repository.create_reminder_log(
        user_id=admin_user_id,
        person_id=first_person.id,
        event_date=date(2026, 4, 21),
        reminder_type="birthday",
        days_before=1,
        status="pending",
    )
    second_log = await reminders_repository.create_reminder_log(
        user_id=admin_user_id,
        person_id=second_person.id,
        event_date=date(2026, 4, 21),
        reminder_type="birthday",
        days_before=1,
        status="pending",
    )

    await reminders_repository.mark_log_sent(
        user_id=admin_user_id,
        log_id=first_log.id,
        telegram_message_id=1,
    )
    await reminders_repository.mark_log_failed(
        user_id=admin_user_id,
        log_id=second_log.id,
        error_message="telegram failed",
    )

    await sqlite_session.flush()

    stats = await AdminService(sqlite_session).get_stats()

    assert stats.total_users == 2
    assert stats.active_users == 2
    assert stats.total_people == 3
    assert stats.total_active_people == 3
    assert stats.total_relationships == 1
    assert stats.total_active_relationships == 1
    assert stats.failed_backups == 1
    assert stats.failed_imports == 1
    assert stats.reminder_sent_count == 1
    assert stats.reminder_failed_count == 1
    assert stats.recent_import_job_counts["failed"] == 1
