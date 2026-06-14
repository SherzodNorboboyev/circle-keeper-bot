from __future__ import annotations

from collections.abc import Awaitable, Callable, Collection
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.users import UserRepository


class CurrentUserMiddleware(BaseMiddleware):
    def __init__(self, admin_ids: Collection[int], default_timezone: str) -> None:
        self._admin_ids = set(admin_ids)
        self._default_timezone = default_timezone

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        telegram_user = getattr(event, "from_user", None)

        if telegram_user is None:
            return await handler(event, data)

        session = data.get("session")
        if not isinstance(session, AsyncSession):
            raise RuntimeError("DatabaseSessionMiddleware must run before CurrentUserMiddleware.")

        chat_id = self._extract_chat_id(event=event, fallback_chat_id=telegram_user.id)

        repository = UserRepository(session)
        current_user = await repository.upsert_from_telegram(
            telegram_user_id=telegram_user.id,
            chat_id=chat_id,
            username=telegram_user.username,
            first_name=telegram_user.first_name,
            last_name=telegram_user.last_name,
            language_code=None,
            is_admin=telegram_user.id in self._admin_ids,
            default_timezone=self._default_timezone,
        )

        data["current_user"] = current_user

        if not current_user.is_active:
            await self._answer_inactive_user(event)
            return None

        return await handler(event, data)

    @staticmethod
    def _extract_chat_id(event: TelegramObject, fallback_chat_id: int) -> int:
        if isinstance(event, Message):
            return event.chat.id

        if isinstance(event, CallbackQuery) and event.message and hasattr(event.message, "chat"):
            return event.message.chat.id

        return fallback_chat_id

    @staticmethod
    async def _answer_inactive_user(event: TelegramObject) -> None:
        text = "Profilingiz vaqtincha bloklangan. Administrator bilan bog‘laning."

        if isinstance(event, Message):
            await event.answer(text)
            return

        if isinstance(event, CallbackQuery):
            await event.answer(text, show_alert=True)

            if event.message and hasattr(event.message, "answer"):
                await event.message.answer(text)
