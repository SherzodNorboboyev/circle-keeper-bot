from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Backup


class BackupsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_backup_record(
        self,
        user_id: int,
        backup_type: str,
        storage_format: str,
        telegram_chat_id: int,
        filename: str,
        schema_version: str,
        status: str = "pending",
        telegram_message_id: int | None = None,
        file_id: str | None = None,
        file_unique_id: str | None = None,
        sha256: str | None = None,
        file_size: int | None = None,
        is_latest: bool = False,
        error_message: str | None = None,
    ) -> Backup:
        backup = Backup(
            user_id=user_id,
            backup_type=backup_type,
            storage_format=storage_format,
            telegram_chat_id=telegram_chat_id,
            telegram_message_id=telegram_message_id,
            file_id=file_id,
            file_unique_id=file_unique_id,
            filename=filename,
            sha256=sha256,
            file_size=file_size,
            schema_version=schema_version,
            status=status,
            is_latest=is_latest,
            error_message=error_message,
        )

        self.session.add(backup)
        await self.session.flush()
        await self.session.refresh(backup)

        return backup

    async def mark_backup_sent(
        self,
        backup_id: int,
        telegram_message_id: int,
        file_id: str,
        file_unique_id: str,
        sha256: str,
        file_size: int,
    ) -> Backup:
        backup = await self._get_backup_by_id(backup_id=backup_id)

        if backup is None:
            raise ValueError(f"Backup not found: {backup_id}")

        backup.telegram_message_id = telegram_message_id
        backup.file_id = file_id
        backup.file_unique_id = file_unique_id
        backup.sha256 = sha256
        backup.file_size = file_size
        backup.status = "sent"
        backup.error_message = None

        await self.session.flush()
        await self.set_latest_backup(user_id=backup.user_id, backup_id=backup.id)
        await self.session.refresh(backup)

        return backup

    async def mark_backup_failed(
        self,
        backup_id: int,
        error_message: str,
    ) -> Backup:
        backup = await self._get_backup_by_id(backup_id=backup_id)

        if backup is None:
            raise ValueError(f"Backup not found: {backup_id}")

        backup.status = "failed"
        backup.is_latest = False
        backup.error_message = error_message[:5000]

        await self.session.flush()
        await self.session.refresh(backup)

        return backup

    async def set_latest_backup(
        self,
        user_id: int,
        backup_id: int,
    ) -> Backup:
        await self.session.execute(
            update(Backup)
            .where(
                Backup.user_id == user_id,
                Backup.is_latest.is_(True),
            )
            .values(is_latest=False),
        )

        backup = await self._get_backup_by_id(backup_id=backup_id)

        if backup is None or backup.user_id != user_id:
            raise ValueError(f"Backup not found for user: backup_id={backup_id}, user_id={user_id}")

        backup.is_latest = True

        await self.session.flush()
        await self.session.refresh(backup)

        return backup

    async def get_latest_backup(self, user_id: int) -> Backup | None:
        result = await self.session.execute(
            select(Backup)
            .where(
                Backup.user_id == user_id,
                Backup.is_latest.is_(True),
                Backup.status == "sent",
            )
            .order_by(Backup.created_at.desc(), Backup.id.desc())
            .limit(1),
        )

        return result.scalar_one_or_none()

    async def list_backups(
        self,
        user_id: int,
        page: int = 1,
        page_size: int = 10,
    ) -> list[Backup]:
        page = max(1, page)
        page_size = max(1, min(page_size, 100))
        offset = (page - 1) * page_size

        result = await self.session.execute(
            select(Backup)
            .where(Backup.user_id == user_id)
            .order_by(Backup.created_at.desc(), Backup.id.desc())
            .limit(page_size)
            .offset(offset),
        )

        return list(result.scalars().all())

    async def create_pending(
        self,
        user_id: int,
        backup_type: str,
        storage_format: str,
        telegram_chat_id: int,
        filename: str,
        schema_version: str,
    ) -> Backup:
        return await self.create_backup_record(
            user_id=user_id,
            backup_type=backup_type,
            storage_format=storage_format,
            telegram_chat_id=telegram_chat_id,
            filename=filename,
            schema_version=schema_version,
            status="pending",
            is_latest=False,
        )

    async def mark_sent(
        self,
        backup: Backup,
        telegram_message_id: int,
        file_id: str,
        file_unique_id: str,
        sha256: str,
        file_size: int,
    ) -> Backup:
        return await self.mark_backup_sent(
            backup_id=backup.id,
            telegram_message_id=telegram_message_id,
            file_id=file_id,
            file_unique_id=file_unique_id,
            sha256=sha256,
            file_size=file_size,
        )

    async def mark_failed(self, backup: Backup, error_message: str) -> Backup:
        return await self.mark_backup_failed(
            backup_id=backup.id,
            error_message=error_message,
        )

    async def _get_backup_by_id(self, backup_id: int) -> Backup | None:
        result = await self.session.execute(
            select(Backup).where(Backup.id == backup_id),
        )

        return result.scalar_one_or_none()
