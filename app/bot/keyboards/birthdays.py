from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.services.i18n import I18nService
from app.services.people_service import PeopleService
from app.services.reminder_service import UpcomingBirthday


def birthdays_period_keyboard(i18n: I18nService, lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=i18n.t("birthdays.button.today", lang=lang),
                    callback_data="birthdays:today",
                ),
                InlineKeyboardButton(
                    text=i18n.t("birthdays.button.tomorrow", lang=lang),
                    callback_data="birthdays:tomorrow",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=i18n.t("birthdays.button.next_7", lang=lang),
                    callback_data="birthdays:7",
                ),
                InlineKeyboardButton(
                    text=i18n.t("birthdays.button.next_30", lang=lang),
                    callback_data="birthdays:30",
                ),
            ],
        ],
    )


def birthdays_people_keyboard(
    items: list[UpcomingBirthday],
    i18n: I18nService,
    lang: str,
) -> InlineKeyboardMarkup:
    people_service = PeopleService()
    rows: list[list[InlineKeyboardButton]] = []

    for item in items[:30]:
        rows.append(
            [
                InlineKeyboardButton(
                    text=people_service.format_full_name(item.person),
                    callback_data=f"people:view:{item.person.id}",
                ),
            ],
        )

    rows.append(
        [
            InlineKeyboardButton(
                text=i18n.t("birthdays.button.periods", lang=lang),
                callback_data="birthdays:menu",
            ),
        ],
    )

    return InlineKeyboardMarkup(inline_keyboard=rows)
