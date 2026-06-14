from __future__ import annotations

from math import ceil
from typing import Any

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.main_menu import main_menu_keyboard
from app.bot.keyboards.people import optional_step_keyboard, person_list_keyboard
from app.bot.keyboards.relationships import (
    relationship_action_keyboard,
    relationship_confirm_keyboard,
    relationship_delete_confirm_keyboard,
    relationship_direction_keyboard,
    relationship_list_keyboard,
    relationship_type_keyboard,
    relationship_view_actions_keyboard,
    reverse_type_keyboard,
)
from app.bot.states.relationship_states import RelationshipStates
from app.db.models import Relationship, User
from app.db.repositories.people import PeopleRepository
from app.db.repositories.relationships import RelationshipsRepository
from app.services.audit_service import AuditService
from app.services.backup_trigger import BackupTriggerService
from app.services.i18n import I18nService
from app.services.people_service import PeopleService
from app.services.relationship_service import RelationshipService, RelationshipValidationError

router = Router(name="relationships")

PAGE_SIZE = 10

RELATIONSHIP_MENU_TEXTS = {
    "Aloqalar",
    "Связи",
    "Relationships",
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


@router.callback_query(F.data == "relationship:noop")
async def relationship_noop(callback: CallbackQuery) -> None:
    await callback.answer()


@router.message(Command("relationships"))
@router.message(F.text.in_(RELATIONSHIP_MENU_TEXTS))
async def relationships_menu(
    message: Message,
    state: FSMContext,
    i18n: I18nService,
    lang: str,
) -> None:
    await state.clear()
    await state.set_state(RelationshipStates.select_action)

    await message.answer(
        i18n.t("relationship.menu", lang=lang),
        reply_markup=relationship_action_keyboard(i18n=i18n, lang=lang),
    )


@router.callback_query(F.data == "relationship_action:create")
async def relationship_create_action(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    current_user: User,
    i18n: I18nService,
    lang: str,
) -> None:
    await state.clear()
    await state.set_state(RelationshipStates.select_from)

    await send_person_selection(
        target=callback.message,
        session=session,
        user_id=current_user.id,
        i18n=i18n,
        lang=lang,
        page=1,
        action="rel_from",
        page_action="rel_from",
        title_key="relationship.select_from",
    )

    await callback.answer()


@router.callback_query(F.data.startswith("people:relationship:"))
async def relationship_create_from_profile(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    current_user: User,
    i18n: I18nService,
    lang: str,
) -> None:
    from_person_id = parse_id(callback.data)

    people_repository = PeopleRepository(session)
    from_person = await people_repository.get_person_by_id(
        user_id=current_user.id,
        person_id=from_person_id,
    )

    if from_person is None:
        await callback.message.answer(i18n.t("relationship.person_not_found", lang=lang))
        await callback.answer()
        return

    await state.clear()
    await state.update_data(from_person_id=from_person.id)
    await state.set_state(RelationshipStates.select_to)

    await callback.message.answer(
        i18n.t(
            "relationship.selected_from",
            lang=lang,
            full_name=PeopleService().format_full_name(from_person),
        ),
    )

    await send_person_selection(
        target=callback.message,
        session=session,
        user_id=current_user.id,
        i18n=i18n,
        lang=lang,
        page=1,
        action="rel_to",
        page_action="rel_to",
        title_key="relationship.select_to",
    )

    await callback.answer()


@router.callback_query(StateFilter(RelationshipStates.select_from), F.data.startswith("people:rel_from_page:"))
async def relationship_select_from_page(
    callback: CallbackQuery,
    session: AsyncSession,
    current_user: User,
    i18n: I18nService,
    lang: str,
) -> None:
    page = parse_page(callback.data)

    await edit_person_selection(
        callback=callback,
        session=session,
        user_id=current_user.id,
        i18n=i18n,
        lang=lang,
        page=page,
        action="rel_from",
        page_action="rel_from",
        title_key="relationship.select_from",
    )


@router.callback_query(StateFilter(RelationshipStates.select_to), F.data.startswith("people:rel_to_page:"))
async def relationship_select_to_page(
    callback: CallbackQuery,
    session: AsyncSession,
    current_user: User,
    i18n: I18nService,
    lang: str,
) -> None:
    page = parse_page(callback.data)

    await edit_person_selection(
        callback=callback,
        session=session,
        user_id=current_user.id,
        i18n=i18n,
        lang=lang,
        page=page,
        action="rel_to",
        page_action="rel_to",
        title_key="relationship.select_to",
    )


@router.callback_query(StateFilter(RelationshipStates.select_from), F.data.startswith("people:rel_from:"))
async def relationship_from_selected(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    current_user: User,
    i18n: I18nService,
    lang: str,
) -> None:
    from_person_id = parse_id(callback.data)

    people_repository = PeopleRepository(session)
    from_person = await people_repository.get_person_by_id(
        user_id=current_user.id,
        person_id=from_person_id,
    )

    if from_person is None:
        await callback.message.answer(i18n.t("relationship.person_not_found", lang=lang))
        await callback.answer()
        return

    await state.update_data(from_person_id=from_person.id)
    await state.set_state(RelationshipStates.select_to)

    await callback.message.answer(
        i18n.t(
            "relationship.selected_from",
            lang=lang,
            full_name=PeopleService().format_full_name(from_person),
        ),
    )

    await send_person_selection(
        target=callback.message,
        session=session,
        user_id=current_user.id,
        i18n=i18n,
        lang=lang,
        page=1,
        action="rel_to",
        page_action="rel_to",
        title_key="relationship.select_to",
    )

    await callback.answer()


@router.callback_query(StateFilter(RelationshipStates.select_to), F.data.startswith("people:rel_to:"))
async def relationship_to_selected(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    current_user: User,
    i18n: I18nService,
    lang: str,
) -> None:
    to_person_id = parse_id(callback.data)
    data = await state.get_data()

    from_person_id = int(data["from_person_id"])

    if from_person_id == to_person_id:
        await callback.message.answer(i18n.t("relationship.self_not_allowed", lang=lang))
        await callback.answer()
        return

    people_repository = PeopleRepository(session)
    to_person = await people_repository.get_person_by_id(
        user_id=current_user.id,
        person_id=to_person_id,
    )

    if to_person is None:
        await callback.message.answer(i18n.t("relationship.person_not_found", lang=lang))
        await callback.answer()
        return

    await state.update_data(to_person_id=to_person.id)
    await state.set_state(RelationshipStates.relationship_type)

    await callback.message.answer(
        i18n.t(
            "relationship.selected_to",
            lang=lang,
            full_name=PeopleService().format_full_name(to_person),
        ),
    )

    await callback.message.answer(
        i18n.t("relationship.ask_type", lang=lang),
        reply_markup=relationship_type_keyboard(i18n=i18n, lang=lang),
    )

    await callback.answer()


@router.callback_query(StateFilter(RelationshipStates.relationship_type), F.data.startswith("relationship_type:"))
async def relationship_type_selected(
    callback: CallbackQuery,
    state: FSMContext,
    i18n: I18nService,
    lang: str,
) -> None:
    relationship_type = callback.data.split(":", maxsplit=1)[1] if callback.data else ""

    if relationship_type == "cancel":
        await cancel_relationship_flow(callback=callback, state=state, i18n=i18n, lang=lang)
        return

    if relationship_type == "back":
        await state.set_state(RelationshipStates.select_to)
        await callback.message.answer(i18n.t("relationship.select_to", lang=lang))
        await callback.answer()
        return

    if relationship_type == "custom":
        await state.update_data(relationship_type=relationship_type)
        await state.set_state(RelationshipStates.custom_label)

        await callback.message.answer(
            i18n.t("relationship.ask_custom_label", lang=lang),
            reply_markup=optional_step_keyboard(
                i18n=i18n,
                lang=lang,
                allow_skip=False,
                allow_back=True,
            ),
        )
        await callback.answer()
        return

    await state.update_data(relationship_type=relationship_type)
    await proceed_after_relationship_type(
        callback=callback,
        state=state,
        i18n=i18n,
        lang=lang,
        relationship_type=relationship_type,
    )


@router.message(RelationshipStates.custom_label)
async def relationship_custom_label_input(
    message: Message,
    state: FSMContext,
    i18n: I18nService,
    lang: str,
) -> None:
    value = (message.text or "").strip()

    if value in BACK_TEXTS:
        await state.set_state(RelationshipStates.relationship_type)
        await message.answer(
            i18n.t("relationship.ask_type", lang=lang),
            reply_markup=relationship_type_keyboard(i18n=i18n, lang=lang),
        )
        return

    if not value:
        await message.answer(i18n.t("relationship.custom_label_required", lang=lang))
        return

    await state.update_data(custom_label=value)

    await state.set_state(RelationshipStates.direction)
    await message.answer(
        i18n.t("relationship.ask_direction", lang=lang),
        reply_markup=relationship_direction_keyboard(i18n=i18n, lang=lang),
    )


@router.callback_query(StateFilter(RelationshipStates.direction), F.data.startswith("relationship_direction:"))
async def relationship_direction_selected(
    callback: CallbackQuery,
    state: FSMContext,
    i18n: I18nService,
    lang: str,
) -> None:
    direction = callback.data.split(":", maxsplit=1)[1] if callback.data else ""

    if direction == "cancel":
        await cancel_relationship_flow(callback=callback, state=state, i18n=i18n, lang=lang)
        return

    if direction == "back":
        data = await state.get_data()

        if data.get("relationship_type") == "custom":
            await state.set_state(RelationshipStates.custom_label)
            await callback.message.answer(
                i18n.t("relationship.ask_custom_label", lang=lang),
                reply_markup=optional_step_keyboard(
                    i18n=i18n,
                    lang=lang,
                    allow_skip=False,
                    allow_back=True,
                ),
            )
        else:
            await state.set_state(RelationshipStates.relationship_type)
            await callback.message.answer(
                i18n.t("relationship.ask_type", lang=lang),
                reply_markup=relationship_type_keyboard(i18n=i18n, lang=lang),
            )

        await callback.answer()
        return

    if direction == "bidirectional":
        await state.update_data(
            is_bidirectional=True,
            reverse_relationship_type=None,
        )
        await ask_relationship_note(callback=callback, state=state, i18n=i18n, lang=lang)
        return

    if direction == "directed":
        await state.update_data(is_bidirectional=False)
        await state.set_state(RelationshipStates.reverse_type)

        await callback.message.answer(
            i18n.t("relationship.ask_reverse_type", lang=lang),
            reply_markup=reverse_type_keyboard(i18n=i18n, lang=lang),
        )
        await callback.answer()
        return

    await callback.answer()


@router.callback_query(StateFilter(RelationshipStates.reverse_type), F.data.startswith("relationship_reverse:"))
async def relationship_reverse_type_selected(
    callback: CallbackQuery,
    state: FSMContext,
    i18n: I18nService,
    lang: str,
) -> None:
    reverse_type = callback.data.split(":", maxsplit=1)[1] if callback.data else ""

    if reverse_type == "cancel":
        await cancel_relationship_flow(callback=callback, state=state, i18n=i18n, lang=lang)
        return

    if reverse_type == "back":
        await state.set_state(RelationshipStates.direction)
        await callback.message.answer(
            i18n.t("relationship.ask_direction", lang=lang),
            reply_markup=relationship_direction_keyboard(i18n=i18n, lang=lang),
        )
        await callback.answer()
        return

    await state.update_data(
        reverse_relationship_type=None if reverse_type == "none" else reverse_type,
    )
    await ask_relationship_note(callback=callback, state=state, i18n=i18n, lang=lang)


@router.message(RelationshipStates.note)
async def relationship_note_input(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    current_user: User,
    i18n: I18nService,
    lang: str,
) -> None:
    await state.update_data(note=optional_text(message.text))

    await show_relationship_preview_from_message(
        message=message,
        state=state,
        session=session,
        current_user=current_user,
        i18n=i18n,
        lang=lang,
    )


@router.callback_query(StateFilter(RelationshipStates.confirm), F.data == "relationship_confirm:save")
async def relationship_confirm_save(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    current_user: User,
    i18n: I18nService,
    lang: str,
) -> None:
    data = await state.get_data()
    service = RelationshipService()

    try:
        relationship = await service.create_relationship(
            session=session,
            user_id=current_user.id,
            from_person_id=int(data["from_person_id"]),
            to_person_id=int(data["to_person_id"]),
            relationship_type=str(data["relationship_type"]),
            custom_label=data.get("custom_label"),
            note=data.get("note"),
            is_bidirectional=data.get("is_bidirectional"),
            reverse_relationship_type=data.get("reverse_relationship_type"),
        )
    except RelationshipValidationError as exc:
        await callback.message.answer(i18n.t(exc.message_key, lang=lang))
        await callback.answer()
        return

    audit_service = AuditService(session)
    await audit_service.log_relationship_created(
        user_id=current_user.id,
        relationship_id=relationship.id,
        new_value=service.relationship_to_dict(relationship),
    )

    backup_trigger = BackupTriggerService()
    await backup_trigger.trigger_user_backup(
        user_id=current_user.id,
        reason="relationship.created",
        metadata={"relationship_id": relationship.id},
    )

    await state.clear()

    await callback.message.answer(
        i18n.t("relationship.created", lang=lang),
        reply_markup=main_menu_keyboard(i18n=i18n, lang=lang),
    )
    await callback.answer()


@router.callback_query(StateFilter(RelationshipStates.confirm), F.data == "relationship_confirm:back")
async def relationship_confirm_back(
    callback: CallbackQuery,
    state: FSMContext,
    i18n: I18nService,
    lang: str,
) -> None:
    await ask_relationship_note(callback=callback, state=state, i18n=i18n, lang=lang)


@router.callback_query(StateFilter(RelationshipStates.confirm), F.data == "relationship_confirm:cancel")
async def relationship_confirm_cancel(
    callback: CallbackQuery,
    state: FSMContext,
    i18n: I18nService,
    lang: str,
) -> None:
    await cancel_relationship_flow(callback=callback, state=state, i18n=i18n, lang=lang)


@router.callback_query(F.data == "relationship_action:list")
async def relationship_list_action(
    callback: CallbackQuery,
    session: AsyncSession,
    current_user: User,
    i18n: I18nService,
    lang: str,
) -> None:
    await send_relationship_list(
        target=callback.message,
        session=session,
        user_id=current_user.id,
        i18n=i18n,
        lang=lang,
        page=1,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("relationship:list_page:"))
async def relationship_list_page(
    callback: CallbackQuery,
    session: AsyncSession,
    current_user: User,
    i18n: I18nService,
    lang: str,
) -> None:
    page = parse_page(callback.data)

    await edit_relationship_list(
        callback=callback,
        session=session,
        user_id=current_user.id,
        i18n=i18n,
        lang=lang,
        page=page,
    )


@router.callback_query(F.data.startswith("relationship:view:"))
async def relationship_view(
    callback: CallbackQuery,
    session: AsyncSession,
    current_user: User,
    i18n: I18nService,
    lang: str,
) -> None:
    relationship_id = parse_id(callback.data)
    repository = RelationshipsRepository(session)

    relationship = await repository.get_relationship_by_id(
        user_id=current_user.id,
        relationship_id=relationship_id,
    )

    if relationship is None:
        await callback.message.answer(i18n.t("relationship.not_found", lang=lang))
        await callback.answer()
        return

    text = await render_relationship_view(
        session=session,
        user_id=current_user.id,
        relationship=relationship,
        i18n=i18n,
        lang=lang,
    )

    await callback.message.edit_text(
        text,
        reply_markup=relationship_view_actions_keyboard(
            relationship_id=relationship.id,
            i18n=i18n,
            lang=lang,
        ),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("relationship:delete:"))
async def relationship_delete(
    callback: CallbackQuery,
    session: AsyncSession,
    current_user: User,
    i18n: I18nService,
    lang: str,
) -> None:
    relationship_id = parse_id(callback.data)
    repository = RelationshipsRepository(session)

    relationship = await repository.get_relationship_by_id(
        user_id=current_user.id,
        relationship_id=relationship_id,
    )

    if relationship is None:
        await callback.message.answer(i18n.t("relationship.not_found", lang=lang))
        await callback.answer()
        return

    await callback.message.answer(
        i18n.t("relationship.delete_confirm", lang=lang),
        reply_markup=relationship_delete_confirm_keyboard(
            relationship_id=relationship.id,
            i18n=i18n,
            lang=lang,
        ),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("relationship_delete:confirm:"))
async def relationship_delete_confirm(
    callback: CallbackQuery,
    session: AsyncSession,
    current_user: User,
    i18n: I18nService,
    lang: str,
) -> None:
    relationship_id = parse_id(callback.data)

    repository = RelationshipsRepository(session)
    service = RelationshipService()

    relationship = await repository.get_relationship_by_id(
        user_id=current_user.id,
        relationship_id=relationship_id,
    )

    if relationship is None:
        await callback.message.answer(i18n.t("relationship.not_found", lang=lang))
        await callback.answer()
        return

    old_value = service.relationship_to_dict(relationship)

    deleted_relationship = await repository.soft_delete_relationship(
        user_id=current_user.id,
        relationship_id=relationship_id,
    )

    if deleted_relationship is None:
        await callback.message.answer(i18n.t("relationship.not_found", lang=lang))
        await callback.answer()
        return

    audit_service = AuditService(session)
    await audit_service.log_relationship_deleted(
        user_id=current_user.id,
        relationship_id=deleted_relationship.id,
        old_value=old_value,
        new_value=service.relationship_to_dict(deleted_relationship),
    )

    backup_trigger = BackupTriggerService()
    await backup_trigger.trigger_user_backup(
        user_id=current_user.id,
        reason="relationship.deleted",
        metadata={"relationship_id": deleted_relationship.id},
    )

    await callback.message.answer(
        i18n.t("relationship.deleted", lang=lang),
        reply_markup=main_menu_keyboard(i18n=i18n, lang=lang),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("relationship_delete:cancel:"))
async def relationship_delete_cancel(
    callback: CallbackQuery,
    i18n: I18nService,
    lang: str,
) -> None:
    await callback.message.answer(i18n.t("error.cancelled", lang=lang))
    await callback.answer()


async def proceed_after_relationship_type(
    callback: CallbackQuery,
    state: FSMContext,
    i18n: I18nService,
    lang: str,
    relationship_type: str,
) -> None:
    if relationship_type in {"relative"}:
        await state.set_state(RelationshipStates.direction)
        await callback.message.answer(
            i18n.t("relationship.ask_direction", lang=lang),
            reply_markup=relationship_direction_keyboard(i18n=i18n, lang=lang),
        )
        await callback.answer()
        return

    if relationship_type in {"parent", "child"}:
        await state.update_data(
            is_bidirectional=False,
            reverse_relationship_type="child" if relationship_type == "parent" else "parent",
        )
        await ask_relationship_note(callback=callback, state=state, i18n=i18n, lang=lang)
        return

    await state.update_data(
        is_bidirectional=True,
        reverse_relationship_type=None,
    )
    await ask_relationship_note(callback=callback, state=state, i18n=i18n, lang=lang)


async def ask_relationship_note(
    callback: CallbackQuery,
    state: FSMContext,
    i18n: I18nService,
    lang: str,
) -> None:
    await state.set_state(RelationshipStates.note)

    await callback.message.answer(
        i18n.t("relationship.ask_note", lang=lang),
        reply_markup=optional_step_keyboard(i18n=i18n, lang=lang),
    )
    await callback.answer()


async def show_relationship_preview_from_message(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    current_user: User,
    i18n: I18nService,
    lang: str,
) -> None:
    data = await state.get_data()
    service = RelationshipService()

    try:
        prepared = await service.prepare_create_data(
            session=session,
            user_id=current_user.id,
            from_person_id=int(data["from_person_id"]),
            to_person_id=int(data["to_person_id"]),
            relationship_type=str(data["relationship_type"]),
            custom_label=data.get("custom_label"),
            note=data.get("note"),
            is_bidirectional=data.get("is_bidirectional"),
            reverse_relationship_type=data.get("reverse_relationship_type"),
        )
    except RelationshipValidationError as exc:
        await message.answer(i18n.t(exc.message_key, lang=lang))
        return

    await state.update_data(prepared_relationship=prepared)
    await state.set_state(RelationshipStates.confirm)

    await message.answer(
        await render_relationship_preview(
            session=session,
            user_id=current_user.id,
            data=prepared,
            i18n=i18n,
            lang=lang,
        ),
        reply_markup=relationship_confirm_keyboard(i18n=i18n, lang=lang),
    )


async def send_person_selection(
    target: Message,
    session: AsyncSession,
    user_id: int,
    i18n: I18nService,
    lang: str,
    page: int,
    action: str,
    page_action: str,
    title_key: str,
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
        build_person_selection_text(
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


async def edit_person_selection(
    callback: CallbackQuery,
    session: AsyncSession,
    user_id: int,
    i18n: I18nService,
    lang: str,
    page: int,
    action: str,
    page_action: str,
    title_key: str,
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
        build_person_selection_text(
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


async def send_relationship_list(
    target: Message,
    session: AsyncSession,
    user_id: int,
    i18n: I18nService,
    lang: str,
    page: int,
) -> None:
    repository = RelationshipsRepository(session)
    total_count = await repository.count_relationships(user_id=user_id)

    if total_count == 0:
        await target.answer(
            i18n.t("relationship.empty", lang=lang),
            reply_markup=relationship_action_keyboard(i18n=i18n, lang=lang),
        )
        return

    relationships = await repository.list_relationships(
        user_id=user_id,
        page=page,
        page_size=PAGE_SIZE,
    )

    items = await build_relationship_list_items(
        session=session,
        user_id=user_id,
        relationships=relationships,
        i18n=i18n,
        lang=lang,
    )

    await target.answer(
        build_relationship_list_text(
            i18n=i18n,
            lang=lang,
            page=page,
            total_count=total_count,
        ),
        reply_markup=relationship_list_keyboard(
            items=items,
            i18n=i18n,
            lang=lang,
            page=page,
            total_count=total_count,
            page_size=PAGE_SIZE,
        ),
    )


async def edit_relationship_list(
    callback: CallbackQuery,
    session: AsyncSession,
    user_id: int,
    i18n: I18nService,
    lang: str,
    page: int,
) -> None:
    repository = RelationshipsRepository(session)
    total_count = await repository.count_relationships(user_id=user_id)

    if total_count == 0:
        await callback.message.edit_text(i18n.t("relationship.empty", lang=lang))
        await callback.answer()
        return

    total_pages = max(1, ceil(total_count / PAGE_SIZE))
    page = min(max(1, page), total_pages)

    relationships = await repository.list_relationships(
        user_id=user_id,
        page=page,
        page_size=PAGE_SIZE,
    )

    items = await build_relationship_list_items(
        session=session,
        user_id=user_id,
        relationships=relationships,
        i18n=i18n,
        lang=lang,
    )

    await callback.message.edit_text(
        build_relationship_list_text(
            i18n=i18n,
            lang=lang,
            page=page,
            total_count=total_count,
        ),
        reply_markup=relationship_list_keyboard(
            items=items,
            i18n=i18n,
            lang=lang,
            page=page,
            total_count=total_count,
            page_size=PAGE_SIZE,
        ),
    )
    await callback.answer()


async def build_relationship_list_items(
    session: AsyncSession,
    user_id: int,
    relationships: list[Relationship],
    i18n: I18nService,
    lang: str,
) -> list[tuple[int, str]]:
    people_repository = PeopleRepository(session)
    people_service = PeopleService()

    items: list[tuple[int, str]] = []

    for relationship in relationships:
        from_person = await people_repository.get_person_by_id(
            user_id=user_id,
            person_id=relationship.from_person_id,
        )
        to_person = await people_repository.get_person_by_id(
            user_id=user_id,
            person_id=relationship.to_person_id,
        )

        if from_person is None or to_person is None:
            continue

        label = (
            relationship.custom_label
            if relationship.relationship_type == "custom" and relationship.custom_label
            else i18n.t(
                f"relationship.labels.{relationship.relationship_type}",
                lang=lang,
            )
        )

        from_name = people_service.format_full_name(from_person)
        to_name = people_service.format_full_name(to_person)
        relationship_text = f"{from_name} — {label} — {to_name}"

        items.append(
            (
                relationship.id,
                relationship_text,
            ),
        )

    return items


async def render_relationship_preview(
    session: AsyncSession,
    user_id: int,
    data: dict[str, Any],
    i18n: I18nService,
    lang: str,
) -> str:
    people_repository = PeopleRepository(session)
    people_service = PeopleService()

    from_person = await people_repository.get_person_by_id(
        user_id=user_id,
        person_id=int(data["from_person_id"]),
    )
    to_person = await people_repository.get_person_by_id(
        user_id=user_id,
        person_id=int(data["to_person_id"]),
    )

    from_name = people_service.format_full_name(from_person) if from_person else "—"
    to_name = people_service.format_full_name(to_person) if to_person else "—"

    relationship_label = (
        data["custom_label"]
        if data["relationship_type"] == "custom"
        else i18n.t(
            f"relationship.labels.{data['relationship_type']}",
            lang=lang,
        )
    )
    reverse_label = "—"

    if data.get("reverse_relationship_type"):
        reverse_label = i18n.t(
            f"relationship.labels.{data['reverse_relationship_type']}",
            lang=lang,
        )

    return i18n.t(
        "relationship.preview",
        lang=lang,
        from_person=from_name,
        to_person=to_name,
        relationship_type=relationship_label,
        custom_label=data.get("custom_label") or "—",
        is_bidirectional=(
            i18n.t("common.yes", lang=lang) if data.get("is_bidirectional") else i18n.t("common.no", lang=lang)
        ),
        reverse_relationship_type=reverse_label,
        note=data.get("note") or "—",
    )


async def render_relationship_view(
    session: AsyncSession,
    user_id: int,
    relationship: Relationship,
    i18n: I18nService,
    lang: str,
) -> str:
    people_repository = PeopleRepository(session)
    people_service = PeopleService()

    from_person = await people_repository.get_person_by_id(
        user_id=user_id,
        person_id=relationship.from_person_id,
    )
    to_person = await people_repository.get_person_by_id(
        user_id=user_id,
        person_id=relationship.to_person_id,
    )

    relationship_label = (
        relationship.custom_label
        if relationship.relationship_type == "custom" and relationship.custom_label
        else i18n.t(
            f"relationship.labels.{relationship.relationship_type}",
            lang=lang,
        )
    )

    reverse_label = "—"

    if relationship.reverse_relationship_type:
        reverse_label = i18n.t(
            f"relationship.labels.{relationship.reverse_relationship_type}",
            lang=lang,
        )

    return i18n.t(
        "relationship.view",
        lang=lang,
        from_person=people_service.format_full_name(from_person) if from_person else "—",
        to_person=people_service.format_full_name(to_person) if to_person else "—",
        relationship_type=relationship_label,
        custom_label=relationship.custom_label or "—",
        is_bidirectional=(
            i18n.t("common.yes", lang=lang) if relationship.is_bidirectional else i18n.t("common.no", lang=lang)
        ),
        reverse_relationship_type=reverse_label,
        note=relationship.note or "—",
    )


def build_person_selection_text(
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


def build_relationship_list_text(
    i18n: I18nService,
    lang: str,
    page: int,
    total_count: int,
) -> str:
    total_pages = max(1, ceil(total_count / PAGE_SIZE))

    return "\n".join(
        [
            i18n.t("relationship.list_title", lang=lang),
            i18n.t("relationship.count", lang=lang, count=total_count),
            i18n.t("relationship.page", lang=lang, page=page, total_pages=total_pages),
        ],
    )


async def cancel_relationship_flow(
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
