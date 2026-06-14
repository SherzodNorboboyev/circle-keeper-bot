from __future__ import annotations

from aiogram import Router
from aiogram.types import CallbackQuery, ErrorEvent, Message
from loguru import logger

from app.services.i18n import I18nService


router = Router(name="errors")


@router.errors()
async def global_error_handler(
    event: ErrorEvent,
    i18n: I18nService | None = None,
    lang: str = "uz",
) -> bool:
    logger.exception(
        "unhandled_bot_error",
        update=event.update.model_dump(exclude_none=True) if event.update else None,
        exception=str(event.exception),
    )

    text = i18n.t("error.unexpected", lang=lang) if i18n else "Kutilmagan xatolik yuz berdi."

    message = getattr(event.update, "message", None)
    callback_query = getattr(event.update, "callback_query", None)

    if isinstance(message, Message):
        await message.answer(text)
        return True

    if isinstance(callback_query, CallbackQuery):
        await callback_query.answer(text, show_alert=True)

        if callback_query.message and hasattr(callback_query.message, "answer"):
            await callback_query.message.answer(text)

        return True

    return True