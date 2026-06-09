from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.audit_logs import AuditLogRepository


class AuditService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = AuditLogRepository(session)

    async def log_person_created(
        self,
        user_id: int,
        person_id: int,
        new_value: dict[str, Any],
    ) -> None:
        await self.repository.create(
            user_id=user_id,
            action="person.created",
            entity_type="person",
            entity_id=person_id,
            old_value=None,
            new_value=new_value,
        )

    async def log_person_updated(
        self,
        user_id: int,
        person_id: int,
        old_value: dict[str, Any],
        new_value: dict[str, Any],
    ) -> None:
        await self.repository.create(
            user_id=user_id,
            action="person.updated",
            entity_type="person",
            entity_id=person_id,
            old_value=old_value,
            new_value=new_value,
        )

    async def log_person_deleted(
        self,
        user_id: int,
        person_id: int,
        old_value: dict[str, Any],
        new_value: dict[str, Any],
    ) -> None:
        await self.repository.create(
            user_id=user_id,
            action="person.deleted",
            entity_type="person",
            entity_id=person_id,
            old_value=old_value,
            new_value=new_value,
        )