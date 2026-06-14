from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class SettingsStates(StatesGroup):
    timezone = State()
    reminder_time = State()
    days_before = State()
