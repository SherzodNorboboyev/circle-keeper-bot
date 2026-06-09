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
    note = State()
    relationship_prompt = State()
    confirmation = State()