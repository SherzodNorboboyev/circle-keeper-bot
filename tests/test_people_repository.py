from __future__ import annotations

from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.people import PeopleRepository
from app.db.repositories.users import UserRepository
from app.services.people_service import PeopleService


async def create_test_user(sqlite_session: AsyncSession, telegram_user_id: int = 9001) -> int:
    repository = UserRepository(sqlite_session)

    user = await repository.upsert_from_telegram(
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


async def test_people_repository_create_get_list(sqlite_session: AsyncSession) -> None:
    user_id = await create_test_user(sqlite_session)
    service = PeopleService()
    repository = PeopleRepository(sqlite_session)

    prepared = service.prepare_create_data(
        {
            "first_name": "Ali",
            "last_name": "Valiyev",
            "phone": "+998 90-123-45-67",
            "telegram_username": "@AliValiyev",
            "birth_date": "1995-04-21",
            "category": "friend",
        },
    )

    person = await repository.create_person(user_id=user_id, data=prepared)

    found_person = await repository.get_person_by_id(
        user_id=user_id,
        person_id=person.id,
    )
    people = await repository.list_people(user_id=user_id)

    assert found_person is not None
    assert found_person.id == person.id
    assert found_person.user_id == user_id
    assert found_person.first_name == "Ali"
    assert found_person.phone == "+998901234567"
    assert found_person.telegram_username == "alivaliyev"
    assert found_person.birth_date == date(1995, 4, 21)
    assert len(people) == 1
    assert people[0].id == person.id


async def test_people_repository_search_query(sqlite_session: AsyncSession) -> None:
    user_id = await create_test_user(sqlite_session, telegram_user_id=9002)
    service = PeopleService()
    repository = PeopleRepository(sqlite_session)

    ali = service.prepare_create_data(
        {
            "first_name": "Ali",
            "last_name": "Valiyev",
            "nickname": "Alish",
            "phone": "+998 90-111-22-33",
            "category": "friend",
            "workplace": "Example LLC",
        },
    )
    sardor = service.prepare_create_data(
        {
            "first_name": "Sardor",
            "last_name": "Karimov",
            "phone": "+998 90-444-55-66",
            "category": "colleague",
            "workplace": "Another LLC",
        },
    )

    await repository.create_person(user_id=user_id, data=ali)
    await repository.create_person(user_id=user_id, data=sardor)

    results_by_name = await repository.search_people(user_id=user_id, query="ali")
    results_by_phone = await repository.search_people(user_id=user_id, query="901112233")
    results_by_workplace = await repository.search_people(user_id=user_id, query="another")

    assert [person.first_name for person in results_by_name] == ["Ali"]
    assert [person.first_name for person in results_by_phone] == ["Ali"]
    assert [person.first_name for person in results_by_workplace] == ["Sardor"]


async def test_people_soft_delete_removed_from_active_list(sqlite_session: AsyncSession) -> None:
    user_id = await create_test_user(sqlite_session, telegram_user_id=9003)
    service = PeopleService()
    repository = PeopleRepository(sqlite_session)

    prepared = service.prepare_create_data(
        {
            "first_name": "Ali",
            "category": "friend",
        },
    )

    person = await repository.create_person(user_id=user_id, data=prepared)

    deleted_person = await repository.soft_delete_person(
        user_id=user_id,
        person_id=person.id,
    )

    active_people = await repository.list_people(user_id=user_id)
    hidden_person = await repository.get_person_by_id(
        user_id=user_id,
        person_id=person.id,
    )
    included_deleted_person = await repository.get_person_by_id(
        user_id=user_id,
        person_id=person.id,
        include_deleted=True,
    )

    assert deleted_person is not None
    assert deleted_person.deleted_at is not None
    assert active_people == []
    assert hidden_person is None
    assert included_deleted_person is not None
    assert included_deleted_person.id == person.id


async def test_people_repository_isolated_by_user_id(sqlite_session: AsyncSession) -> None:
    first_user_id = await create_test_user(sqlite_session, telegram_user_id=9004)
    second_user_id = await create_test_user(sqlite_session, telegram_user_id=9005)

    service = PeopleService()
    repository = PeopleRepository(sqlite_session)

    prepared = service.prepare_create_data(
        {
            "first_name": "Ali",
            "category": "friend",
        },
    )

    person = await repository.create_person(user_id=first_user_id, data=prepared)

    visible_for_owner = await repository.get_person_by_id(
        user_id=first_user_id,
        person_id=person.id,
    )
    hidden_for_other_user = await repository.get_person_by_id(
        user_id=second_user_id,
        person_id=person.id,
    )

    assert visible_for_owner is not None
    assert hidden_for_other_user is None


async def test_people_repository_find_duplicates(sqlite_session: AsyncSession) -> None:
    user_id = await create_test_user(sqlite_session, telegram_user_id=9006)
    service = PeopleService()
    repository = PeopleRepository(sqlite_session)

    prepared = service.prepare_create_data(
        {
            "first_name": "Ali",
            "last_name": "Valiyev",
            "phone": "+998 90-123-45-67",
            "telegram_username": "@ali",
            "birth_date": "1995-04-21",
            "nickname": "Alish",
            "category": "friend",
        },
    )

    await repository.create_person(user_id=user_id, data=prepared)

    duplicates = await repository.find_duplicates(
        user_id=user_id,
        phone="+998901234567",
        telegram_username="ali",
        first_name="Ali",
        last_name="Valiyev",
        birth_date=date(1995, 4, 21),
        nickname="Alish",
    )

    assert len(duplicates) == 1
    assert duplicates[0].first_name == "Ali"