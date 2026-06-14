from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.users import UserRepository


async def test_user_upsert_creates_and_updates_user(sqlite_session: AsyncSession) -> None:
    repository = UserRepository(sqlite_session)

    user = await repository.upsert_from_telegram(
        telegram_user_id=62001,
        chat_id=62001,
        username="old_username",
        first_name="Old",
        last_name="User",
        language_code=None,
        is_admin=False,
        default_timezone="Asia/Tashkent",
    )

    updated_user = await repository.upsert_from_telegram(
        telegram_user_id=62001,
        chat_id=62002,
        username="new_username",
        first_name="New",
        last_name="User",
        language_code=None,
        is_admin=True,
        default_timezone="Asia/Tashkent",
    )

    assert updated_user.id == user.id
    assert updated_user.chat_id == 62002
    assert updated_user.username == "new_username"
    assert updated_user.first_name == "New"
    assert updated_user.is_admin is True
    assert updated_user.is_active is True


async def test_user_deactivate_does_not_reactivate_on_upsert(sqlite_session: AsyncSession) -> None:
    repository = UserRepository(sqlite_session)

    user = await repository.upsert_from_telegram(
        telegram_user_id=62003,
        chat_id=62003,
        username=None,
        first_name="Inactive",
        last_name=None,
        language_code=None,
        is_admin=False,
        default_timezone="Asia/Tashkent",
    )

    await repository.deactivate(user_id=user.id)

    updated_user = await repository.upsert_from_telegram(
        telegram_user_id=62003,
        chat_id=62004,
        username=None,
        first_name="Inactive",
        last_name=None,
        language_code=None,
        is_admin=False,
        default_timezone="Asia/Tashkent",
    )

    assert updated_user.id == user.id
    assert updated_user.is_active is False