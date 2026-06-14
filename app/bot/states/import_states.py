from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class RestoreStates(StatesGroup):
    waiting_for_file = State()
    confirm = State()


class ExcelImportStates(StatesGroup):
    waiting_for_file = State()
    confirm = State()


class ImportStates(StatesGroup):
    waiting_for_file = State()
    preview = State()
    confirmation = State()