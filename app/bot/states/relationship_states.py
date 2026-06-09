from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class RelationshipStates(StatesGroup):
    select_action = State()
    select_from = State()
    select_to = State()
    relationship_type = State()
    custom_label = State()
    direction = State()
    reverse_type = State()
    note = State()
    confirm = State()