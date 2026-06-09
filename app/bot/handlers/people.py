from __future__ import annotations

from math import ceil
from typing import Any

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.main_menu import main_menu_keyboard
from app.bot.keyboards.people import (
    category_keyboard,
    confirm_keyboard,
    delete_confirm_keyboard,
    edit_field_keyboard,
    first_step_keyboard,
    gender_keyboard,
    optional_step_keyboard,
    person_list_keyboard,
    profile_actions_keyboard,
    yes_no_keyboard,
)
from app.bot.states.people_states import (
    AddPersonStates,
    DeletePersonStates,
    EditPersonStates,
    SearchPersonStates,
)
from app.db.models import Person, User
from app.db.repositories.people import PeopleRepository
from app.services.audit_service import AuditService
from app.services.backup_trigger import BackupTriggerService
from app.services.i18n import I18nService
from app.services.people_service import PeopleService, PeopleValidationError

router = Router(name="people")

PAGE_SIZE = 10

ADD_MENU_TEXTS = {
    "Odam qo‘shish",
    "Добавить человека",
    "Add person",
}

LIST_MENU_TEXTS = {
    "Odamlarni ko‘rish",
    "Список людей",
    "People list",
}

SEARCH_MENU_TEXTS = {
    "Qidirish",
    "Поиск",
    "Search",
}

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

YES_TEXTS = {
    "Ha",
    "Да",
    "Yes",
}

NO_TEXTS = {
    "Yo‘q",
    "Нет",
    "No",
}

ADD_BACK_TRANSITIONS: dict[str, tuple[Any, str, bool]] = {
    AddPersonStates.last_name.state: (AddPersonStates.first_name, "person.ask_first_name", False),
    AddPersonStates.middle_name.state: (AddPersonStates.last_name, "person.ask_last_name", True),
    AddPersonStates.phone.state: (AddPersonStates.middle_name, "person.ask_middle_name", True),
    AddPersonStates.telegram_username.state: (AddPersonStates.phone, "person.ask_phone", True),
    AddPersonStates.birth_date.state: (AddPersonStates.telegram_username, "person.ask_telegram_username", True),
    AddPersonStates.note.state: (AddPersonStates.category, "person.ask_category", True),
    AddPersonStates.relationship_offer.state: (AddPersonStates.note, "person.ask_note", True),
    AddPersonStates.confirm.state: (AddPersonStates.relationship_offer, "person.ask_relationship_offer", False),
}


@router.message(Command("cancel"))
@router.message(F.text.in_(CANCEL_TEXTS))
async def cancel_flow(
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


@router.callback_query(F.data == "people:noop")
async def people_noop(callback: CallbackQuery) -> None:
    await callback.answer()


@router.message(Command("add"))
@router.message(F.text.in_(ADD_MENU_TEXTS))
async def add_person_start(
    message: Message,
    state: FSMContext,
    i18n: I18nService,
    lang: str,
) -> None:
    await state.clear()
    await state.set_state(AddPersonStates.first_name)

    await message.answer(
        i18n.t("person.ask_first_name", lang=lang),
        reply_markup=first_step_keyboard(i18n=i18n, lang=lang),
    )


@router.message(StateFilter(AddPersonStates.last_name, AddPersonStates.middle_name, AddPersonStates.phone, AddPersonStates.telegram_username, AddPersonStates.birth_date, AddPersonStates.note, AddPersonStates.relationship_offer, AddPersonStates.confirm), F.text.in_(BACK_TEXTS))
async def add_person_back(
    message: Message,
    state: FSMContext,
    i18n: I18nService,
    lang: str,
) -> None:
    current_state = await state.get_state()
    transition = ADD_BACK_TRANSITIONS.get(current_state)

    if transition is None:
        await message.answer(
            i18n.t("person.ask_first_name", lang=lang),
            reply_markup=first_step_keyboard(i18n=i18n, lang=lang),
        )
        await state.set_state(AddPersonStates.first_name)
        return

    previous_state, message_key, allow_skip = transition
    await state.set_state(previous_state)

    if previous_state == AddPersonStates.category:
        await message.answer(
            i18n.t(message_key, lang=lang),
            reply_markup=ReplyKeyboardRemove(),
        )
        await message.answer(
            i18n.t("person.ask_category", lang=lang),
            reply_markup=category_keyboard(i18n=i18n, lang=lang),
        )
        return

    if previous_state == AddPersonStates.relationship_offer:
        keyboard = yes_no_keyboard(i18n=i18n, lang=lang)
    elif allow_skip:
        keyboard = optional_step_keyboard(i18n=i18n, lang=lang)
    else:
        keyboard = first_step_keyboard(i18n=i18n, lang=lang)

    await message.answer(
        i18n.t(message_key, lang=lang),
        reply_markup=keyboard,
    )


@router.message(AddPersonStates.first_name)
async def add_person_first_name(
    message: Message,
    state: FSMContext,
    i18n: I18nService,
    lang: str,
) -> None:
    value = (message.text or "").strip()

    if not value:
        await message.answer(i18n.t("error.required_field", lang=lang))
        return

    await state.update_data(first_name=value)
    await state.set_state(AddPersonStates.last_name)

    await message.answer(
        i18n.t("person.ask_last_name", lang=lang),
        reply_markup=optional_step_keyboard(i18n=i18n, lang=lang),
    )


@router.message(AddPersonStates.last_name)
async def add_person_last_name(
    message: Message,
    state: FSMContext,
    i18n: I18nService,
    lang: str,
) -> None:
    await state.update_data(last_name=optional_text(message.text))
    await state.set_state(AddPersonStates.middle_name)

    await message.answer(
        i18n.t("person.ask_middle_name", lang=lang),
        reply_markup=optional_step_keyboard(i18n=i18n, lang=lang),
    )


@router.message(AddPersonStates.middle_name)
async def add_person_middle_name(
    message: Message,
    state: FSMContext,
    i18n: I18nService,
    lang: str,
) -> None:
    await state.update_data(middle_name=optional_text(message.text))
    await state.set_state(AddPersonStates.phone)

    await message.answer(
        i18n.t("person.ask_phone", lang=lang),
        reply_markup=optional_step_keyboard(i18n=i18n, lang=lang),
    )


@router.message(AddPersonStates.phone)
async def add_person_phone(
    message: Message,
    state: FSMContext,
    i18n: I18nService,
    lang: str,
) -> None:
    await state.update_data(phone=optional_text(message.text))
    await state.set_state(AddPersonStates.telegram_username)

    await message.answer(
        i18n.t("person.ask_telegram_username", lang=lang),
        reply_markup=optional_step_keyboard(i18n=i18n, lang=lang),
    )


@router.message(AddPersonStates.telegram_username)
async def add_person_telegram_username(
    message: Message,
    state: FSMContext,
    i18n: I18nService,
    lang: str,
) -> None:
    await state.update_data(telegram_username=optional_text(message.text))
    await state.set_state(AddPersonStates.birth_date)

    await message.answer(
        i18n.t("person.ask_birth_date", lang=lang),
        reply_markup=optional_step_keyboard(i18n=i18n, lang=lang),
    )


@router.message(AddPersonStates.birth_date)
async def add_person_birth_date(
    message: Message,
    state: FSMContext,
    i18n: I18nService,
    lang: str,
) -> None:
    service = PeopleService()
    value = optional_text(message.text)

    if value is not None:
        try:
            service.parse_birth_date(value)
        except PeopleValidationError as exc:
            await message.answer(i18n.t(exc.message_key, lang=lang))
            return

    await state.update_data(birth_date=value)
    await state.set_state(AddPersonStates.category)

    await message.answer(
        i18n.t("person.ask_category", lang=lang),
        reply_markup=ReplyKeyboardRemove(),
    )
    await message.answer(
        i18n.t("person.ask_category", lang=lang),
        reply_markup=category_keyboard(i18n=i18n, lang=lang),
    )


@router.callback_query(StateFilter(AddPersonStates.category), F.data.startswith("person_category:"))
async def add_person_category(
    callback: CallbackQuery,
    state: FSMContext,
    i18n: I18nService,
    lang: str,
) -> None:
    category = callback.data.split(":", maxsplit=1)[1] if callback.data else ""

    if category == "cancel":
        await state.clear()
        await callback.message.answer(
            i18n.t("error.cancelled", lang=lang),
            reply_markup=main_menu_keyboard(i18n=i18n, lang=lang),
        )
        await callback.answer()
        return

    if category == "back":
        await state.set_state(AddPersonStates.birth_date)
        await callback.message.answer(
            i18n.t("person.ask_birth_date", lang=lang),
            reply_markup=optional_step_keyboard(i18n=i18n, lang=lang),
        )
        await callback.answer()
        return

    if category == "custom":
        await state.update_data(category=category)
        await state.set_state(AddPersonStates.custom_category)

        await callback.message.answer(
            i18n.t("person.ask_custom_category", lang=lang),
            reply_markup=optional_step_keyboard(
                i18n=i18n,
                lang=lang,
                allow_skip=False,
                allow_back=True,
            ),
        )
        await callback.answer()
        return

    await state.update_data(category=category, custom_category=None)
    await state.set_state(AddPersonStates.note)

    await callback.message.answer(
        i18n.t("person.ask_note", lang=lang),
        reply_markup=optional_step_keyboard(i18n=i18n, lang=lang),
    )
    await callback.answer()


@router.message(AddPersonStates.custom_category)
async def add_person_custom_category(
    message: Message,
    state: FSMContext,
    i18n: I18nService,
    lang: str,
) -> None:
    value = (message.text or "").strip()

    if value in BACK_TEXTS:
        await state.set_state(AddPersonStates.category)
        await message.answer(
            i18n.t("person.ask_category", lang=lang),
            reply_markup=ReplyKeyboardRemove(),
        )
        await message.answer(
            i18n.t("person.ask_category", lang=lang),
            reply_markup=category_keyboard(i18n=i18n, lang=lang),
        )
        return

    if not value:
        await message.answer(i18n.t("person.custom_category_required", lang=lang))
        return

    await state.update_data(custom_category=value)
    await state.set_state(AddPersonStates.note)

    await message.answer(
        i18n.t("person.ask_note", lang=lang),
        reply_markup=optional_step_keyboard(i18n=i18n, lang=lang),
    )


@router.message(AddPersonStates.note)
async def add_person_note(
    message: Message,
    state: FSMContext,
    i18n: I18nService,
    lang: str,
) -> None:
    await state.update_data(note=optional_text(message.text))
    await state.set_state(AddPersonStates.relationship_offer)

    await message.answer(
        i18n.t("person.ask_relationship_offer", lang=lang),
        reply_markup=yes_no_keyboard(i18n=i18n, lang=lang),
    )


@router.message(AddPersonStates.relationship_offer)
async def add_person_relationship_offer(
    message: Message,
    state: FSMContext,
    i18n: I18nService,
    lang: str,
) -> None:
    text = (message.text or "").strip()

    if text in YES_TEXTS:
        await state.update_data(relationship_offer=True)
    elif text in NO_TEXTS:
        await state.update_data(relationship_offer=False)
    else:
        await message.answer(
            i18n.t("person.choose_yes_no", lang=lang),
            reply_markup=yes_no_keyboard(i18n=i18n, lang=lang),
        )
        return

    data = await state.get_data()
    service = PeopleService()

    try:
        prepared_data = service.prepare_create_data(data)
    except PeopleValidationError as exc:
        await message.answer(i18n.t(exc.message_key, lang=lang))
        return

    await state.set_state(AddPersonStates.confirm)

    await message.answer(
        i18n.t(
            "person.preview",
            lang=lang,
            preview=render_person_preview(
                data=prepared_data,
                i18n=i18n,
                lang=lang,
                service=service,
            ),
        ),
        reply_markup=confirm_keyboard(i18n=i18n, lang=lang, prefix="person_add"),
    )


@router.callback_query(StateFilter(AddPersonStates.confirm), F.data == "person_add:save")
async def add_person_save(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    current_user: User,
    i18n: I18nService,
    lang: str,
) -> None:
    data = await state.get_data()
    service = PeopleService()

    try:
        prepared_data = service.prepare_create_data(data)
    except PeopleValidationError as exc:
        await callback.message.answer(i18n.t(exc.message_key, lang=lang))
        await callback.answer()
        return

    repository = PeopleRepository(session)
    person = await repository.create_person(
        user_id=current_user.id,
        data=prepared_data,
    )

    audit_service = AuditService(session)
    await audit_service.log_person_created(
        user_id=current_user.id,
        person_id=person.id,
        new_value=service.person_to_dict(person),
    )

    backup_trigger = BackupTriggerService()
    await backup_trigger.trigger_user_backup(
        user_id=current_user.id,
        reason="person.created",
        metadata={"person_id": person.id},
    )

    await state.clear()

    await callback.message.answer(
        i18n.t("person.saved", lang=lang),
        reply_markup=main_menu_keyboard(i18n=i18n, lang=lang),
    )

    if data.get("relationship_offer"):
        await callback.message.answer(i18n.t("person.relationship_offer_after_save", lang=lang))

    await callback.answer()


@router.callback_query(StateFilter(AddPersonStates.confirm), F.data == "person_add:back")
async def add_person_confirm_back(
    callback: CallbackQuery,
    state: FSMContext,
    i18n: I18nService,
    lang: str,
) -> None:
    await state.set_state(AddPersonStates.relationship_offer)

    await callback.message.answer(
        i18n.t("person.ask_relationship_offer", lang=lang),
        reply_markup=yes_no_keyboard(i18n=i18n, lang=lang),
    )
    await callback.answer()


@router.callback_query(StateFilter(AddPersonStates.confirm), F.data == "person_add:cancel")
async def add_person_confirm_cancel(
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


@router.message(Command("list"))
@router.message(F.text.in_(LIST_MENU_TEXTS))
async def list_people_command(
    message: Message,
    session: AsyncSession,
    current_user: User,
    i18n: I18nService,
    lang: str,
) -> None:
    await send_people_list(
        target=message,
        session=session,
        user_id=current_user.id,
        i18n=i18n,
        lang=lang,
        page=1,
        action="view",
        page_action="list",
    )


@router.callback_query(F.data.startswith("people:list_page:"))
async def list_people_page(
    callback: CallbackQuery,
    session: AsyncSession,
    current_user: User,
    i18n: I18nService,
    lang: str,
) -> None:
    page = parse_page(callback.data, default=1)

    await edit_people_list(
        callback=callback,
        session=session,
        user_id=current_user.id,
        i18n=i18n,
        lang=lang,
        page=page,
        action="view",
        page_action="list",
    )


@router.message(Command("view"))
async def view_person_command(
    message: Message,
    session: AsyncSession,
    current_user: User,
    i18n: I18nService,
    lang: str,
) -> None:
    await send_people_list(
        target=message,
        session=session,
        user_id=current_user.id,
        i18n=i18n,
        lang=lang,
        page=1,
        action="view",
        page_action="list",
        title_key="person.select_to_view",
    )


@router.callback_query(F.data.startswith("people:view:"))
async def view_person_callback(
    callback: CallbackQuery,
    session: AsyncSession,
    current_user: User,
    i18n: I18nService,
    lang: str,
) -> None:
    person_id = parse_id(callback.data)
    repository = PeopleRepository(session)
    person = await repository.get_person_by_id(
        user_id=current_user.id,
        person_id=person_id,
    )

    if person is None:
        await callback.message.answer(i18n.t("person.not_found", lang=lang))
        await callback.answer()
        return

    service = PeopleService()

    await callback.message.edit_text(
        render_person_profile(
            person=person,
            i18n=i18n,
            lang=lang,
            service=service,
        ),
        reply_markup=profile_actions_keyboard(
            person_id=person.id,
            i18n=i18n,
            lang=lang,
        ),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("people:relationship:"))
async def relationship_hook_callback(
    callback: CallbackQuery,
    i18n: I18nService,
    lang: str,
) -> None:
    await callback.message.answer(i18n.t("person.relationships_placeholder", lang=lang))
    await callback.answer()


@router.callback_query(F.data.startswith("people:add_child:"))
async def add_child_hook_callback(
    callback: CallbackQuery,
    i18n: I18nService,
    lang: str,
) -> None:
    await callback.message.answer(i18n.t("person.add_child_placeholder", lang=lang))
    await callback.answer()


@router.message(Command("search"))
@router.message(F.text.in_(SEARCH_MENU_TEXTS))
async def search_people_command(
    message: Message,
    state: FSMContext,
    i18n: I18nService,
    lang: str,
) -> None:
    await state.clear()
    await state.set_state(SearchPersonStates.query)

    await message.answer(
        i18n.t("person.search_prompt", lang=lang),
        reply_markup=optional_step_keyboard(
            i18n=i18n,
            lang=lang,
            allow_skip=False,
            allow_back=False,
        ),
    )


@router.message(SearchPersonStates.query)
async def search_people_query(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    current_user: User,
    i18n: I18nService,
    lang: str,
) -> None:
    query = (message.text or "").strip()

    if not query:
        await message.answer(i18n.t("person.search_prompt", lang=lang))
        return

    await state.update_data(search_query=query)

    await send_search_results(
        target=message,
        session=session,
        user_id=current_user.id,
        query=query,
        i18n=i18n,
        lang=lang,
        page=1,
    )


@router.callback_query(F.data.startswith("people:search_page:"))
async def search_people_page(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    current_user: User,
    i18n: I18nService,
    lang: str,
) -> None:
    data = await state.get_data()
    query = str(data.get("search_query") or "").strip()

    if not query:
        await callback.message.answer(i18n.t("person.search_prompt", lang=lang))
        await state.set_state(SearchPersonStates.query)
        await callback.answer()
        return

    page = parse_page(callback.data, default=1)

    await edit_search_results(
        callback=callback,
        session=session,
        user_id=current_user.id,
        query=query,
        i18n=i18n,
        lang=lang,
        page=page,
    )


@router.message(Command("edit"))
async def edit_person_command(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    current_user: User,
    i18n: I18nService,
    lang: str,
) -> None:
    await state.clear()
    await state.set_state(EditPersonStates.select_person)

    await send_people_list(
        target=message,
        session=session,
        user_id=current_user.id,
        i18n=i18n,
        lang=lang,
        page=1,
        action="edit",
        page_action="edit",
        title_key="person.select_to_edit",
    )


@router.callback_query(StateFilter(EditPersonStates.select_person), F.data.startswith("people:edit_page:"))
async def edit_person_page(
    callback: CallbackQuery,
    session: AsyncSession,
    current_user: User,
    i18n: I18nService,
    lang: str,
) -> None:
    page = parse_page(callback.data, default=1)

    await edit_people_list(
        callback=callback,
        session=session,
        user_id=current_user.id,
        i18n=i18n,
        lang=lang,
        page=page,
        action="edit",
        page_action="edit",
        title_key="person.select_to_edit",
    )


@router.callback_query(F.data.startswith("people:edit:"))
async def edit_person_selected(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    current_user: User,
    i18n: I18nService,
    lang: str,
) -> None:
    person_id = parse_id(callback.data)
    repository = PeopleRepository(session)
    person = await repository.get_person_by_id(
        user_id=current_user.id,
        person_id=person_id,
    )

    if person is None:
        await callback.message.answer(i18n.t("person.not_found", lang=lang))
        await callback.answer()
        return

    await state.set_state(EditPersonStates.select_field)
    await state.update_data(person_id=person.id)

    await callback.message.answer(
        i18n.t(
            "person.select_field",
            lang=lang,
            full_name=PeopleService().format_full_name(person),
        ),
        reply_markup=edit_field_keyboard(i18n=i18n, lang=lang),
    )
    await callback.answer()


@router.callback_query(StateFilter(EditPersonStates.select_field), F.data.startswith("person_edit_field:"))
async def edit_person_field_selected(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    current_user: User,
    i18n: I18nService,
    lang: str,
) -> None:
    field_name = callback.data.split(":", maxsplit=1)[1] if callback.data else ""

    repository = PeopleRepository(session)
    data = await state.get_data()
    person = await repository.get_person_by_id(
        user_id=current_user.id,
        person_id=int(data["person_id"]),
    )

    if person is None:
        await callback.message.answer(i18n.t("person.not_found", lang=lang))
        await callback.answer()
        return

    await state.update_data(edit_field=field_name)
    await state.set_state(EditPersonStates.input_value)

    if field_name == "category":
        await callback.message.answer(
            i18n.t("person.ask_category", lang=lang),
            reply_markup=category_keyboard(i18n=i18n, lang=lang, prefix="person_edit_category"),
        )
        await callback.answer()
        return

    if field_name == "gender":
        await callback.message.answer(
            i18n.t("person.ask_gender", lang=lang),
            reply_markup=gender_keyboard(i18n=i18n, lang=lang, prefix="person_edit_gender"),
        )
        await callback.answer()
        return

    current_value = format_field_value(
        person=person,
        field_name=field_name,
        service=PeopleService(),
        lang=lang,
    )

    await callback.message.answer(
        i18n.t(
            "person.input_new_value",
            lang=lang,
            field=i18n.t(f"person.field.{field_name}", lang=lang),
            current_value=current_value,
        ),
        reply_markup=optional_step_keyboard(
            i18n=i18n,
            lang=lang,
            allow_skip=field_name != "first_name",
            allow_back=True,
        ),
    )
    await callback.answer()


@router.callback_query(StateFilter(EditPersonStates.input_value), F.data.startswith("person_edit_category:"))
async def edit_person_category_value(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    current_user: User,
    i18n: I18nService,
    lang: str,
) -> None:
    selected_category = callback.data.split(":", maxsplit=1)[1] if callback.data else ""

    if selected_category == "cancel":
        await state.clear()
        await callback.message.answer(
            i18n.t("error.cancelled", lang=lang),
            reply_markup=main_menu_keyboard(i18n=i18n, lang=lang),
        )
        await callback.answer()
        return

    if selected_category == "back":
        await state.set_state(EditPersonStates.select_field)
        await callback.message.answer(
            i18n.t("person.select_field_again", lang=lang),
            reply_markup=edit_field_keyboard(i18n=i18n, lang=lang),
        )
        await callback.answer()
        return

    if selected_category == "custom":
        await state.update_data(
            edit_field="category",
            pending_category="custom",
            awaiting_custom_category=True,
        )
        await callback.message.answer(
            i18n.t("person.ask_custom_category", lang=lang),
            reply_markup=optional_step_keyboard(
                i18n=i18n,
                lang=lang,
                allow_skip=False,
                allow_back=True,
            ),
        )
        await callback.answer()
        return

    await prepare_edit_preview(
        callback=callback,
        state=state,
        session=session,
        current_user=current_user,
        i18n=i18n,
        lang=lang,
        raw_update={"category": selected_category},
    )


@router.callback_query(StateFilter(EditPersonStates.input_value), F.data.startswith("person_edit_gender:"))
async def edit_person_gender_value(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    current_user: User,
    i18n: I18nService,
    lang: str,
) -> None:
    selected_gender = callback.data.split(":", maxsplit=1)[1] if callback.data else ""

    if selected_gender == "cancel":
        await state.clear()
        await callback.message.answer(
            i18n.t("error.cancelled", lang=lang),
            reply_markup=main_menu_keyboard(i18n=i18n, lang=lang),
        )
        await callback.answer()
        return

    raw_update = {"gender": None if selected_gender == "clear" else selected_gender}

    await prepare_edit_preview(
        callback=callback,
        state=state,
        session=session,
        current_user=current_user,
        i18n=i18n,
        lang=lang,
        raw_update=raw_update,
    )


@router.message(EditPersonStates.input_value)
async def edit_person_input_value(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    current_user: User,
    i18n: I18nService,
    lang: str,
) -> None:
    data = await state.get_data()

    if message.text in BACK_TEXTS:
        await state.set_state(EditPersonStates.select_field)
        await message.answer(
            i18n.t("person.select_field_again", lang=lang),
            reply_markup=edit_field_keyboard(i18n=i18n, lang=lang),
        )
        return

    raw_text = optional_text(message.text)
    raw_update: dict[str, Any]

    if data.get("awaiting_custom_category"):
        if not raw_text:
            await message.answer(i18n.t("person.custom_category_required", lang=lang))
            return

        raw_update = {
            "category": "custom",
            "custom_category": raw_text,
        }
    else:
        field_name = str(data["edit_field"])

        if raw_text is None and field_name == "first_name":
            await message.answer(i18n.t("error.required_field", lang=lang))
            return

        raw_update = {field_name: raw_text}

    await prepare_edit_preview_from_message(
        message=message,
        state=state,
        session=session,
        current_user=current_user,
        i18n=i18n,
        lang=lang,
        raw_update=raw_update,
    )


@router.callback_query(StateFilter(EditPersonStates.confirm), F.data == "person_edit:save")
async def edit_person_save(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    current_user: User,
    i18n: I18nService,
    lang: str,
) -> None:
    data = await state.get_data()
    person_id = int(data["person_id"])
    raw_update = dict(data.get("pending_update") or {})

    repository = PeopleRepository(session)
    service = PeopleService()

    person = await repository.get_person_by_id(
        user_id=current_user.id,
        person_id=person_id,
    )

    if person is None:
        await callback.message.answer(i18n.t("person.not_found", lang=lang))
        await callback.answer()
        return

    old_value = service.person_to_dict(person)

    try:
        prepared_update = service.prepare_update_data(
            existing_person=person,
            data=raw_update,
        )
    except PeopleValidationError as exc:
        await callback.message.answer(i18n.t(exc.message_key, lang=lang))
        await callback.answer()
        return

    updated_person = await repository.update_person(
        user_id=current_user.id,
        person_id=person_id,
        data=prepared_update,
    )

    if updated_person is None:
        await callback.message.answer(i18n.t("person.not_found", lang=lang))
        await callback.answer()
        return

    new_value = service.person_to_dict(updated_person)

    audit_service = AuditService(session)
    await audit_service.log_person_updated(
        user_id=current_user.id,
        person_id=updated_person.id,
        old_value=old_value,
        new_value=new_value,
    )

    backup_trigger = BackupTriggerService()
    await backup_trigger.trigger_user_backup(
        user_id=current_user.id,
        reason="person.updated",
        metadata={"person_id": updated_person.id},
    )

    await state.clear()

    await callback.message.answer(
        i18n.t("person.updated", lang=lang),
        reply_markup=main_menu_keyboard(i18n=i18n, lang=lang),
    )
    await callback.message.answer(
        render_person_profile(
            person=updated_person,
            i18n=i18n,
            lang=lang,
            service=service,
        ),
        reply_markup=profile_actions_keyboard(
            person_id=updated_person.id,
            i18n=i18n,
            lang=lang,
        ),
    )
    await callback.answer()


@router.callback_query(StateFilter(EditPersonStates.confirm), F.data == "person_edit:back")
async def edit_person_confirm_back(
    callback: CallbackQuery,
    state: FSMContext,
    i18n: I18nService,
    lang: str,
) -> None:
    await state.set_state(EditPersonStates.select_field)

    await callback.message.answer(
        i18n.t("person.select_field_again", lang=lang),
        reply_markup=edit_field_keyboard(i18n=i18n, lang=lang),
    )
    await callback.answer()


@router.callback_query(F.data == "person_edit:cancel")
async def edit_person_cancel(
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


@router.message(Command("delete"))
async def delete_person_command(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    current_user: User,
    i18n: I18nService,
    lang: str,
) -> None:
    await state.clear()
    await state.set_state(DeletePersonStates.select_person)

    await send_people_list(
        target=message,
        session=session,
        user_id=current_user.id,
        i18n=i18n,
        lang=lang,
        page=1,
        action="delete",
        page_action="delete",
        title_key="person.select_to_delete",
    )


@router.callback_query(StateFilter(DeletePersonStates.select_person), F.data.startswith("people:delete_page:"))
async def delete_person_page(
    callback: CallbackQuery,
    session: AsyncSession,
    current_user: User,
    i18n: I18nService,
    lang: str,
) -> None:
    page = parse_page(callback.data, default=1)

    await edit_people_list(
        callback=callback,
        session=session,
        user_id=current_user.id,
        i18n=i18n,
        lang=lang,
        page=page,
        action="delete",
        page_action="delete",
        title_key="person.select_to_delete",
    )


@router.callback_query(F.data.startswith("people:delete:"))
async def delete_person_selected(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    current_user: User,
    i18n: I18nService,
    lang: str,
) -> None:
    person_id = parse_id(callback.data)
    repository = PeopleRepository(session)
    person = await repository.get_person_by_id(
        user_id=current_user.id,
        person_id=person_id,
    )

    if person is None:
        await callback.message.answer(i18n.t("person.not_found", lang=lang))
        await callback.answer()
        return

    await state.set_state(DeletePersonStates.confirm)
    await state.update_data(person_id=person.id)

    await callback.message.answer(
        i18n.t(
            "person.delete_confirm",
            lang=lang,
            full_name=PeopleService().format_full_name(person),
        ),
        reply_markup=delete_confirm_keyboard(i18n=i18n, lang=lang),
    )
    await callback.answer()


@router.callback_query(StateFilter(DeletePersonStates.confirm), F.data == "person_delete:confirm")
async def delete_person_confirm(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    current_user: User,
    i18n: I18nService,
    lang: str,
) -> None:
    data = await state.get_data()
    person_id = int(data["person_id"])

    repository = PeopleRepository(session)
    service = PeopleService()

    person = await repository.get_person_by_id(
        user_id=current_user.id,
        person_id=person_id,
    )

    if person is None:
        await callback.message.answer(i18n.t("person.not_found", lang=lang))
        await callback.answer()
        return

    old_value = service.person_to_dict(person)

    deleted_person = await repository.soft_delete_person(
        user_id=current_user.id,
        person_id=person_id,
    )

    if deleted_person is None:
        await callback.message.answer(i18n.t("person.not_found", lang=lang))
        await callback.answer()
        return

    await service.run_after_person_deleted_hooks(
        user_id=current_user.id,
        person_id=deleted_person.id,
    )

    audit_service = AuditService(session)
    await audit_service.log_person_deleted(
        user_id=current_user.id,
        person_id=deleted_person.id,
        old_value=old_value,
        new_value=service.person_to_dict(deleted_person),
    )

    backup_trigger = BackupTriggerService()
    await backup_trigger.trigger_user_backup(
        user_id=current_user.id,
        reason="person.deleted",
        metadata={"person_id": deleted_person.id},
    )

    await state.clear()

    await callback.message.answer(
        i18n.t("person.deleted", lang=lang),
        reply_markup=main_menu_keyboard(i18n=i18n, lang=lang),
    )
    await callback.answer()


@router.callback_query(F.data == "person_delete:cancel")
async def delete_person_cancel(
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


async def send_people_list(
    target: Message,
    session: AsyncSession,
    user_id: int,
    i18n: I18nService,
    lang: str,
    page: int,
    action: str,
    page_action: str,
    title_key: str = "person.select_to_view",
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
        build_list_text(
            i18n=i18n,
            lang=lang,
            title_key=title_key,
            page=page,
            total_count=total_count,
        ),
        reply_markup=person_list_keyboard(
            people=people,
            i18n=i18n,
            lang=lang,
            action=action,
            page=page,
            total_count=total_count,
            page_size=PAGE_SIZE,
            page_action=page_action,
        ),
    )


async def edit_people_list(
    callback: CallbackQuery,
    session: AsyncSession,
    user_id: int,
    i18n: I18nService,
    lang: str,
    page: int,
    action: str,
    page_action: str,
    title_key: str = "person.select_to_view",
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
        build_list_text(
            i18n=i18n,
            lang=lang,
            title_key=title_key,
            page=page,
            total_count=total_count,
        ),
        reply_markup=person_list_keyboard(
            people=people,
            i18n=i18n,
            lang=lang,
            action=action,
            page=page,
            total_count=total_count,
            page_size=PAGE_SIZE,
            page_action=page_action,
        ),
    )
    await callback.answer()


async def send_search_results(
    target: Message,
    session: AsyncSession,
    user_id: int,
    query: str,
    i18n: I18nService,
    lang: str,
    page: int,
) -> None:
    repository = PeopleRepository(session)
    total_count = await repository.count_search_people(user_id=user_id, query=query)

    if total_count == 0:
        await target.answer(
            i18n.t("person.search_empty", lang=lang),
            reply_markup=main_menu_keyboard(i18n=i18n, lang=lang),
        )
        return

    people = await repository.search_people(
        user_id=user_id,
        query=query,
        page=page,
        page_size=PAGE_SIZE,
    )

    await target.answer(
        build_search_text(
            i18n=i18n,
            lang=lang,
            query=query,
            page=page,
            total_count=total_count,
        ),
        reply_markup=person_list_keyboard(
            people=people,
            i18n=i18n,
            lang=lang,
            action="view",
            page=page,
            total_count=total_count,
            page_size=PAGE_SIZE,
            page_action="search",
        ),
    )


async def edit_search_results(
    callback: CallbackQuery,
    session: AsyncSession,
    user_id: int,
    query: str,
    i18n: I18nService,
    lang: str,
    page: int,
) -> None:
    repository = PeopleRepository(session)
    total_count = await repository.count_search_people(user_id=user_id, query=query)

    if total_count == 0:
        await callback.message.edit_text(i18n.t("person.search_empty", lang=lang))
        await callback.answer()
        return

    total_pages = max(1, ceil(total_count / PAGE_SIZE))
    page = min(max(1, page), total_pages)

    people = await repository.search_people(
        user_id=user_id,
        query=query,
        page=page,
        page_size=PAGE_SIZE,
    )

    await callback.message.edit_text(
        build_search_text(
            i18n=i18n,
            lang=lang,
            query=query,
            page=page,
            total_count=total_count,
        ),
        reply_markup=person_list_keyboard(
            people=people,
            i18n=i18n,
            lang=lang,
            action="view",
            page=page,
            total_count=total_count,
            page_size=PAGE_SIZE,
            page_action="search",
        ),
    )
    await callback.answer()


async def prepare_edit_preview(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    current_user: User,
    i18n: I18nService,
    lang: str,
    raw_update: dict[str, Any],
) -> None:
    data = await state.get_data()
    repository = PeopleRepository(session)
    service = PeopleService()

    person = await repository.get_person_by_id(
        user_id=current_user.id,
        person_id=int(data["person_id"]),
    )

    if person is None:
        await callback.message.answer(i18n.t("person.not_found", lang=lang))
        await callback.answer()
        return

    try:
        prepared_update = service.prepare_update_data(
            existing_person=person,
            data=raw_update,
        )
    except PeopleValidationError as exc:
        await callback.message.answer(i18n.t(exc.message_key, lang=lang))
        await callback.answer()
        return

    await state.update_data(
        pending_update=raw_update,
        awaiting_custom_category=False,
        pending_category=None,
    )
    await state.set_state(EditPersonStates.confirm)

    await callback.message.answer(
        render_edit_preview(
            person=person,
            prepared_update=prepared_update,
            i18n=i18n,
            lang=lang,
            service=service,
        ),
        reply_markup=confirm_keyboard(i18n=i18n, lang=lang, prefix="person_edit"),
    )
    await callback.answer()


async def prepare_edit_preview_from_message(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    current_user: User,
    i18n: I18nService,
    lang: str,
    raw_update: dict[str, Any],
) -> None:
    data = await state.get_data()
    repository = PeopleRepository(session)
    service = PeopleService()

    person = await repository.get_person_by_id(
        user_id=current_user.id,
        person_id=int(data["person_id"]),
    )

    if person is None:
        await message.answer(i18n.t("person.not_found", lang=lang))
        return

    try:
        prepared_update = service.prepare_update_data(
            existing_person=person,
            data=raw_update,
        )
    except PeopleValidationError as exc:
        await message.answer(i18n.t(exc.message_key, lang=lang))
        return

    await state.update_data(
        pending_update=raw_update,
        awaiting_custom_category=False,
        pending_category=None,
    )
    await state.set_state(EditPersonStates.confirm)

    await message.answer(
        render_edit_preview(
            person=person,
            prepared_update=prepared_update,
            i18n=i18n,
            lang=lang,
            service=service,
        ),
        reply_markup=confirm_keyboard(i18n=i18n, lang=lang, prefix="person_edit"),
    )


def render_person_preview(
    data: dict[str, Any],
    i18n: I18nService,
    lang: str,
    service: PeopleService,
) -> str:
    rows = [
        ("first_name", data.get("first_name")),
        ("last_name", data.get("last_name")),
        ("middle_name", data.get("middle_name")),
        ("nickname", data.get("nickname")),
        ("phone", data.get("phone")),
        ("telegram_username", format_username(data.get("telegram_username"))),
        ("birth_date", service.format_birth_date(data, lang=lang)),
        ("gender", format_gender(data.get("gender"), i18n=i18n, lang=lang)),
        ("category", format_category(data.get("category"), data.get("custom_category"), i18n=i18n, lang=lang)),
        ("note", data.get("note")),
        ("how_met", data.get("how_met")),
        ("location", data.get("location")),
        ("workplace", data.get("workplace")),
        ("education_place", data.get("education_place")),
    ]

    rendered_rows = []

    for field_name, value in rows:
        if value is None or value == "":
            continue

        rendered_rows.append(
            f"{i18n.t(f'person.field.{field_name}', lang=lang)}: {value}",
        )

    return "\n".join(rendered_rows) if rendered_rows else "—"


def render_person_profile(
    person: Person,
    i18n: I18nService,
    lang: str,
    service: PeopleService,
) -> str:
    age = service.calculate_age(person)
    birth_date_text = service.format_birth_date(person, lang=lang)

    if age is not None:
        birth_date_text = i18n.t(
            "person.birth_date_with_age",
            lang=lang,
            birth_date=birth_date_text,
            age=age,
        )

    rows = [
        f"👤 {service.format_full_name(person)}",
        f"📛 {i18n.t('person.field.nickname', lang=lang)}: {person.nickname or '—'}",
        f"📱 {i18n.t('person.field.phone', lang=lang)}: {person.phone or '—'}",
        f"🔗 {i18n.t('person.field.telegram_username', lang=lang)}: {format_username(person.telegram_username)}",
        f"🎂 {i18n.t('person.field.birth_date', lang=lang)}: {birth_date_text}",
        f"🏷 {i18n.t('person.field.category', lang=lang)}: {format_category(person.category, person.custom_category, i18n=i18n, lang=lang)}",
        f"📍 {i18n.t('person.field.location', lang=lang)}: {person.location or '—'}",
        f"💼 {i18n.t('person.field.workplace', lang=lang)}: {person.workplace or '—'}",
        f"🎓 {i18n.t('person.field.education_place', lang=lang)}: {person.education_place or '—'}",
        f"📝 {i18n.t('person.field.note', lang=lang)}: {person.note or '—'}",
        "",
        i18n.t("person.relationships_placeholder", lang=lang),
    ]

    return "\n".join(rows)


def render_edit_preview(
    person: Person,
    prepared_update: dict[str, Any],
    i18n: I18nService,
    lang: str,
    service: PeopleService,
) -> str:
    preview_rows = [
        i18n.t("person.edit_preview_title", lang=lang),
        "",
        i18n.t(
            "person.editing_person",
            lang=lang,
            full_name=service.format_full_name(person),
        ),
    ]

    for field_name, new_value in prepared_update.items():
        if field_name in {"birth_year_known", "birth_month", "birth_day"}:
            continue

        old_value = format_field_value(
            person=person,
            field_name=field_name,
            service=service,
            lang=lang,
            i18n=i18n,
        )

        display_new_value = format_raw_value(
            field_name=field_name,
            value=new_value,
            prepared_update=prepared_update,
            service=service,
            i18n=i18n,
            lang=lang,
        )

        preview_rows.append(
            f"{i18n.t(f'person.field.{field_name}', lang=lang)}: {old_value} → {display_new_value}",
        )

    return "\n".join(preview_rows)


def format_field_value(
    person: Person,
    field_name: str,
    service: PeopleService,
    lang: str,
    i18n: I18nService | None = None,
) -> str:
    if field_name == "birth_date":
        return service.format_birth_date(person, lang=lang)

    if field_name == "category":
        return format_category(
            person.category,
            person.custom_category,
            i18n=i18n,
            lang=lang,
        )

    if field_name == "gender":
        return format_gender(
            person.gender,
            i18n=i18n,
            lang=lang,
        )

    if field_name == "telegram_username":
        return format_username(person.telegram_username)

    value = getattr(person, field_name, None)

    return str(value) if value is not None and str(value) else "—"


def format_raw_value(
    field_name: str,
    value: Any,
    prepared_update: dict[str, Any],
    service: PeopleService,
    i18n: I18nService,
    lang: str,
) -> str:
    if field_name == "birth_date":
        return service.format_birth_date(prepared_update, lang=lang)

    if field_name == "category":
        return format_category(
            value,
            prepared_update.get("custom_category"),
            i18n=i18n,
            lang=lang,
        )

    if field_name == "gender":
        return format_gender(value, i18n=i18n, lang=lang)

    if field_name == "telegram_username":
        return format_username(value)

    return str(value) if value is not None and str(value) else "—"


def format_category(
    category: str | None,
    custom_category: str | None,
    i18n: I18nService | None,
    lang: str,
) -> str:
    if category == "custom" and custom_category:
        return custom_category

    if category and i18n is not None:
        return i18n.t(f"person.category.{category}", lang=lang)

    return category or "—"


def format_gender(
    gender: str | None,
    i18n: I18nService | None,
    lang: str,
) -> str:
    if gender and i18n is not None:
        return i18n.t(f"person.gender.{gender}", lang=lang)

    return gender or "—"


def format_username(value: Any) -> str:
    if value is None or not str(value).strip():
        return "—"

    username = str(value).strip().lstrip("@")

    return f"@{username}"


def build_list_text(
    i18n: I18nService,
    lang: str,
    title_key: str,
    page: int,
    total_count: int,
) -> str:
    total_pages = max(1, ceil(total_count / PAGE_SIZE))

    return "\n".join(
        [
            i18n.t(title_key, lang=lang),
            i18n.t("person.count", lang=lang, count=total_count),
            i18n.t("person.page", lang=lang, page=page, total_pages=total_pages),
        ],
    )


def build_search_text(
    i18n: I18nService,
    lang: str,
    query: str,
    page: int,
    total_count: int,
) -> str:
    total_pages = max(1, ceil(total_count / PAGE_SIZE))

    return "\n".join(
        [
            i18n.t("person.search_results", lang=lang, query=query),
            i18n.t("person.count", lang=lang, count=total_count),
            i18n.t("person.page", lang=lang, page=page, total_pages=total_pages),
        ],
    )


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