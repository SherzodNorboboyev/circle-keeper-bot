from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.services.i18n import I18nService


def settings_keyboard(
    i18n: I18nService,
    lang: str,
    birthday_on_day_enabled: bool,
) -> InlineKeyboardMarkup:
    toggle_key = "settings.disable_on_day" if birthday_on_day_enabled else "settings.enable_on_day"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=i18n.t("settings.change_timezone", lang=lang),
                    callback_data="settings:timezone",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=i18n.t("settings.change_reminder_time", lang=lang),
                    callback_data="settings:reminder_time",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=i18n.t("settings.change_days_before", lang=lang),
                    callback_data="settings:days_before",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=i18n.t(toggle_key, lang=lang),
                    callback_data="settings:toggle_on_day",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=i18n.t("menu.change_language", lang=lang),
                    callback_data="settings:language",
                ),
            ],
        ],
    )