from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditLog, Person, Relationship, Reminder, ReminderLog, UserSetting
from app.services.backup_service import BackupService, SCHEMA_VERSION


@dataclass(frozen=True)
class RestorePreview:
    generated_at: str | None
    people_count: int
    relationships_count: int
    reminders_count: int
    settings_count: int
    schema_version: str


@dataclass(frozen=True)
class RestoreResult:
    people_count: int
    relationships_count: int
    reminders_count: int
    settings_count: int


class RestoreValidationError(ValueError):
    def __init__(self, message_key: str, detail: str | None = None) -> None:
        self.message_key = message_key
        self.detail = detail
        super().__init__(message_key)


class RestoreService:
    MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024

    def validate_document(
        self,
        filename: str,
        content_type: str | None,
        file_size: int,
    ) -> None:
        if not filename.lower().endswith(".json"):
            raise RestoreValidationError("restore.invalid_file")

        if file_size > self.MAX_FILE_SIZE_BYTES:
            raise RestoreValidationError("restore.invalid_file")

        allowed_content_types = {
            None,
            "",
            "application/json",
            "text/plain",
            "application/octet-stream",
        }

        if content_type not in allowed_content_types:
            raise RestoreValidationError("restore.invalid_file")

    def parse_backup(self, content: bytes) -> dict[str, Any]:
        try:
            payload = json.loads(content.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RestoreValidationError("restore.invalid_file") from exc

        if not isinstance(payload, dict):
            raise RestoreValidationError("restore.invalid_file")

        if payload.get("schema_version") != SCHEMA_VERSION:
            raise RestoreValidationError("restore.invalid_file")

        self.verify_checksum(payload)

        return payload

    def build_preview(self, payload: dict[str, Any]) -> RestorePreview:
        return RestorePreview(
            generated_at=payload.get("generated_at"),
            people_count=len(payload.get("people") or []),
            relationships_count=len(payload.get("relationships") or []),
            reminders_count=len(payload.get("reminders") or []),
            settings_count=len(payload.get("settings") or []),
            schema_version=str(payload.get("schema_version") or ""),
        )

    async def replace_all(
        self,
        session: AsyncSession,
        user_id: int,
        payload: dict[str, Any],
    ) -> RestoreResult:
        preview = self.build_preview(payload)

        async with session.begin_nested():
            await self._delete_existing_user_data(
                session=session,
                user_id=user_id,
            )

            person_id_map = await self._restore_people(
                session=session,
                user_id=user_id,
                people=payload.get("people") or [],
            )
            relationships_count = await self._restore_relationships(
                session=session,
                user_id=user_id,
                relationships=payload.get("relationships") or [],
                person_id_map=person_id_map,
            )
            reminders_count = await self._restore_reminders(
                session=session,
                user_id=user_id,
                reminders=payload.get("reminders") or [],
                person_id_map=person_id_map,
            )
            settings_count = await self._restore_settings(
                session=session,
                user_id=user_id,
                settings=payload.get("settings") or [],
            )

            audit_log = AuditLog(
                user_id=user_id,
                action="restore.replace_all",
                entity_type="restore",
                entity_id=None,
                old_value=None,
                new_value={
                    "schema_version": preview.schema_version,
                    "generated_at": preview.generated_at,
                    "people_count": len(person_id_map),
                    "relationships_count": relationships_count,
                    "reminders_count": reminders_count,
                    "settings_count": settings_count,
                },
            )
            session.add(audit_log)

        return RestoreResult(
            people_count=len(person_id_map),
            relationships_count=relationships_count,
            reminders_count=reminders_count,
            settings_count=settings_count,
        )

    @staticmethod
    def verify_checksum(payload: dict[str, Any]) -> None:
        metadata = payload.get("metadata")

        if not isinstance(metadata, dict):
            return

        expected_sha256 = metadata.get("sha256")

        if not expected_sha256:
            return

        payload_for_checksum = copy.deepcopy(payload)
        payload_for_checksum["metadata"]["sha256"] = None

        actual_sha256 = BackupService.calculate_payload_checksum(payload_for_checksum)

        if actual_sha256 != expected_sha256:
            raise RestoreValidationError("restore.invalid_file", detail="checksum_mismatch")

    async def _delete_existing_user_data(
        self,
        session: AsyncSession,
        user_id: int,
    ) -> None:
        await session.execute(delete(ReminderLog).where(ReminderLog.user_id == user_id))
        await session.execute(delete(Reminder).where(Reminder.user_id == user_id))
        await session.execute(delete(Relationship).where(Relationship.user_id == user_id))
        await session.execute(delete(Person).where(Person.user_id == user_id))
        await session.execute(delete(UserSetting).where(UserSetting.user_id == user_id))

    async def _restore_people(
        self,
        session: AsyncSession,
        user_id: int,
        people: list[dict[str, Any]],
    ) -> dict[int, int]:
        person_id_map: dict[int, int] = {}

        for item in people:
            old_id = int(item["id"])

            person = Person(
                user_id=user_id,
                first_name=item["first_name"],
                last_name=item.get("last_name"),
                middle_name=item.get("middle_name"),
                nickname=item.get("nickname"),
                phone=item.get("phone"),
                telegram_username=item.get("telegram_username"),
                birth_date=self.parse_date(item.get("birth_date")),
                birth_year_known=bool(item.get("birth_year_known")),
                birth_month=item.get("birth_month"),
                birth_day=item.get("birth_day"),
                gender=item.get("gender"),
                category=item.get("category"),
                custom_category=item.get("custom_category"),
                note=item.get("note"),
                how_met=item.get("how_met"),
                location=item.get("location"),
                workplace=item.get("workplace"),
                education_place=item.get("education_place"),
                created_at=self.parse_datetime(item.get("created_at")),
                updated_at=self.parse_datetime(item.get("updated_at")),
                deleted_at=self.parse_datetime(item.get("deleted_at")),
            )

            session.add(person)
            await session.flush()
            person_id_map[old_id] = person.id

        return person_id_map

    async def _restore_relationships(
        self,
        session: AsyncSession,
        user_id: int,
        relationships: list[dict[str, Any]],
        person_id_map: dict[int, int],
    ) -> int:
        created_count = 0

        for item in relationships:
            old_from_person_id = int(item["from_person_id"])
            old_to_person_id = int(item["to_person_id"])

            if old_from_person_id not in person_id_map or old_to_person_id not in person_id_map:
                continue

            relationship = Relationship(
                user_id=user_id,
                from_person_id=person_id_map[old_from_person_id],
                to_person_id=person_id_map[old_to_person_id],
                relationship_type=item["relationship_type"],
                custom_label=item.get("custom_label"),
                note=item.get("note"),
                is_bidirectional=bool(item.get("is_bidirectional")),
                reverse_relationship_type=item.get("reverse_relationship_type"),
                created_at=self.parse_datetime(item.get("created_at")),
                updated_at=self.parse_datetime(item.get("updated_at")),
                deleted_at=self.parse_datetime(item.get("deleted_at")),
            )

            session.add(relationship)
            created_count += 1

        await session.flush()
        return created_count

    async def _restore_reminders(
        self,
        session: AsyncSession,
        user_id: int,
        reminders: list[dict[str, Any]],
        person_id_map: dict[int, int],
    ) -> int:
        created_count = 0

        for item in reminders:
            old_person_id = int(item["person_id"])

            if old_person_id not in person_id_map:
                continue

            reminder = Reminder(
                user_id=user_id,
                person_id=person_id_map[old_person_id],
                reminder_type=item.get("reminder_type") or "birthday",
                days_before=int(item.get("days_before") or 1),
                remind_time_local=self.parse_time(item.get("remind_time_local") or "09:00"),
                enabled=bool(item.get("enabled")),
                created_at=self.parse_datetime(item.get("created_at")),
                updated_at=self.parse_datetime(item.get("updated_at")),
            )

            session.add(reminder)
            created_count += 1

        await session.flush()
        return created_count

    async def _restore_settings(
        self,
        session: AsyncSession,
        user_id: int,
        settings: list[dict[str, Any]],
    ) -> int:
        created_count = 0

        for item in settings:
            setting = UserSetting(
                user_id=user_id,
                key=item["key"],
                value=item.get("value") or {"value": None},
            )

            session.add(setting)
            created_count += 1

        await session.flush()
        return created_count

    @staticmethod
    def parse_date(value: str | None) -> date | None:
        if not value:
            return None

        return date.fromisoformat(value)

    @staticmethod
    def parse_datetime(value: str | None) -> datetime | None:
        if not value:
            return None

        normalized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)

    @staticmethod
    def parse_time(value: str):
        from datetime import time

        hour, minute = value.split(":", maxsplit=1)
        return time(hour=int(hour), minute=int(minute))