from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from app.db.models import GENDERS
from app.services.i18n import I18nService


def child_first_step_keyboard(i18n: I18nService, lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=i18n.t("common.cancel", lang=lang)),
            ],
        ],
        resize_keyboard=True,
    )


def child_optional_step_keyboard(
    i18n: I18nService,
    lang: str,
    allow_skip: bool = True,
    allow_back: bool = True,
) -> ReplyKeyboardMarkup:
    row: list[KeyboardButton] = []

    if allow_skip:
        row.append(KeyboardButton(text=i18n.t("common.skip", lang=lang)))

    if allow_back:
        row.append(KeyboardButton(text=i18n.t("common.back", lang=lang)))

    row.append(KeyboardButton(text=i18n.t("common.cancel", lang=lang)))

    return ReplyKeyboardMarkup(
        keyboard=[row],
        resize_keyboard=True,
    )


def child_gender_keyboard(i18n: I18nService, lang: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    for gender in GENDERS:
        rows.append(
            [
                InlineKeyboardButton(
                    text=i18n.t(f"person.gender.{gender}", lang=lang),
                    callback_data=f"child_gender:{gender}",
                ),
            ],
        )

    rows.append(
        [
            InlineKeyboardButton(
                text=i18n.t("common.skip", lang=lang),
                callback_data="child_gender:clear",
            ),
        ],
    )
    rows.append(
        [
            InlineKeyboardButton(
                text=i18n.t("common.back", lang=lang),
                callback_data="child_gender:back",
            ),
            InlineKeyboardButton(
                text=i18n.t("common.cancel", lang=lang),
                callback_data="child_gender:cancel",
            ),
        ],
    )

    return InlineKeyboardMarkup(inline_keyboard=rows)


def child_confirm_keyboard(i18n: I18nService, lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=i18n.t("common.save", lang=lang),
                    callback_data="child_confirm:save",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=i18n.t("common.back", lang=lang),
                    callback_data="child_confirm:back",
                ),
                InlineKeyboardButton(
                    text=i18n.t("common.cancel", lang=lang),
                    callback_data="child_confirm:cancel",
                ),
            ],
        ],
    )