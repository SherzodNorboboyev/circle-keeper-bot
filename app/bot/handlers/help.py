from __future__ import annotations

from collections.abc import Callable

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router(name="help")


@router.message(Command("help"))
async def command_help(message: Message, tr: Callable[..., str]) -> None:
    await message.answer(tr("help.text"))
