from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.users import UserRepository


async def test_user_upsert_creates_user(sqlite_session: AsyncSession) -> None:
    repository = UserRepository(sqlite_session)

    user = await repository.upsert_from_telegram(
        telegram_user_id=1001,
        chat_id=2001,
        username="ali",
        first_name="Ali",
        last_name="Valiyev",
        language_code=None,
        is_admin=True,
        default_timezone="Asia/Tashkent",
    )

    await sqlite_session.commit()

    assert user.id is not None
    assert user.telegram_user_id == 1001
    assert user.chat_id == 2001
    assert user.username == "ali"
    assert user.language_code is None
    assert user.timezone == "Asia/Tashkent"
    assert user.is_admin is True
    assert user.is_active is True


async def test_user_upsert_updates_existing_user(sqlite_session: AsyncSession) -> None:
    repository = UserRepository(sqlite_session)

    first_user = await repository.upsert_from_telegram(
        telegram_user_id=1002,
        chat_id=2002,
        username="old_username",
        first_name="Old",
        last_name="Name",
        language_code=None,
        is_admin=False,
        default_timezone="Asia/Tashkent",
    )
    await sqlite_session.commit()

    second_user = await repository.upsert_from_telegram(
        telegram_user_id=1002,
        chat_id=3002,
        username="new_username",
        first_name="New",
        last_name="Name",
        language_code=None,
        is_admin=True,
        default_timezone="Asia/Tashkent",
    )
    await sqlite_session.commit()

    assert second_user.id == first_user.id
    assert second_user.chat_id == 3002
    assert second_user.username == "new_username"
    assert second_user.first_name == "New"
    assert second_user.is_admin is True


async def test_set_language(sqlite_session: AsyncSession) -> None:
    repository = UserRepository(sqlite_session)

    user = await repository.upsert_from_telegram(
        telegram_user_id=1003,
        chat_id=2003,
        username=None,
        first_name="Ali",
        last_name=None,
        language_code=None,
        is_admin=False,
        default_timezone="Asia/Tashkent",
    )

    await repository.set_language(user_id=user.id, language_code="ru")
    await sqlite_session.commit()

    assert user.language_code == "ru"
