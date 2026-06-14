from __future__ import annotations

from collections.abc import Iterable
from math import ceil

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from app.db.models import GENDERS, PERSON_CATEGORIES, Person
from app.services.i18n import I18nService
from app.services.people_service import PeopleService


def optional_step_keyboard(
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
        one_time_keyboard=False,
    )


def first_step_keyboard(i18n: I18nService, lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=i18n.t("common.cancel", lang=lang)),
            ],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


def yes_no_keyboard(i18n: I18nService, lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=i18n.t("common.yes", lang=lang)),
                KeyboardButton(text=i18n.t("common.no", lang=lang)),
            ],
            [
                KeyboardButton(text=i18n.t("common.back", lang=lang)),
                KeyboardButton(text=i18n.t("common.cancel", lang=lang)),
            ],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


def category_keyboard(
    i18n: I18nService,
    lang: str,
    prefix: str = "person_category",
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    categories = list(PERSON_CATEGORIES)

    for index in range(0, len(categories), 2):
        row: list[InlineKeyboardButton] = []

        for category in categories[index : index + 2]:
            row.append(
                InlineKeyboardButton(
                    text=i18n.t(f"person.category.{category}", lang=lang),
                    callback_data=f"{prefix}:{category}",
                ),
            )

        rows.append(row)

    rows.append(
        [
            InlineKeyboardButton(
                text=i18n.t("common.back", lang=lang),
                callback_data=f"{prefix}:back",
            ),
            InlineKeyboardButton(
                text=i18n.t("common.cancel", lang=lang),
                callback_data=f"{prefix}:cancel",
            ),
        ],
    )

    return InlineKeyboardMarkup(inline_keyboard=rows)


def gender_keyboard(
    i18n: I18nService,
    lang: str,
    prefix: str = "person_gender",
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    for gender in GENDERS:
        rows.append(
            [
                InlineKeyboardButton(
                    text=i18n.t(f"person.gender.{gender}", lang=lang),
                    callback_data=f"{prefix}:{gender}",
                ),
            ],
        )

    rows.append(
        [
            InlineKeyboardButton(
                text=i18n.t("common.skip", lang=lang),
                callback_data=f"{prefix}:clear",
            ),
            InlineKeyboardButton(
                text=i18n.t("common.cancel", lang=lang),
                callback_data=f"{prefix}:cancel",
            ),
        ],
    )

    return InlineKeyboardMarkup(inline_keyboard=rows)


def person_list_keyboard(
    people: Iterable[Person],
    i18n: I18nService,
    lang: str,
    action: str,
    page: int,
    total_count: int,
    page_size: int = 10,
    page_action: str = "list",
) -> InlineKeyboardMarkup:
    service = PeopleService()
    rows: list[list[InlineKeyboardButton]] = []

    for person in people:
        rows.append(
            [
                InlineKeyboardButton(
                    text=service.format_full_name(person),
                    callback_data=f"people:{action}:{person.id}",
                ),
            ],
        )

    total_pages = max(1, ceil(total_count / page_size))

    pagination_row: list[InlineKeyboardButton] = []

    if page > 1:
        pagination_row.append(
            InlineKeyboardButton(
                text="⬅️",
                callback_data=f"people:{page_action}_page:{page - 1}",
            ),
        )

    pagination_row.append(
        InlineKeyboardButton(
            text=i18n.t("person.page", lang=lang, page=page, total_pages=total_pages),
            callback_data="people:noop",
        ),
    )

    if page < total_pages:
        pagination_row.append(
            InlineKeyboardButton(
                text="➡️",
                callback_data=f"people:{page_action}_page:{page + 1}",
            ),
        )

    if pagination_row:
        rows.append(pagination_row)

    return InlineKeyboardMarkup(inline_keyboard=rows)


def edit_field_keyboard(i18n: I18nService, lang: str) -> InlineKeyboardMarkup:
    fields = (
        "first_name",
        "last_name",
        "middle_name",
        "nickname",
        "phone",
        "telegram_username",
        "birth_date",
        "gender",
        "category",
        "custom_category",
        "note",
        "how_met",
        "location",
        "workplace",
        "education_place",
    )

    rows: list[list[InlineKeyboardButton]] = []

    for field_name in fields:
        rows.append(
            [
                InlineKeyboardButton(
                    text=i18n.t(f"person.field.{field_name}", lang=lang),
                    callback_data=f"person_edit_field:{field_name}",
                ),
            ],
        )

    rows.append(
        [
            InlineKeyboardButton(
                text=i18n.t("common.cancel", lang=lang),
                callback_data="person_edit:cancel",
            ),
        ],
    )

    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_keyboard(
    i18n: I18nService,
    lang: str,
    prefix: str,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=i18n.t("common.save", lang=lang),
                    callback_data=f"{prefix}:save",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=i18n.t("common.back", lang=lang),
                    callback_data=f"{prefix}:back",
                ),
                InlineKeyboardButton(
                    text=i18n.t("common.cancel", lang=lang),
                    callback_data=f"{prefix}:cancel",
                ),
            ],
        ],
    )


def delete_confirm_keyboard(i18n: I18nService, lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=i18n.t("common.yes", lang=lang),
                    callback_data="person_delete:confirm",
                ),
                InlineKeyboardButton(
                    text=i18n.t("common.no", lang=lang),
                    callback_data="person_delete:cancel",
                ),
            ],
        ],
    )


def profile_actions_keyboard(
    person_id: int,
    i18n: I18nService,
    lang: str,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=i18n.t("person.button.edit", lang=lang),
                    callback_data=f"people:edit:{person_id}",
                ),
                InlineKeyboardButton(
                    text=i18n.t("person.button.delete", lang=lang),
                    callback_data=f"people:delete:{person_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=i18n.t("person.button.add_relationship", lang=lang),
                    callback_data=f"people:relationship:{person_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=i18n.t("person.button.add_child", lang=lang),
                    callback_data=f"people:add_child:{person_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=i18n.t("common.back", lang=lang),
                    callback_data="people:list_page:1",
                ),
            ],
        ],
    )
