from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.people import PeopleRepository
from app.db.repositories.relationships import RelationshipsRepository
from app.db.repositories.users import UserRepository
from app.services.people_service import PeopleService
from app.services.relationship_service import RelationshipService


async def create_test_user(
    sqlite_session: AsyncSession,
    telegram_user_id: int,
) -> int:
    user = await UserRepository(sqlite_session).upsert_from_telegram(
        telegram_user_id=telegram_user_id,
        chat_id=telegram_user_id,
        username=f"user_{telegram_user_id}",
        first_name="Test",
        last_name="User",
        language_code=None,
        is_admin=False,
        default_timezone="Asia/Tashkent",
    )
    await sqlite_session.flush()

    return user.id


async def create_person(sqlite_session: AsyncSession, user_id: int, first_name: str):
    data = PeopleService().prepare_create_data(
        {
            "first_name": first_name,
            "category": "friend",
        },
    )

    return await PeopleRepository(sqlite_session).create_person(
        user_id=user_id,
        data=data,
    )


async def test_person_soft_delete_soft_deletes_relationships(sqlite_session: AsyncSession) -> None:
    user_id = await create_test_user(sqlite_session, telegram_user_id=33001)
    first_person = await create_person(sqlite_session, user_id, "Ali")
    second_person = await create_person(sqlite_session, user_id, "Sardor")

    relationship_service = RelationshipService()
    relationship = await relationship_service.create_relationship(
        session=sqlite_session,
        user_id=user_id,
        from_person_id=first_person.id,
        to_person_id=second_person.id,
        relationship_type="friend",
    )

    people_repository = PeopleRepository(sqlite_session)
    relationships_repository = RelationshipsRepository(sqlite_session)

    deleted_person = await people_repository.soft_delete_person(
        user_id=user_id,
        person_id=first_person.id,
    )
    deleted_relationships = await relationships_repository.soft_delete_relationships_for_person(
        user_id=user_id,
        person_id=first_person.id,
    )

    active_relationships_for_second_person = await relationships_repository.list_relationships_for_person(
        user_id=user_id,
        person_id=second_person.id,
    )

    assert deleted_person is not None
    assert deleted_person.deleted_at is not None
    assert len(deleted_relationships) == 1
    assert deleted_relationships[0].id == relationship.id
    assert deleted_relationships[0].deleted_at is not None
    assert active_relationships_for_second_person == []