from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class ImportStates(StatesGroup):
    waiting_for_file = State()
    preview = State()
    confirmation = State()