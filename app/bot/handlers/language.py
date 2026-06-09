from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.inline import language_selection_keyboard
from app.bot.keyboards.main_menu import main_menu_keyboard
from app.db.models import User
from app.db.repositories.users import UserRepository
from app.services.i18n import I18nService, SUPPORTED_LANGUAGES

router = Router(name="language")


@router.message(Command("language"))
async def command_language(message: Message, i18n: I18nService, lang: str) -> None:
    await message.answer(
        i18n.t("start.choose_language", lang=lang),
        reply_markup=language_selection_keyboard(),
    )


@router.callback_query(F.data.startswith("lang:"))
async def language_selected(
    callback: CallbackQuery,
    session: AsyncSession,
    current_user: User,
    i18n: I18nService,
) -> None:
    selected_language = callback.data.split(":", maxsplit=1)[1] if callback.data else ""

    if selected_language not in SUPPORTED_LANGUAGES:
        await callback.answer(
            i18n.t("error.required_field", lang=current_user.language_code or "uz"),
            show_alert=True,
        )
        return

    repository = UserRepository(session)
    await repository.set_language(user_id=current_user.id, language_code=selected_language)

    if callback.message:
        await callback.message.answer(
            i18n.t("language.changed", lang=selected_language),
            reply_markup=main_menu_keyboard(i18n=i18n, lang=selected_language),
        )

    await callback.answer()