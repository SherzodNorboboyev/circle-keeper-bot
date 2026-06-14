from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.services.i18n import I18nService


router = Router(name="privacy")


@router.message(Command("delete_my_data"))
async def delete_my_data_disabled(
    message: Message,
    i18n: I18nService,
    lang: str,
) -> None:
    await message.answer(i18n.t("privacy.delete_my_data_coming_soon", lang=lang))