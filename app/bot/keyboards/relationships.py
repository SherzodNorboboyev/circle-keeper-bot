from __future__ import annotations

from collections.abc import Iterable
from math import ceil

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.db.models import RELATIONSHIP_TYPES
from app.services.i18n import I18nService


def relationship_action_keyboard(i18n: I18nService, lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=i18n.t("relationship.button.create", lang=lang),
                    callback_data="relationship_action:create",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=i18n.t("relationship.button.list", lang=lang),
                    callback_data="relationship_action:list",
                ),
            ],
        ],
    )


def relationship_type_keyboard(
    i18n: I18nService,
    lang: str,
    prefix: str = "relationship_type",
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    relationship_types = list(RELATIONSHIP_TYPES)

    for index in range(0, len(relationship_types), 2):
        row: list[InlineKeyboardButton] = []

        for relationship_type in relationship_types[index : index + 2]:
            row.append(
                InlineKeyboardButton(
                    text=i18n.t(f"relationship.labels.{relationship_type}", lang=lang),
                    callback_data=f"{prefix}:{relationship_type}",
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


def relationship_direction_keyboard(i18n: I18nService, lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=i18n.t("relationship.direction.bidirectional", lang=lang),
                    callback_data="relationship_direction:bidirectional",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=i18n.t("relationship.direction.directed", lang=lang),
                    callback_data="relationship_direction:directed",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=i18n.t("common.back", lang=lang),
                    callback_data="relationship_direction:back",
                ),
                InlineKeyboardButton(
                    text=i18n.t("common.cancel", lang=lang),
                    callback_data="relationship_direction:cancel",
                ),
            ],
        ],
    )


def reverse_type_keyboard(i18n: I18nService, lang: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    for relationship_type in RELATIONSHIP_TYPES:
        rows.append(
            [
                InlineKeyboardButton(
                    text=i18n.t(f"relationship.labels.{relationship_type}", lang=lang),
                    callback_data=f"relationship_reverse:{relationship_type}",
                ),
            ],
        )

    rows.append(
        [
            InlineKeyboardButton(
                text=i18n.t("relationship.reverse.none", lang=lang),
                callback_data="relationship_reverse:none",
            ),
        ],
    )
    rows.append(
        [
            InlineKeyboardButton(
                text=i18n.t("common.back", lang=lang),
                callback_data="relationship_reverse:back",
            ),
            InlineKeyboardButton(
                text=i18n.t("common.cancel", lang=lang),
                callback_data="relationship_reverse:cancel",
            ),
        ],
    )

    return InlineKeyboardMarkup(inline_keyboard=rows)


def relationship_confirm_keyboard(i18n: I18nService, lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=i18n.t("common.save", lang=lang),
                    callback_data="relationship_confirm:save",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=i18n.t("common.back", lang=lang),
                    callback_data="relationship_confirm:back",
                ),
                InlineKeyboardButton(
                    text=i18n.t("common.cancel", lang=lang),
                    callback_data="relationship_confirm:cancel",
                ),
            ],
        ],
    )


def relationship_list_keyboard(
    items: Iterable[tuple[int, str]],
    i18n: I18nService,
    lang: str,
    page: int,
    total_count: int,
    page_size: int = 10,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    for relationship_id, label in items:
        rows.append(
            [
                InlineKeyboardButton(
                    text=label,
                    callback_data=f"relationship:view:{relationship_id}",
                ),
            ],
        )

    total_pages = max(1, ceil(total_count / page_size))

    pagination_row: list[InlineKeyboardButton] = []

    if page > 1:
        pagination_row.append(
            InlineKeyboardButton(
                text="⬅️",
                callback_data=f"relationship:list_page:{page - 1}",
            ),
        )

    pagination_row.append(
        InlineKeyboardButton(
            text=i18n.t("relationship.page", lang=lang, page=page, total_pages=total_pages),
            callback_data="relationship:noop",
        ),
    )

    if page < total_pages:
        pagination_row.append(
            InlineKeyboardButton(
                text="➡️",
                callback_data=f"relationship:list_page:{page + 1}",
            ),
        )

    rows.append(pagination_row)

    return InlineKeyboardMarkup(inline_keyboard=rows)


def relationship_view_actions_keyboard(
    relationship_id: int,
    i18n: I18nService,
    lang: str,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=i18n.t("relationship.button.delete", lang=lang),
                    callback_data=f"relationship:delete:{relationship_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=i18n.t("relationship.button.back_to_list", lang=lang),
                    callback_data="relationship_action:list",
                ),
            ],
        ],
    )


def relationship_delete_confirm_keyboard(
    relationship_id: int,
    i18n: I18nService,
    lang: str,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=i18n.t("common.yes", lang=lang),
                    callback_data=f"relationship_delete:confirm:{relationship_id}",
                ),
                InlineKeyboardButton(
                    text=i18n.t("common.no", lang=lang),
                    callback_data=f"relationship_delete:cancel:{relationship_id}",
                ),
            ],
        ],
    )
