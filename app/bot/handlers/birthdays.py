from __future__ import annotations

from datetime import date

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.birthdays import birthdays_people_keyboard, birthdays_period_keyboard
from app.db.models import User
from app.services.i18n import I18nService
from app.services.people_service import PeopleService
from app.services.reminder_service import ReminderService, UpcomingBirthday

router = Router(name="birthdays")

BIRTHDAYS_MENU_TEXTS = {
    "Tug‘ilgan kunlar",
    "Дни рождения",
    "Birthdays",
}


@router.message(Command("birthdays"))
@router.message(F.text.in_(BIRTHDAYS_MENU_TEXTS))
async def birthdays_command(
    message: Message,
    session: AsyncSession,
    current_user: User,
    i18n: I18nService,
    lang: str,
) -> None:
    await message.answer(
        i18n.t("birthdays.menu", lang=lang),
        reply_markup=birthdays_period_keyboard(i18n=i18n, lang=lang),
    )

    await send_birthdays_for_period(
        target=message,
        session=session,
        user_id=current_user.id,
        i18n=i18n,
        lang=lang,
        mode="7",
    )


@router.callback_query(F.data == "birthdays:menu")
async def birthdays_menu_callback(
    callback: CallbackQuery,
    i18n: I18nService,
    lang: str,
) -> None:
    await callback.message.answer(
        i18n.t("birthdays.menu", lang=lang),
        reply_markup=birthdays_period_keyboard(i18n=i18n, lang=lang),
    )
    await callback.answer()


@router.callback_query(F.data.in_({"birthdays:today", "birthdays:tomorrow", "birthdays:7", "birthdays:30"}))
async def birthdays_period_callback(
    callback: CallbackQuery,
    session: AsyncSession,
    current_user: User,
    i18n: I18nService,
    lang: str,
) -> None:
    mode = callback.data.split(":", maxsplit=1)[1] if callback.data else "7"

    await send_birthdays_for_period(
        target=callback.message,
        session=session,
        user_id=current_user.id,
        i18n=i18n,
        lang=lang,
        mode=mode,
    )

    await callback.answer()


async def send_birthdays_for_period(
    target: Message,
    session: AsyncSession,
    user_id: int,
    i18n: I18nService,
    lang: str,
    mode: str,
) -> None:
    service = ReminderService(i18n=i18n)

    if mode == "today":
        items = await service.get_birthdays_for_exact_offset(
            session=session,
            user_id=user_id,
            offset_days=0,
        )
        title_key = "birthdays.today_title"
    elif mode == "tomorrow":
        items = await service.get_birthdays_for_exact_offset(
            session=session,
            user_id=user_id,
            offset_days=1,
        )
        title_key = "birthdays.tomorrow_title"
    elif mode == "30":
        items = await service.get_upcoming_birthdays(
            session=session,
            user_id=user_id,
            days_ahead=30,
        )
        title_key = "birthdays.upcoming_30_title"
    else:
        items = await service.get_upcoming_birthdays(
            session=session,
            user_id=user_id,
            days_ahead=7,
        )
        title_key = "birthdays.upcoming_title"

    if not items:
        await target.answer(
            "\n".join(
                [
                    i18n.t(title_key, lang=lang),
                    i18n.t("birthdays.empty", lang=lang),
                ],
            ),
            reply_markup=birthdays_period_keyboard(i18n=i18n, lang=lang),
        )
        return

    await target.answer(
        render_birthdays(
            items=items,
            title=i18n.t(title_key, lang=lang),
            i18n=i18n,
            lang=lang,
        ),
        reply_markup=birthdays_people_keyboard(
            items=items,
            i18n=i18n,
            lang=lang,
        ),
    )


def render_birthdays(
    items: list[UpcomingBirthday],
    title: str,
    i18n: I18nService,
    lang: str,
) -> str:
    people_service = PeopleService()
    rows = [title, ""]

    for item in items:
        birth_date_text = format_birth_date_for_line(item.birthday_date, lang=lang)

        if item.age is not None:
            rows.append(
                i18n.t(
                    "birthdays.item_with_age",
                    lang=lang,
                    full_name=people_service.format_full_name(item.person),
                    birth_date=birth_date_text,
                    age=item.age,
                    days_until=item.days_until,
                ),
            )
        else:
            rows.append(
                i18n.t(
                    "birthdays.item",
                    lang=lang,
                    full_name=people_service.format_full_name(item.person),
                    birth_date=birth_date_text,
                    days_until=item.days_until,
                ),
            )

    return "\n".join(rows)


def format_birth_date_for_line(value: date, lang: str) -> str:
    if lang == "en":
        return value.strftime("%Y-%m-%d")

    return value.strftime("%d.%m.%Y")