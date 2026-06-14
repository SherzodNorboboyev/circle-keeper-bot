from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from app.db.models import User
from app.services.i18n import I18nService


class I18nMiddleware(BaseMiddleware):
    def __init__(self, i18n: I18nService, default_language: str = "uz") -> None:
        self._i18n = i18n
        self._default_language = default_language

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        current_user = data.get("current_user")

        if isinstance(current_user, User) and current_user.language_code:
            lang = current_user.language_code
        else:
            lang = self._default_language

        data["lang"] = lang
        data["i18n"] = self._i18n
        data["tr"] = lambda key, **kwargs: self._i18n.t(key, lang=lang, **kwargs)

        return await handler(event, data)
