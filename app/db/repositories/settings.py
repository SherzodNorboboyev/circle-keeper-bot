from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import UserSetting


class SettingsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_setting(
        self,
        user_id: int,
        key: str,
    ) -> UserSetting | None:
        result = await self.session.execute(
            select(UserSetting).where(
                UserSetting.user_id == user_id,
                UserSetting.key == key,
            ),
        )

        return result.scalar_one_or_none()

    async def get_value(
        self,
        user_id: int,
        key: str,
        default: Any = None,
    ) -> Any:
        setting = await self.get_setting(user_id=user_id, key=key)

        if setting is None:
            return default

        return self.unwrap_value(setting.value, default=default)

    async def get_settings(
        self,
        user_id: int,
    ) -> dict[str, Any]:
        result = await self.session.execute(
            select(UserSetting).where(UserSetting.user_id == user_id),
        )

        rows = list(result.scalars().all())

        return {
            row.key: self.unwrap_value(row.value)
            for row in rows
        }

    async def set_setting(
        self,
        user_id: int,
        key: str,
        value: Any,
    ) -> UserSetting:
        setting = await self.get_setting(user_id=user_id, key=key)

        wrapped_value = self.wrap_value(value)

        if setting is None:
            setting = UserSetting(
                user_id=user_id,
                key=key,
                value=wrapped_value,
            )
            self.session.add(setting)
        else:
            setting.value = wrapped_value

        await self.session.flush()
        await self.session.refresh(setting)

        return setting

    async def delete_setting(
        self,
        user_id: int,
        key: str,
    ) -> bool:
        setting = await self.get_setting(user_id=user_id, key=key)

        if setting is None:
            return False

        await self.session.delete(setting)
        await self.session.flush()

        return True

    @staticmethod
    def wrap_value(value: Any) -> dict[str, Any]:
        return {"value": value}

    @staticmethod
    def unwrap_value(value: dict[str, Any], default: Any = None) -> Any:
        if isinstance(value, dict) and "value" in value:
            return value["value"]

        return default