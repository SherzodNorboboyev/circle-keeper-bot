from __future__ import annotations

from collections.abc import Callable
from html import escape

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from app.bot.keyboards.inline import language_selection_keyboard
from app.bot.keyboards.main_menu import main_menu_keyboard
from app.db.models import User
from app.services.i18n import I18nService

router = Router(name="start")


@router.message(CommandStart())
async def command_start(
    message: Message,
    current_user: User,
    lang: str,
    i18n: I18nService,
    tr: Callable[..., str],
) -> None:
    if not current_user.language_code:
        await message.answer(
            tr("start.choose_language"),
            reply_markup=language_selection_keyboard(),
        )
        return

    first_name = escape(message.from_user.first_name if message.from_user else "")

    await message.answer(
        tr("start.welcome", first_name=first_name),
        reply_markup=main_menu_keyboard(i18n=i18n, lang=lang),
    )