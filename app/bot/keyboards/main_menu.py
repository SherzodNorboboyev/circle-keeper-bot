from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from app.services.i18n import I18nService


def main_menu_keyboard(i18n: I18nService, lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=i18n.t("menu.add_person", lang=lang)),
                KeyboardButton(text=i18n.t("menu.list_people", lang=lang)),
            ],
            [
                KeyboardButton(text=i18n.t("menu.search", lang=lang)),
                KeyboardButton(text=i18n.t("menu.birthdays", lang=lang)),
            ],
            [
                KeyboardButton(text=i18n.t("menu.relationships", lang=lang)),
                KeyboardButton(text=i18n.t("menu.excel", lang=lang)),
            ],
            [
                KeyboardButton(text=i18n.t("menu.backup", lang=lang)),
                KeyboardButton(text=i18n.t("menu.settings", lang=lang)),
            ],
            [
                KeyboardButton(text=i18n.t("menu.change_language", lang=lang)),
            ],
        ],
        resize_keyboard=True,
        input_field_placeholder=i18n.t("help.text", lang=lang)[:64],
    )
