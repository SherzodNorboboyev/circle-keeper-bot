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
    update = event.update
    message = getattr(update, "message", None)
    callback_query = getattr(update, "callback_query", None)

    telegram_user_id: int | None = None
    chat_id: int | None = None

    if isinstance(message, Message):
        telegram_user_id = message.from_user.id if message.from_user else None
        chat_id = message.chat.id if message.chat else None
    elif isinstance(callback_query, CallbackQuery):
        telegram_user_id = callback_query.from_user.id if callback_query.from_user else None
        if callback_query.message and hasattr(callback_query.message, "chat"):
            chat_id = callback_query.message.chat.id

    logger.exception(
        "unhandled_bot_error",
        update_id=update.update_id if update else None,
        telegram_user_id=telegram_user_id,
        chat_id=chat_id,
        exception_type=type(event.exception).__name__,
        exception_message=str(event.exception),
    )

    text = i18n.t("error.unexpected", lang=lang) if i18n else "Kutilmagan xatolik yuz berdi."

    if isinstance(message, Message):
        await message.answer(text)
        return True

    if isinstance(callback_query, CallbackQuery):
        await callback_query.answer(text, show_alert=True)

        if callback_query.message and hasattr(callback_query.message, "answer"):
            await callback_query.message.answer(text)

        return True

    return True
