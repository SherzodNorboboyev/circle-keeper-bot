from __future__ import annotations

import pytest

from app.config import Settings
from app.services.security_service import SecurityService, SecurityValidationError


def test_mask_database_url_hides_password() -> None:
    masked = SecurityService.mask_database_url(
        "postgresql+asyncpg://user:secret_password@example.com:5432/dbname",
    )

    assert "secret_password" not in masked
    assert "***" in masked


def test_excel_upload_validation_accepts_xlsx() -> None:
    settings = Settings(
        _env_file=None,
        BOT_TOKEN="123456:ABC",
        EXCEL_MAX_FILE_SIZE_MB=5,
    )
    service = SecurityService(settings=settings)

    result = service.validate_excel_upload(
        filename="networking_import_template.xlsx",
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        file_size=1024,
    )

    assert result.extension == ".xlsx"


def test_excel_upload_validation_rejects_wrong_extension() -> None:
    settings = Settings(
        _env_file=None,
        BOT_TOKEN="123456:ABC",
    )
    service = SecurityService(settings=settings)

    with pytest.raises(SecurityValidationError) as exc:
        service.validate_excel_upload(
            filename="data.xls",
            content_type="application/octet-stream",
            file_size=1024,
        )

    assert exc.value.message_key == "excel.invalid_extension"


def test_backup_upload_validation_rejects_large_file() -> None:
    settings = Settings(
        _env_file=None,
        BOT_TOKEN="123456:ABC",
        BACKUP_MAX_FILE_SIZE_MB=1,
    )
    service = SecurityService(settings=settings)

    with pytest.raises(SecurityValidationError) as exc:
        service.validate_json_backup_upload(
            filename="backup.json",
            content_type="application/json",
            file_size=2 * 1024 * 1024,
        )

    assert exc.value.message_key == "restore.invalid_file"


def test_formula_detection_and_escape() -> None:
    assert SecurityService.is_formula_like("=HYPERLINK(\"x\")") is True
    assert SecurityService.is_formula_like("+SUM(A1:A2)") is True
    assert SecurityService.is_formula_like("normal text") is False
    assert SecurityService.escape_formula_like("@username") == "'@username"
    assert SecurityService.escape_formula_like("Ali") == "Ali"