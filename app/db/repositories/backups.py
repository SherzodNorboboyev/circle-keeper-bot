from __future__ import annotations

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Backup


class BackupsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_pending(
        self,
        user_id: int,
        backup_type: str,
        storage_format: str,
        telegram_chat_id: int,
        filename: str,
        schema_version: str,
    ) -> Backup:
        backup = Backup(
            user_id=user_id,
            backup_type=backup_type,
            storage_format=storage_format,
            telegram_chat_id=telegram_chat_id,
            filename=filename,
            schema_version=schema_version,
            status="pending",
            is_latest=False,
        )

        self.session.add(backup)
        await self.session.flush()
        return backup

    async def mark_sent(
        self,
        backup: Backup,
        telegram_message_id: int,
        file_id: str,
        file_unique_id: str,
        sha256: str,
        file_size: int,
    ) -> Backup:
        await self.session.execute(
            update(Backup)
            .where(
                Backup.user_id == backup.user_id,
                Backup.is_latest.is_(True),
            )
            .values(is_latest=False),
        )

        backup.telegram_message_id = telegram_message_id
        backup.file_id = file_id
        backup.file_unique_id = file_unique_id
        backup.sha256 = sha256
        backup.file_size = file_size
        backup.status = "sent"
        backup.is_latest = True
        backup.error_message = None

        await self.session.flush()
        return backup

    async def mark_failed(self, backup: Backup, error_message: str) -> Backup:
        backup.status = "failed"
        backup.error_message = error_message[:5000]
        backup.is_latest = False

        await self.session.flush()
        return backup