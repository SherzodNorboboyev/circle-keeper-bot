from __future__ import annotations

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ImportErrorRecord, ImportJob


class ImportsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_job(
        self,
        user_id: int,
        import_type: str,
        filename: str,
        file_size: int,
    ) -> ImportJob:
        import_job = ImportJob(
            user_id=user_id,
            import_type=import_type,
            filename=filename,
            file_size=file_size,
            status="pending",
        )

        self.session.add(import_job)
        await self.session.flush()
        return import_job

    async def set_status(
        self,
        import_job: ImportJob,
        status: str,
        completed_at: datetime | None = None,
        error_message: str | None = None,
    ) -> ImportJob:
        import_job.status = status
        import_job.completed_at = completed_at
        import_job.error_message = error_message

        await self.session.flush()
        return import_job

    async def add_error(
        self,
        import_job_id: int,
        error_code: str,
        error_message: str,
        sheet_name: str | None = None,
        row_number: int | None = None,
        column_name: str | None = None,
        suggested_fix: str | None = None,
    ) -> ImportErrorRecord:
        error = ImportErrorRecord(
            import_job_id=import_job_id,
            sheet_name=sheet_name,
            row_number=row_number,
            column_name=column_name,
            error_code=error_code,
            error_message=error_message,
            suggested_fix=suggested_fix,
        )

        self.session.add(error)
        await self.session.flush()
        return error