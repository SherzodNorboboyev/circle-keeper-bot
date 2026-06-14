from __future__ import annotations

from collections.abc import Collection

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import SUPPORTED_LANGUAGES, User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, user_id: int) -> User | None:
        result = await self.session.execute(
            select(User).where(User.id == user_id),
        )
        return result.scalar_one_or_none()

    async def get_by_telegram_user_id(self, telegram_user_id: int) -> User | None:
        result = await self.session.execute(
            select(User).where(User.telegram_user_id == telegram_user_id),
        )
        return result.scalar_one_or_none()

    async def upsert_from_telegram(
        self,
        telegram_user_id: int,
        chat_id: int,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
        language_code: str | None,
        is_admin: bool,
        default_timezone: str,
    ) -> User:
        existing_user = await self.get_by_telegram_user_id(telegram_user_id=telegram_user_id)

        normalized_language = self._normalize_language(language_code)

        if existing_user is not None:
            existing_user.chat_id = chat_id
            existing_user.username = username
            existing_user.first_name = first_name
            existing_user.last_name = last_name
            existing_user.is_admin = bool(existing_user.is_admin or is_admin)

            if not existing_user.timezone:
                existing_user.timezone = default_timezone

            await self.session.flush()
            return existing_user

        user = User(
            telegram_user_id=telegram_user_id,
            chat_id=chat_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            language_code=normalized_language,
            timezone=default_timezone,
            is_admin=is_admin,
            is_active=True,
        )

        self.session.add(user)
        await self.session.flush()
        return user

    async def set_language(self, user_id: int, language_code: str) -> User:
        normalized_language = self._normalize_language(language_code)

        if normalized_language is None:
            raise ValueError(f"Unsupported language_code: {language_code}")

        user = await self.get_by_id(user_id=user_id)

        if user is None:
            raise ValueError(f"User not found: {user_id}")

        user.language_code = normalized_language
        await self.session.flush()
        return user

    async def set_timezone(self, user_id: int, timezone: str) -> User:
        user = await self.get_by_id(user_id=user_id)

        if user is None:
            raise ValueError(f"User not found: {user_id}")

        user.timezone = timezone
        await self.session.flush()
        return user

    async def set_admin(self, user_id: int, is_admin: bool) -> User:
        user = await self.get_by_id(user_id=user_id)

        if user is None:
            raise ValueError(f"User not found: {user_id}")

        user.is_admin = is_admin
        await self.session.flush()
        return user

    async def deactivate(self, user_id: int) -> None:
        user = await self.get_by_id(user_id=user_id)

        if user is None:
            return

        user.is_active = False
        await self.session.flush()

    async def activate(self, user_id: int) -> None:
        user = await self.get_by_id(user_id=user_id)

        if user is None:
            return

        user.is_active = True
        await self.session.flush()

    @staticmethod
    def _normalize_language(language_code: str | None) -> str | None:
        if language_code is None:
            return None

        language_code = language_code.lower().split("-", maxsplit=1)[0]

        if language_code in SUPPORTED_LANGUAGES:
            return language_code

        return None

    @staticmethod
    def is_admin(telegram_user_id: int, admin_ids: Collection[int]) -> bool:
        return telegram_user_id in set(admin_ids)
