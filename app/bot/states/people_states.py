from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class AddPersonStates(StatesGroup):
    first_name = State()
    last_name = State()
    middle_name = State()
    phone = State()
    telegram_username = State()
    birth_date = State()
    category = State()
    custom_category = State()
    note = State()
    relationship_offer = State()
    confirm = State()


class EditPersonStates(StatesGroup):
    select_person = State()
    select_field = State()
    input_value = State()
    confirm = State()


class SearchPersonStates(StatesGroup):
    query = State()


class DeletePersonStates(StatesGroup):
    select_person = State()
    confirm = State()


class ImportStates(StatesGroup):
    waiting_for_file = State()
    preview = State()
    confirmation = State()
