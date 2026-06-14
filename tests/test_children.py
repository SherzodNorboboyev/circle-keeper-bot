from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.people import PeopleRepository
from app.db.repositories.relationships import RelationshipsRepository
from app.db.repositories.users import UserRepository
from app.services.child_service import ChildService
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


async def create_parent(sqlite_session: AsyncSession, user_id: int):
    data = PeopleService().prepare_create_data(
        {
            "first_name": "Ali",
            "category": "father",
            "gender": "male",
        },
    )

    return await PeopleRepository(sqlite_session).create_person(
        user_id=user_id,
        data=data,
    )


async def test_add_child_creates_separate_person_and_relationship(sqlite_session: AsyncSession) -> None:
    user_id = await create_test_user(sqlite_session, telegram_user_id=32001)
    parent = await create_parent(sqlite_session, user_id)

    result = await ChildService().create_child_for_parent(
        session=sqlite_session,
        user_id=user_id,
        parent_person_id=parent.id,
        child_data={
            "first_name": "Vali",
            "last_name": "Aliyev",
            "birth_date": "04-21",
            "gender": "male",
            "note": "Katta farzand",
        },
    )

    people_repository = PeopleRepository(sqlite_session)
    relationships_repository = RelationshipsRepository(sqlite_session)
    relationship_service = RelationshipService()

    people = await people_repository.list_people(user_id=user_id)
    relationships_for_parent = await relationships_repository.list_relationships_for_person(
        user_id=user_id,
        person_id=parent.id,
    )

    assert len(people) == 2
    assert result.child.id != parent.id
    assert result.child.first_name == "Vali"
    assert result.child.category == "child"
    assert result.child.birth_date is None
    assert result.child.birth_year_known is False
    assert result.child.birth_month == 4
    assert result.child.birth_day == 21

    assert len(relationships_for_parent) == 1
    assert relationships_for_parent[0].from_person_id == parent.id
    assert relationships_for_parent[0].to_person_id == result.child.id
    assert relationships_for_parent[0].relationship_type == "parent"
    assert relationships_for_parent[0].custom_label == "father"
    assert relationships_for_parent[0].is_bidirectional is False
    assert relationships_for_parent[0].reverse_relationship_type == "child"

    assert (
        relationship_service.get_display_relationship_type_for_viewer(
            relationships_for_parent[0],
            parent.id,
        )
        == "child"
    )
    assert (
        relationship_service.get_display_relationship_type_for_viewer(
            relationships_for_parent[0],
            result.child.id,
        )
        == "parent"
    )
