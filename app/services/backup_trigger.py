from __future__ import annotations

from typing import Any

from loguru import logger


class BackupTriggerService:
    async def trigger_user_backup(
        self,
        user_id: int,
        reason: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        logger.bind(
            user_id=user_id,
            reason=reason,
            metadata=metadata or {},
        ).info("backup_trigger_registered")