from __future__ import annotations

from math import ceil
from typing import Any

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.children import (
    child_confirm_keyboard,
    child_first_step_keyboard,
    child_gender_keyboard,
    child_optional_step_keyboard,
)
from app.bot.keyboards.main_menu import main_menu_keyboard
from app.bot.keyboards.people import person_list_keyboard
from app.bot.states.child_states import AddChildStates
from app.db.models import User
from app.db.repositories.people import PeopleRepository
from app.services.child_service import ChildService
from app.services.i18n import I18nService
from app.services.people_service import PeopleService, PeopleValidationError
from app.services.relationship_service import RelationshipValidationError

router = Router(name="children")

PAGE_SIZE = 10

SKIP_TEXTS = {
    "O‘tkazib yuborish",
    "Пропустить",
    "Skip",
}

BACK_TEXTS = {
    "Ortga",
    "Назад",
    "Back",
}

CANCEL_TEXTS = {
    "Bekor qilish",
    "Отмена",
    "Cancel",
}


@router.message(Command("add_child"))
async def add_child_command(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    current_user: User,
    i18n: I18nService,
    lang: str,
) -> None:
    await state.clear()
    await state.set_state(AddChildStates.select_parent)

    await send_parent_selection(
        target=message,
        session=session,
        user_id=current_user.id,
        i18n=i18n,
        lang=lang,
        page=1,
    )


@router.callback_query(F.data.startswith("people:add_child:"))
async def add_child_from_profile(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    current_user: User,
    i18n: I18nService,
    lang: str,
) -> None:
    parent_person_id = parse_id(callback.data)

    people_repository = PeopleRepository(session)
    parent = await people_repository.get_person_by_id(
        user_id=current_user.id,
        person_id=parent_person_id,
    )

    if parent is None:
        await callback.message.answer(i18n.t("relationship.person_not_found", lang=lang))
        await callback.answer()
        return

    await state.clear()
    await state.update_data(parent_person_id=parent.id)
    await state.set_state(AddChildStates.first_name)

    await callback.message.answer(
        i18n.t(
            "child.selected_parent",
            lang=lang,
            full_name=PeopleService().format_full_name(parent),
        ),
    )
    await callback.message.answer(
        i18n.t("child.ask_first_name", lang=lang),
        reply_markup=child_first_step_keyboard(i18n=i18n, lang=lang),
    )

    await callback.answer()


@router.callback_query(StateFilter(AddChildStates.select_parent), F.data.startswith("people:child_parent_page:"))
async def add_child_parent_page(
    callback: CallbackQuery,
    session: AsyncSession,
    current_user: User,
    i18n: I18nService,
    lang: str,
) -> None:
    page = parse_page(callback.data)

    await edit_parent_selection(
        callback=callback,
        session=session,
        user_id=current_user.id,
        i18n=i18n,
        lang=lang,
        page=page,
    )


@router.callback_query(StateFilter(AddChildStates.select_parent), F.data.startswith("people:child_parent:"))
async def add_child_parent_selected(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    current_user: User,
    i18n: I18nService,
    lang: str,
) -> None:
    parent_person_id = parse_id(callback.data)

    people_repository = PeopleRepository(session)
    parent = await people_repository.get_person_by_id(
        user_id=current_user.id,
        person_id=parent_person_id,
    )

    if parent is None:
        await callback.message.answer(i18n.t("relationship.person_not_found", lang=lang))
        await callback.answer()
        return

    await state.update_data(parent_person_id=parent.id)
    await state.set_state(AddChildStates.first_name)

    await callback.message.answer(
        i18n.t(
            "child.selected_parent",
            lang=lang,
            full_name=PeopleService().format_full_name(parent),
        ),
    )
    await callback.message.answer(
        i18n.t("child.ask_first_name", lang=lang),
        reply_markup=child_first_step_keyboard(i18n=i18n, lang=lang),
    )

    await callback.answer()


@router.message(AddChildStates.first_name)
async def add_child_first_name(
    message: Message,
    state: FSMContext,
    i18n: I18nService,
    lang: str,
) -> None:
    value = (message.text or "").strip()

    if value in CANCEL_TEXTS:
        await cancel_child_flow_message(message=message, state=state, i18n=i18n, lang=lang)
        return

    if not value:
        await message.answer(i18n.t("error.required_field", lang=lang))
        return

    await state.update_data(first_name=value)
    await state.set_state(AddChildStates.last_name)

    await message.answer(
        i18n.t("child.ask_last_name", lang=lang),
        reply_markup=child_optional_step_keyboard(i18n=i18n, lang=lang),
    )


@router.message(AddChildStates.last_name)
async def add_child_last_name(
    message: Message,
    state: FSMContext,
    i18n: I18nService,
    lang: str,
) -> None:
    if message.text in CANCEL_TEXTS:
        await cancel_child_flow_message(message=message, state=state, i18n=i18n, lang=lang)
        return

    if message.text in BACK_TEXTS:
        await state.set_state(AddChildStates.first_name)
        await message.answer(
            i18n.t("child.ask_first_name", lang=lang),
            reply_markup=child_first_step_keyboard(i18n=i18n, lang=lang),
        )
        return

    await state.update_data(last_name=optional_text(message.text))
    await state.set_state(AddChildStates.birth_date)

    await message.answer(
        i18n.t("child.ask_birth_date", lang=lang),
        reply_markup=child_optional_step_keyboard(i18n=i18n, lang=lang),
    )


@router.message(AddChildStates.birth_date)
async def add_child_birth_date(
    message: Message,
    state: FSMContext,
    i18n: I18nService,
    lang: str,
) -> None:
    if message.text in CANCEL_TEXTS:
        await cancel_child_flow_message(message=message, state=state, i18n=i18n, lang=lang)
        return

    if message.text in BACK_TEXTS:
        await state.set_state(AddChildStates.last_name)
        await message.answer(
            i18n.t("child.ask_last_name", lang=lang),
            reply_markup=child_optional_step_keyboard(i18n=i18n, lang=lang),
        )
        return

    value = optional_text(message.text)
    service = PeopleService()

    if value is not None:
        try:
            service.parse_birth_date(value)
        except PeopleValidationError as exc:
            await message.answer(i18n.t(exc.message_key, lang=lang))
            return

    await state.update_data(birth_date=value)
    await state.set_state(AddChildStates.gender)

    await message.answer(
        i18n.t("child.ask_gender", lang=lang),
        reply_markup=ReplyKeyboardRemove(),
    )
    await message.answer(
        i18n.t("child.ask_gender", lang=lang),
        reply_markup=child_gender_keyboard(i18n=i18n, lang=lang),
    )


@router.callback_query(StateFilter(AddChildStates.gender), F.data.startswith("child_gender:"))
async def add_child_gender(
    callback: CallbackQuery,
    state: FSMContext,
    i18n: I18nService,
    lang: str,
) -> None:
    gender = callback.data.split(":", maxsplit=1)[1] if callback.data else ""

    if gender == "cancel":
        await cancel_child_flow_callback(callback=callback, state=state, i18n=i18n, lang=lang)
        return

    if gender == "back":
        await state.set_state(AddChildStates.birth_date)
        await callback.message.answer(
            i18n.t("child.ask_birth_date", lang=lang),
            reply_markup=child_optional_step_keyboard(i18n=i18n, lang=lang),
        )
        await callback.answer()
        return

    await state.update_data(gender=None if gender == "clear" else gender)
    await state.set_state(AddChildStates.note)

    await callback.message.answer(
        i18n.t("child.ask_note", lang=lang),
        reply_markup=child_optional_step_keyboard(i18n=i18n, lang=lang),
    )
    await callback.answer()


@router.message(AddChildStates.note)
async def add_child_note(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    current_user: User,
    i18n: I18nService,
    lang: str,
) -> None:
    if message.text in CANCEL_TEXTS:
        await cancel_child_flow_message(message=message, state=state, i18n=i18n, lang=lang)
        return

    if message.text in BACK_TEXTS:
        await state.set_state(AddChildStates.gender)
        await message.answer(
            i18n.t("child.ask_gender", lang=lang),
            reply_markup=child_gender_keyboard(i18n=i18n, lang=lang),
        )
        return

    await state.update_data(note=optional_text(message.text))
    await show_child_preview(
        message=message,
        state=state,
        session=session,
        current_user=current_user,
        i18n=i18n,
        lang=lang,
    )


@router.callback_query(StateFilter(AddChildStates.confirm), F.data == "child_confirm:save")
async def add_child_confirm_save(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    current_user: User,
    i18n: I18nService,
    lang: str,
) -> None:
    data = await state.get_data()
    service = ChildService()

    try:
        result = await service.create_child_for_parent(
            session=session,
            user_id=current_user.id,
            parent_person_id=int(data["parent_person_id"]),
            child_data={
                "first_name": data.get("first_name"),
                "last_name": data.get("last_name"),
                "birth_date": data.get("birth_date"),
                "gender": data.get("gender"),
                "note": data.get("note"),
            },
        )
    except (RelationshipValidationError, PeopleValidationError) as exc:
        await callback.message.answer(i18n.t(exc.message_key, lang=lang))
        await callback.answer()
        return

    await state.clear()

    people_service = PeopleService()

    await callback.message.answer(
        i18n.t(
            "child.created",
            lang=lang,
            child_full_name=people_service.format_full_name(result.child),
            parent_full_name=people_service.format_full_name(result.parent),
        ),
        reply_markup=main_menu_keyboard(i18n=i18n, lang=lang),
    )

    await callback.answer()


@router.callback_query(StateFilter(AddChildStates.confirm), F.data == "child_confirm:back")
async def add_child_confirm_back(
    callback: CallbackQuery,
    state: FSMContext,
    i18n: I18nService,
    lang: str,
) -> None:
    await state.set_state(AddChildStates.note)

    await callback.message.answer(
        i18n.t("child.ask_note", lang=lang),
        reply_markup=child_optional_step_keyboard(i18n=i18n, lang=lang),
    )
    await callback.answer()


@router.callback_query(StateFilter(AddChildStates.confirm), F.data == "child_confirm:cancel")
async def add_child_confirm_cancel(
    callback: CallbackQuery,
    state: FSMContext,
    i18n: I18nService,
    lang: str,
) -> None:
    await cancel_child_flow_callback(callback=callback, state=state, i18n=i18n, lang=lang)


async def send_parent_selection(
    target: Message,
    session: AsyncSession,
    user_id: int,
    i18n: I18nService,
    lang: str,
    page: int,
) -> None:
    repository = PeopleRepository(session)
    total_count = await repository.count_people(user_id=user_id)

    if total_count == 0:
        await target.answer(
            i18n.t("person.list_empty", lang=lang),
            reply_markup=main_menu_keyboard(i18n=i18n, lang=lang),
        )
        return

    people = await repository.list_people(
        user_id=user_id,
        page=page,
        page_size=PAGE_SIZE,
    )

    await target.answer(
        build_parent_selection_text(
            i18n=i18n,
            lang=lang,
            page=page,
            total_count=total_count,
        ),
        reply_markup=person_list_keyboard(
            people=people,
            i18n=i18n,
            lang=lang,
            action="child_parent",
            page=page,
            total_count=total_count,
            page_size=PAGE_SIZE,
            page_action="child_parent",
        ),
    )


async def edit_parent_selection(
    callback: CallbackQuery,
    session: AsyncSession,
    user_id: int,
    i18n: I18nService,
    lang: str,
    page: int,
) -> None:
    repository = PeopleRepository(session)
    total_count = await repository.count_people(user_id=user_id)

    if total_count == 0:
        await callback.message.edit_text(i18n.t("person.list_empty", lang=lang))
        await callback.answer()
        return

    total_pages = max(1, ceil(total_count / PAGE_SIZE))
    page = min(max(1, page), total_pages)

    people = await repository.list_people(
        user_id=user_id,
        page=page,
        page_size=PAGE_SIZE,
    )

    await callback.message.edit_text(
        build_parent_selection_text(
            i18n=i18n,
            lang=lang,
            page=page,
            total_count=total_count,
        ),
        reply_markup=person_list_keyboard(
            people=people,
            i18n=i18n,
            lang=lang,
            action="child_parent",
            page=page,
            total_count=total_count,
            page_size=PAGE_SIZE,
            page_action="child_parent",
        ),
    )
    await callback.answer()


async def show_child_preview(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    current_user: User,
    i18n: I18nService,
    lang: str,
) -> None:
    data = await state.get_data()
    people_repository = PeopleRepository(session)
    people_service = PeopleService()

    parent = await people_repository.get_person_by_id(
        user_id=current_user.id,
        person_id=int(data["parent_person_id"]),
    )

    if parent is None:
        await message.answer(i18n.t("relationship.person_not_found", lang=lang))
        return

    preview_data = people_service.prepare_create_data(
        {
            "first_name": data.get("first_name"),
            "last_name": data.get("last_name"),
            "birth_date": data.get("birth_date"),
            "gender": data.get("gender"),
            "note": data.get("note"),
            "category": "child",
        },
    )

    await state.set_state(AddChildStates.confirm)

    await message.answer(
        render_child_preview(
            parent_full_name=people_service.format_full_name(parent),
            data=preview_data,
            i18n=i18n,
            lang=lang,
            people_service=people_service,
        ),
        reply_markup=child_confirm_keyboard(i18n=i18n, lang=lang),
    )


def render_child_preview(
    parent_full_name: str,
    data: dict[str, Any],
    i18n: I18nService,
    lang: str,
    people_service: PeopleService,
) -> str:
    return i18n.t(
        "child.preview",
        lang=lang,
        parent_full_name=parent_full_name,
        first_name=data.get("first_name") or "—",
        last_name=data.get("last_name") or "—",
        birth_date=people_service.format_birth_date(data, lang=lang),
        gender=i18n.t(f"person.gender.{data['gender']}", lang=lang) if data.get("gender") else "—",
        note=data.get("note") or "—",
    )


def build_parent_selection_text(
    i18n: I18nService,
    lang: str,
    page: int,
    total_count: int,
) -> str:
    total_pages = max(1, ceil(total_count / PAGE_SIZE))

    return "\n".join(
        [
            i18n.t("child.select_parent", lang=lang),
            i18n.t("person.count", lang=lang, count=total_count),
            i18n.t("person.page", lang=lang, page=page, total_pages=total_pages),
        ],
    )


async def cancel_child_flow_message(
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


async def cancel_child_flow_callback(
    callback: CallbackQuery,
    state: FSMContext,
    i18n: I18nService,
    lang: str,
) -> None:
    await state.clear()

    await callback.message.answer(
        i18n.t("error.cancelled", lang=lang),
        reply_markup=main_menu_keyboard(i18n=i18n, lang=lang),
    )
    await callback.answer()


def optional_text(value: str | None) -> str | None:
    if value is None:
        return None

    cleaned = value.strip()

    if not cleaned or cleaned in SKIP_TEXTS:
        return None

    return cleaned


def parse_id(callback_data: str | None) -> int:
    if not callback_data:
        raise ValueError("Callback data is empty.")

    return int(callback_data.rsplit(":", maxsplit=1)[1])


def parse_page(callback_data: str | None, default: int = 1) -> int:
    if not callback_data:
        return default

    try:
        return max(1, int(callback_data.rsplit(":", maxsplit=1)[1]))
    except ValueError:
        return default
