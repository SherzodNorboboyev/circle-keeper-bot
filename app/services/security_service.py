from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy.engine.url import make_url

from app.config import Settings, get_settings

FORMULA_PREFIXES = ("=", "+", "-", "@")


class SecurityValidationError(ValueError):
    def __init__(self, message_key: str, detail: str | None = None) -> None:
        self.message_key = message_key
        self.detail = detail
        super().__init__(message_key)


@dataclass(frozen=True)
class UploadValidationResult:
    filename: str
    extension: str
    file_size: int


class SecurityService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def validate_excel_upload(
        self,
        filename: str,
        content_type: str | None,
        file_size: int,
    ) -> UploadValidationResult:
        return self._validate_upload(
            filename=filename,
            content_type=content_type,
            file_size=file_size,
            allowed_extensions={".xlsx"},
            allowed_content_types={
                None,
                "",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "application/octet-stream",
            },
            max_file_size=self.settings.excel_max_file_size_bytes,
            invalid_extension_key="excel.invalid_extension",
            file_too_large_key="excel.file_too_large",
        )

    def validate_json_backup_upload(
        self,
        filename: str,
        content_type: str | None,
        file_size: int,
    ) -> UploadValidationResult:
        return self._validate_upload(
            filename=filename,
            content_type=content_type,
            file_size=file_size,
            allowed_extensions={".json"},
            allowed_content_types={
                None,
                "",
                "application/json",
                "text/plain",
                "application/octet-stream",
            },
            max_file_size=self.settings.backup_max_file_size_bytes,
            invalid_extension_key="restore.invalid_file",
            file_too_large_key="restore.invalid_file",
        )

    def validate_sqlite_restore_upload(
        self,
        filename: str,
        content_type: str | None,
        file_size: int,
    ) -> UploadValidationResult:
        if self.settings.ENV == "production":
            raise SecurityValidationError("restore.invalid_file", detail="sqlite_restore_disabled_in_production")

        return self._validate_upload(
            filename=filename,
            content_type=content_type,
            file_size=file_size,
            allowed_extensions={".sqlite", ".sqlite3", ".db"},
            allowed_content_types={
                None,
                "",
                "application/octet-stream",
                "application/vnd.sqlite3",
            },
            max_file_size=self.settings.backup_max_file_size_bytes,
            invalid_extension_key="restore.invalid_file",
            file_too_large_key="restore.invalid_file",
        )

    @staticmethod
    def is_formula_like(value: Any) -> bool:
        if not isinstance(value, str):
            return False

        return value.strip().startswith(FORMULA_PREFIXES)

    @staticmethod
    def reject_formula_like(value: Any, message_key: str = "excel.import_failed") -> None:
        if SecurityService.is_formula_like(value):
            raise SecurityValidationError(message_key, detail="formula_like_text")

    @staticmethod
    def escape_formula_like(value: Any) -> Any:
        if isinstance(value, str) and value.startswith(FORMULA_PREFIXES):
            return "'" + value

        return value

    @staticmethod
    def mask_secret(value: str | None, visible_chars: int = 4) -> str:
        if not value:
            return ""

        if len(value) <= visible_chars:
            return "***"

        return value[:visible_chars] + "***"

    @staticmethod
    def mask_database_url(database_url: str) -> str:
        try:
            url = make_url(database_url)
        except Exception:
            return "***"

        if url.password:
            return str(url.set(password="***"))

        return str(url)

    @staticmethod
    def sanitize_log_payload(payload: dict[str, Any]) -> dict[str, Any]:
        sensitive_keys = {
            "BOT_TOKEN",
            "DATABASE_URL",
            "WEBHOOK_SECRET",
            "bot_token",
            "database_url",
            "webhook_secret",
            "password",
            "token",
            "secret",
        }

        sanitized: dict[str, Any] = {}

        for key, value in payload.items():
            if key in sensitive_keys or key.lower() in sensitive_keys:
                sanitized[key] = "***"
            elif isinstance(value, dict):
                sanitized[key] = SecurityService.sanitize_log_payload(value)
            else:
                sanitized[key] = value

        return sanitized

    @staticmethod
    def assert_same_user_id(entity_user_id: int, current_user_id: int) -> None:
        if entity_user_id != current_user_id:
            raise SecurityValidationError("security.forbidden", detail="cross_user_access")

    def _validate_upload(
        self,
        filename: str,
        content_type: str | None,
        file_size: int,
        allowed_extensions: set[str],
        allowed_content_types: set[str | None],
        max_file_size: int,
        invalid_extension_key: str,
        file_too_large_key: str,
    ) -> UploadValidationResult:
        filename = filename or ""
        extension = Path(filename).suffix.lower()

        if extension not in allowed_extensions:
            raise SecurityValidationError(invalid_extension_key, detail=extension)

        if content_type not in allowed_content_types:
            raise SecurityValidationError(invalid_extension_key, detail=content_type or "")

        if file_size > max_file_size:
            raise SecurityValidationError(file_too_large_key, detail=str(file_size))

        return UploadValidationResult(
            filename=filename,
            extension=extension,
            file_size=file_size,
        )
