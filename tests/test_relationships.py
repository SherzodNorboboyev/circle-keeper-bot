from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.people import PeopleRepository
from app.db.repositories.relationships import RelationshipsRepository
from app.db.repositories.users import UserRepository
from app.services.people_service import PeopleService
from app.services.relationship_service import RelationshipService, RelationshipValidationError


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


async def create_person(
    sqlite_session: AsyncSession,
    user_id: int,
    first_name: str,
    category: str = "friend",
    gender: str | None = None,
):
    service = PeopleService()
    data = service.prepare_create_data(
        {
            "first_name": first_name,
            "category": category,
            "gender": gender,
        },
    )

    return await PeopleRepository(sqlite_session).create_person(
        user_id=user_id,
        data=data,
    )


async def test_parent_child_reverse_display(sqlite_session: AsyncSession) -> None:
    user_id = await create_test_user(sqlite_session, telegram_user_id=31001)
    parent = await create_person(sqlite_session, user_id, "Ali", category="father", gender="male")
    child = await create_person(sqlite_session, user_id, "Vali", category="child")

    service = RelationshipService()
    relationship = await service.create_relationship(
        session=sqlite_session,
        user_id=user_id,
        from_person_id=parent.id,
        to_person_id=child.id,
        relationship_type="parent",
        custom_label="father",
        is_bidirectional=False,
        reverse_relationship_type="child",
    )

    assert service.get_display_relationship_type_for_viewer(relationship, parent.id) == "child"
    assert service.get_display_relationship_type_for_viewer(relationship, child.id) == "parent"


async def test_symmetric_relationship_visible_for_both_sides(sqlite_session: AsyncSession) -> None:
    user_id = await create_test_user(sqlite_session, telegram_user_id=31002)
    first_person = await create_person(sqlite_session, user_id, "Ali")
    second_person = await create_person(sqlite_session, user_id, "Sardor")

    service = RelationshipService()
    relationship = await service.create_relationship(
        session=sqlite_session,
        user_id=user_id,
        from_person_id=first_person.id,
        to_person_id=second_person.id,
        relationship_type="friend",
    )

    assert relationship.is_bidirectional is True
    assert service.get_display_relationship_type_for_viewer(relationship, first_person.id) == "friend"
    assert service.get_display_relationship_type_for_viewer(relationship, second_person.id) == "friend"


async def test_self_relationship_rejected(sqlite_session: AsyncSession) -> None:
    user_id = await create_test_user(sqlite_session, telegram_user_id=31003)
    person = await create_person(sqlite_session, user_id, "Ali")

    service = RelationshipService()

    with pytest.raises(RelationshipValidationError) as exc:
        await service.create_relationship(
            session=sqlite_session,
            user_id=user_id,
            from_person_id=person.id,
            to_person_id=person.id,
            relationship_type="friend",
        )

    assert exc.value.message_key == "relationship.self_not_allowed"


async def test_cross_user_relationship_rejected(sqlite_session: AsyncSession) -> None:
    first_user_id = await create_test_user(sqlite_session, telegram_user_id=31004)
    second_user_id = await create_test_user(sqlite_session, telegram_user_id=31005)

    first_person = await create_person(sqlite_session, first_user_id, "Ali")
    second_person = await create_person(sqlite_session, second_user_id, "Vali")

    service = RelationshipService()

    with pytest.raises(RelationshipValidationError) as exc:
        await service.create_relationship(
            session=sqlite_session,
            user_id=first_user_id,
            from_person_id=first_person.id,
            to_person_id=second_person.id,
            relationship_type="friend",
        )

    assert exc.value.message_key == "relationship.person_not_found"


async def test_duplicate_relationship_rejected(sqlite_session: AsyncSession) -> None:
    user_id = await create_test_user(sqlite_session, telegram_user_id=31006)
    first_person = await create_person(sqlite_session, user_id, "Ali")
    second_person = await create_person(sqlite_session, user_id, "Sardor")

    service = RelationshipService()

    await service.create_relationship(
        session=sqlite_session,
        user_id=user_id,
        from_person_id=first_person.id,
        to_person_id=second_person.id,
        relationship_type="friend",
    )

    with pytest.raises(RelationshipValidationError) as exc:
        await service.create_relationship(
            session=sqlite_session,
            user_id=user_id,
            from_person_id=first_person.id,
            to_person_id=second_person.id,
            relationship_type="friend",
        )

    assert exc.value.message_key == "relationship.duplicate"


async def test_relationship_repository_soft_delete_for_person(sqlite_session: AsyncSession) -> None:
    user_id = await create_test_user(sqlite_session, telegram_user_id=31007)
    first_person = await create_person(sqlite_session, user_id, "Ali")
    second_person = await create_person(sqlite_session, user_id, "Vali")

    service = RelationshipService()
    relationship = await service.create_relationship(
        session=sqlite_session,
        user_id=user_id,
        from_person_id=first_person.id,
        to_person_id=second_person.id,
        relationship_type="friend",
    )

    repository = RelationshipsRepository(sqlite_session)
    deleted_relationships = await repository.soft_delete_relationships_for_person(
        user_id=user_id,
        person_id=first_person.id,
    )
    active_for_second_person = await repository.list_relationships_for_person(
        user_id=user_id,
        person_id=second_person.id,
    )

    assert len(deleted_relationships) == 1
    assert deleted_relationships[0].id == relationship.id
    assert deleted_relationships[0].deleted_at is not None
    assert active_for_second_person == []
