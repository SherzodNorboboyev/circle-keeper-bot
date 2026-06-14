from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Backup, ImportJob, Person, Relationship, ReminderLog, User


@dataclass(frozen=True)
class AdminStats:
    total_users: int
    active_users: int
    total_people: int
    total_active_people: int
    total_relationships: int
    total_active_relationships: int
    failed_backups: int
    failed_imports: int
    recent_import_job_counts: dict[str, int] = field(default_factory=dict)
    reminder_sent_count: int = 0
    reminder_failed_count: int = 0


class AdminService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_stats(self) -> AdminStats:
        recent_since = datetime.now(UTC) - timedelta(days=7)

        recent_import_counts = await self._group_count(
            select(ImportJob.status, func.count(ImportJob.id))
            .where(ImportJob.created_at >= recent_since)
            .group_by(ImportJob.status),
        )

        return AdminStats(
            total_users=await self._count(select(func.count(User.id))),
            active_users=await self._count(
                select(func.count(User.id)).where(User.is_active.is_(True)),
            ),
            total_people=await self._count(select(func.count(Person.id))),
            total_active_people=await self._count(
                select(func.count(Person.id)).where(Person.deleted_at.is_(None)),
            ),
            total_relationships=await self._count(select(func.count(Relationship.id))),
            total_active_relationships=await self._count(
                select(func.count(Relationship.id)).where(Relationship.deleted_at.is_(None)),
            ),
            failed_backups=await self._count(
                select(func.count(Backup.id)).where(Backup.status == "failed"),
            ),
            failed_imports=await self._count(
                select(func.count(ImportJob.id)).where(ImportJob.status == "failed"),
            ),
            recent_import_job_counts=recent_import_counts,
            reminder_sent_count=await self._count(
                select(func.count(ReminderLog.id)).where(ReminderLog.status == "sent"),
            ),
            reminder_failed_count=await self._count(
                select(func.count(ReminderLog.id)).where(ReminderLog.status == "failed"),
            ),
        )

    async def _count(self, statement) -> int:
        result = await self.session.execute(statement)
        return int(result.scalar_one() or 0)

    async def _group_count(self, statement) -> dict[str, int]:
        result = await self.session.execute(statement)
        return {
            str(status): int(count)
            for status, count in result.all()
        }