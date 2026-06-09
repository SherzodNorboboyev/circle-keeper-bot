from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class AddChildStates(StatesGroup):
    select_parent = State()
    first_name = State()
    last_name = State()
    birth_date = State()
    gender = State()
    note = State()
    confirm = State()