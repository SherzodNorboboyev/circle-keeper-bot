from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.main_menu import main_menu_keyboard
from app.bot.keyboards.settings import settings_keyboard
from app.bot.states.settings_states import SettingsStates
from app.db.models import User
from app.services.i18n import I18nService
from app.services.settings_service import SettingsService, SettingsValidationError

router = Router(name="settings")

SETTINGS_MENU_TEXTS = {
    "Sozlamalar",
    "Настройки",
    "Settings",
}

CANCEL_TEXTS = {
    "Bekor qilish",
    "Отмена",
    "Cancel",
}


@router.message(Command("settings"))
@router.message(F.text.in_(SETTINGS_MENU_TEXTS))
async def settings_command(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    current_user: User,
    i18n: I18nService,
    lang: str,
) -> None:
    await state.clear()
    await send_settings(
        message=message,
        session=session,
        user_id=current_user.id,
        i18n=i18n,
        lang=lang,
    )


@router.callback_query(F.data == "settings:timezone")
async def settings_timezone_callback(
    callback: CallbackQuery,
    state: FSMContext,
    i18n: I18nService,
    lang: str,
) -> None:
    await state.set_state(SettingsStates.timezone)
    await callback.message.answer(i18n.t("settings.ask_timezone", lang=lang))
    await callback.answer()


@router.callback_query(F.data == "settings:reminder_time")
async def settings_reminder_time_callback(
    callback: CallbackQuery,
    state: FSMContext,
    i18n: I18nService,
    lang: str,
) -> None:
    await state.set_state(SettingsStates.reminder_time)
    await callback.message.answer(i18n.t("settings.ask_reminder_time", lang=lang))
    await callback.answer()


@router.callback_query(F.data == "settings:days_before")
async def settings_days_before_callback(
    callback: CallbackQuery,
    state: FSMContext,
    i18n: I18nService,
    lang: str,
) -> None:
    await state.set_state(SettingsStates.days_before)
    await callback.message.answer(i18n.t("settings.ask_days_before", lang=lang))
    await callback.answer()


@router.callback_query(F.data == "settings:toggle_on_day")
async def settings_toggle_on_day_callback(
    callback: CallbackQuery,
    session: AsyncSession,
    current_user: User,
    i18n: I18nService,
    lang: str,
) -> None:
    service = SettingsService(session)
    effective = await service.get_effective_settings(user_id=current_user.id)
    new_value = not effective.birthday_on_day_enabled

    await service.update_birthday_on_day_enabled(
        user_id=current_user.id,
        enabled=new_value,
    )

    await callback.message.answer(i18n.t("settings.updated", lang=lang))
    await send_settings(
        message=callback.message,
        session=session,
        user_id=current_user.id,
        i18n=i18n,
        lang=lang,
    )
    await callback.answer()


@router.callback_query(F.data == "settings:language")
async def settings_language_callback(
    callback: CallbackQuery,
    i18n: I18nService,
    lang: str,
) -> None:
    await callback.message.answer(i18n.t("settings.language_hint", lang=lang))
    await callback.answer()


@router.message(SettingsStates.timezone)
async def settings_timezone_input(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    current_user: User,
    i18n: I18nService,
    lang: str,
) -> None:
    if message.text in CANCEL_TEXTS:
        await cancel_settings(message=message, state=state, i18n=i18n, lang=lang)
        return

    service = SettingsService(session)

    try:
        await service.update_timezone(
            user_id=current_user.id,
            timezone=message.text or "",
        )
    except SettingsValidationError as exc:
        await message.answer(i18n.t(exc.message_key, lang=lang))
        return

    await state.clear()
    await message.answer(
        i18n.t("settings.updated", lang=lang),
        reply_markup=main_menu_keyboard(i18n=i18n, lang=lang),
    )
    await send_settings(
        message=message,
        session=session,
        user_id=current_user.id,
        i18n=i18n,
        lang=lang,
    )


@router.message(SettingsStates.reminder_time)
async def settings_reminder_time_input(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    current_user: User,
    i18n: I18nService,
    lang: str,
) -> None:
    if message.text in CANCEL_TEXTS:
        await cancel_settings(message=message, state=state, i18n=i18n, lang=lang)
        return

    service = SettingsService(session)

    try:
        await service.update_reminder_time(
            user_id=current_user.id,
            reminder_time=message.text or "",
        )
    except SettingsValidationError as exc:
        await message.answer(i18n.t(exc.message_key, lang=lang))
        return

    await state.clear()
    await message.answer(
        i18n.t("settings.updated", lang=lang),
        reply_markup=main_menu_keyboard(i18n=i18n, lang=lang),
    )
    await send_settings(
        message=message,
        session=session,
        user_id=current_user.id,
        i18n=i18n,
        lang=lang,
    )


@router.message(SettingsStates.days_before)
async def settings_days_before_input(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    current_user: User,
    i18n: I18nService,
    lang: str,
) -> None:
    if message.text in CANCEL_TEXTS:
        await cancel_settings(message=message, state=state, i18n=i18n, lang=lang)
        return

    service = SettingsService(session)

    try:
        await service.update_days_before(
            user_id=current_user.id,
            days_before=message.text or "",
        )
    except SettingsValidationError as exc:
        await message.answer(i18n.t(exc.message_key, lang=lang))
        return

    await state.clear()
    await message.answer(
        i18n.t("settings.updated", lang=lang),
        reply_markup=main_menu_keyboard(i18n=i18n, lang=lang),
    )
    await send_settings(
        message=message,
        session=session,
        user_id=current_user.id,
        i18n=i18n,
        lang=lang,
    )


async def send_settings(
    message: Message,
    session: AsyncSession,
    user_id: int,
    i18n: I18nService,
    lang: str,
) -> None:
    service = SettingsService(session)
    effective = await service.get_effective_settings(user_id=user_id)

    await message.answer(
        i18n.t(
            "settings.title",
            lang=lang,
            timezone=effective.timezone,
            reminder_time=effective.reminder_time.strftime("%H:%M"),
            days_before=effective.birthday_days_before,
            birthday_on_day_enabled=i18n.t("common.yes", lang=lang)
            if effective.birthday_on_day_enabled
            else i18n.t("common.no", lang=lang),
        ),
        reply_markup=settings_keyboard(
            i18n=i18n,
            lang=lang,
            birthday_on_day_enabled=effective.birthday_on_day_enabled,
        ),
    )


async def cancel_settings(
    message: Message,
    state: FSMContext,
    i18n: I18nService,
    lang: str,
) -> None:
    await state.clear()
    await message.answer(
        i18n.t("error.cancelled", lang=lang),
        reply_markup=main_menu_keyboard(i18n=i18n, lang=lang),
    )