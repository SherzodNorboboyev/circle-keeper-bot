from __future__ import annotations

import copy
import hashlib
import json
import os
import sqlite3
import tempfile
from dataclasses import dataclass
from datetime import UTC, date, datetime
from io import BytesIO
from pathlib import Path
from typing import Any

from aiogram import Bot
from aiogram.types import BufferedInputFile
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Person, Relationship, Reminder, UserSetting
from app.db.repositories.backups import BackupsRepository
from app.db.repositories.users import UserRepository
from app.services.i18n import I18nService


SCHEMA_VERSION = "1.0.0"
APP_VERSION = "1.0.0"


@dataclass(frozen=True)
class BackupFile:
    payload: dict[str, Any]
    content: bytes
    filename: str
    sha256: str
    file_size: int


@dataclass(frozen=True)
class BackupSendResult:
    success: bool
    backup_id: int
    filename: str
    sha256: str | None
    file_size: int | None
    error_message: str | None = None


class BackupService:
    def __init__(
        self,
        session: AsyncSession,
        bot: Bot,
        i18n: I18nService | None = None,
        default_language: str = "uz",
    ) -> None:
        self.session = session
        self.bot = bot
        self.i18n = i18n or I18nService(default_lang=default_language)
        self.default_language = default_language
        self.repository = BackupsRepository(session)

    async def create_and_send_json_backup(
        self,
        user_id: int,
        backup_type: str = "auto",
        reason: str = "manual",
        notify_on_failure: bool = True,
    ) -> BackupSendResult:
        user = await UserRepository(self.session).get_by_id(user_id=user_id)

        if user is None:
            raise ValueError(f"User not found: {user_id}")

        backup_file = await self.generate_json_backup_file(user_id=user_id)

        backup = await self.repository.create_backup_record(
            user_id=user_id,
            backup_type=backup_type,
            storage_format="json",
            telegram_chat_id=user.chat_id,
            filename=backup_file.filename,
            sha256=backup_file.sha256,
            file_size=backup_file.file_size,
            schema_version=SCHEMA_VERSION,
            status="pending",
            is_latest=False,
        )

        try:
            message = await self.bot.send_document(
                chat_id=user.chat_id,
                document=BufferedInputFile(
                    backup_file.content,
                    filename=backup_file.filename,
                ),
                caption=f"Backup: {reason}",
            )

            if message.document is None:
                raise RuntimeError("Telegram message does not contain document metadata.")

            sent_backup = await self.repository.mark_backup_sent(
                backup_id=backup.id,
                telegram_message_id=message.message_id,
                file_id=message.document.file_id,
                file_unique_id=message.document.file_unique_id,
                sha256=backup_file.sha256,
                file_size=backup_file.file_size,
            )

            return BackupSendResult(
                success=True,
                backup_id=sent_backup.id,
                filename=sent_backup.filename,
                sha256=sent_backup.sha256,
                file_size=sent_backup.file_size,
            )
        except Exception as exc:
            error_message = str(exc)
            await self.repository.mark_backup_failed(
                backup_id=backup.id,
                error_message=error_message,
            )

            logger.exception(
                "backup_send_failed",
                user_id=user_id,
                backup_id=backup.id,
                reason=reason,
            )

            if notify_on_failure:
                await self._notify_auto_backup_failure(
                    chat_id=user.chat_id,
                    lang=user.language_code or self.default_language,
                )

            return BackupSendResult(
                success=False,
                backup_id=backup.id,
                filename=backup.filename,
                sha256=backup.sha256,
                file_size=backup.file_size,
                error_message=error_message,
            )

    async def create_and_send_sqlite_backup(
        self,
        user_id: int,
        backup_type: str = "manual_export",
        reason: str = "manual_sqlite_export",
    ) -> BackupSendResult:
        user = await UserRepository(self.session).get_by_id(user_id=user_id)

        if user is None:
            raise ValueError(f"User not found: {user_id}")

        backup_file = await self.generate_sqlite_backup_file(user_id=user_id)

        backup = await self.repository.create_backup_record(
            user_id=user_id,
            backup_type=backup_type,
            storage_format="sqlite",
            telegram_chat_id=user.chat_id,
            filename=backup_file.filename,
            sha256=backup_file.sha256,
            file_size=backup_file.file_size,
            schema_version=SCHEMA_VERSION,
            status="pending",
            is_latest=False,
        )

        try:
            message = await self.bot.send_document(
                chat_id=user.chat_id,
                document=BufferedInputFile(
                    backup_file.content,
                    filename=backup_file.filename,
                ),
                caption=f"SQLite backup: {reason}",
            )

            if message.document is None:
                raise RuntimeError("Telegram message does not contain document metadata.")

            sent_backup = await self.repository.mark_backup_sent(
                backup_id=backup.id,
                telegram_message_id=message.message_id,
                file_id=message.document.file_id,
                file_unique_id=message.document.file_unique_id,
                sha256=backup_file.sha256,
                file_size=backup_file.file_size,
            )

            return BackupSendResult(
                success=True,
                backup_id=sent_backup.id,
                filename=sent_backup.filename,
                sha256=sent_backup.sha256,
                file_size=sent_backup.file_size,
            )
        except Exception as exc:
            error_message = str(exc)
            await self.repository.mark_backup_failed(
                backup_id=backup.id,
                error_message=error_message,
            )
            return BackupSendResult(
                success=False,
                backup_id=backup.id,
                filename=backup.filename,
                sha256=backup.sha256,
                file_size=backup.file_size,
                error_message=error_message,
            )

    async def generate_json_backup_file(self, user_id: int) -> BackupFile:
        payload = await self.generate_backup_payload(user_id=user_id)

        sha256 = self.calculate_payload_checksum(payload)
        payload["metadata"]["sha256"] = sha256

        content = json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ).encode("utf-8")

        filename = self.build_backup_filename(
            generated_at=datetime.now(UTC),
            extension="json",
        )

        return BackupFile(
            payload=payload,
            content=content,
            filename=filename,
            sha256=sha256,
            file_size=len(content),
        )

    async def generate_sqlite_backup_file(self, user_id: int) -> BackupFile:
        json_backup = await self.generate_json_backup_file(user_id=user_id)
        generated_at = datetime.now(UTC)
        filename = self.build_backup_filename(generated_at=generated_at, extension="sqlite")

        with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as temporary_file:
            temporary_path = Path(temporary_file.name)

        try:
            connection = sqlite3.connect(str(temporary_path))
            try:
                connection.execute(
                    "CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)",
                )
                connection.execute(
                    "CREATE TABLE backup_json (id INTEGER PRIMARY KEY CHECK (id = 1), payload TEXT NOT NULL)",
                )
                connection.execute(
                    "INSERT INTO metadata(key, value) VALUES (?, ?)",
                    ("schema_version", SCHEMA_VERSION),
                )
                connection.execute(
                    "INSERT INTO metadata(key, value) VALUES (?, ?)",
                    ("generated_at", self.format_datetime_z(generated_at)),
                )
                connection.execute(
                    "INSERT INTO backup_json(id, payload) VALUES (1, ?)",
                    (json_backup.content.decode("utf-8"),),
                )
                connection.commit()
            finally:
                connection.close()

            content = temporary_path.read_bytes()
        finally:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                logger.warning("temporary_sqlite_backup_delete_failed", path=str(temporary_path))

        sha256 = self.calculate_sha256(content)

        return BackupFile(
            payload=json_backup.payload,
            content=content,
            filename=filename,
            sha256=sha256,
            file_size=len(content),
        )

    async def generate_backup_payload(self, user_id: int) -> dict[str, Any]:
        user = await UserRepository(self.session).get_by_id(user_id=user_id)

        if user is None:
            raise ValueError(f"User not found: {user_id}")

        people = await self._select_all_people(user_id=user_id)
        relationships = await self._select_all_relationships(user_id=user_id)
        reminders = await self._select_all_reminders(user_id=user_id)
        settings = await self._select_all_settings(user_id=user_id)

        payload: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "backup_type": "user_full",
            "generated_at": self.format_datetime_z(datetime.now(UTC)),
            "user": {
                "telegram_user_id": user.telegram_user_id,
                "language_code": user.language_code,
                "timezone": user.timezone,
            },
            "people": [self.serialize_person(person) for person in people],
            "relationships": [
                self.serialize_relationship(relationship)
                for relationship in relationships
            ],
            "reminders": [
                self.serialize_reminder(reminder)
                for reminder in reminders
            ],
            "settings": [
                self.serialize_setting(setting)
                for setting in settings
            ],
            "metadata": {
                "app_version": APP_VERSION,
                "sha256": None,
            },
        }

        return payload

    async def _select_all_people(self, user_id: int) -> list[Person]:
        result = await self.session.execute(
            select(Person)
            .where(Person.user_id == user_id)
            .order_by(Person.id.asc()),
        )

        return list(result.scalars().all())

    async def _select_all_relationships(self, user_id: int) -> list[Relationship]:
        result = await self.session.execute(
            select(Relationship)
            .where(Relationship.user_id == user_id)
            .order_by(Relationship.id.asc()),
        )

        return list(result.scalars().all())

    async def _select_all_reminders(self, user_id: int) -> list[Reminder]:
        result = await self.session.execute(
            select(Reminder)
            .where(Reminder.user_id == user_id)
            .order_by(Reminder.id.asc()),
        )

        return list(result.scalars().all())

    async def _select_all_settings(self, user_id: int) -> list[UserSetting]:
        result = await self.session.execute(
            select(UserSetting)
            .where(UserSetting.user_id == user_id)
            .order_by(UserSetting.key.asc()),
        )

        return list(result.scalars().all())

    @classmethod
    def calculate_payload_checksum(cls, payload: dict[str, Any]) -> str:
        payload_for_checksum = copy.deepcopy(payload)
        payload_for_checksum.setdefault("metadata", {})
        payload_for_checksum["metadata"]["sha256"] = None

        content = json.dumps(
            payload_for_checksum,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

        return cls.calculate_sha256(content)

    @staticmethod
    def calculate_sha256(content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    @staticmethod
    def build_backup_filename(
        generated_at: datetime,
        extension: str,
    ) -> str:
        generated_at = generated_at.astimezone(UTC)
        timestamp = generated_at.strftime("%Y-%m-%d_%H-%M")
        return f"networking_backup_{timestamp}.{extension}"

    @staticmethod
    def format_datetime_z(value: datetime) -> str:
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)

        return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    @staticmethod
    def serialize_datetime(value: datetime | None) -> str | None:
        if value is None:
            return None

        if value.tzinfo is None:
            return value.replace(microsecond=0).isoformat()

        return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    @staticmethod
    def serialize_date(value: date | None) -> str | None:
        if value is None:
            return None

        return value.isoformat()

    @classmethod
    def serialize_person(cls, person: Person) -> dict[str, Any]:
        return {
            "id": person.id,
            "first_name": person.first_name,
            "last_name": person.last_name,
            "middle_name": person.middle_name,
            "nickname": person.nickname,
            "phone": person.phone,
            "telegram_username": person.telegram_username,
            "birth_date": cls.serialize_date(person.birth_date),
            "birth_year_known": person.birth_year_known,
            "birth_month": person.birth_month,
            "birth_day": person.birth_day,
            "gender": person.gender,
            "category": person.category,
            "custom_category": person.custom_category,
            "note": person.note,
            "how_met": person.how_met,
            "location": person.location,
            "workplace": person.workplace,
            "education_place": person.education_place,
            "created_at": cls.serialize_datetime(person.created_at),
            "updated_at": cls.serialize_datetime(person.updated_at),
            "deleted_at": cls.serialize_datetime(person.deleted_at),
        }

    @classmethod
    def serialize_relationship(cls, relationship: Relationship) -> dict[str, Any]:
        return {
            "id": relationship.id,
            "from_person_id": relationship.from_person_id,
            "to_person_id": relationship.to_person_id,
            "relationship_type": relationship.relationship_type,
            "custom_label": relationship.custom_label,
            "note": relationship.note,
            "is_bidirectional": relationship.is_bidirectional,
            "reverse_relationship_type": relationship.reverse_relationship_type,
            "created_at": cls.serialize_datetime(relationship.created_at),
            "updated_at": cls.serialize_datetime(relationship.updated_at),
            "deleted_at": cls.serialize_datetime(relationship.deleted_at),
        }

    @classmethod
    def serialize_reminder(cls, reminder: Reminder) -> dict[str, Any]:
        return {
            "id": reminder.id,
            "person_id": reminder.person_id,
            "reminder_type": reminder.reminder_type,
            "days_before": reminder.days_before,
            "remind_time_local": reminder.remind_time_local.strftime("%H:%M"),
            "enabled": reminder.enabled,
            "created_at": cls.serialize_datetime(reminder.created_at),
            "updated_at": cls.serialize_datetime(reminder.updated_at),
        }

    @staticmethod
    def serialize_setting(setting: UserSetting) -> dict[str, Any]:
        return {
            "key": setting.key,
            "value": setting.value,
        }

    async def _notify_auto_backup_failure(self, chat_id: int, lang: str) -> None:
        try:
            await self.bot.send_message(
                chat_id=chat_id,
                text=self.i18n.t("backup.auto_failed", lang=lang),
            )
        except Exception:
            logger.exception("backup_failure_notification_failed", chat_id=chat_id)