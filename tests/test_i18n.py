from __future__ import annotations

import json
from pathlib import Path

from app.services.i18n import I18nService


def write_json(path: Path, payload: dict[str, str]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )


def test_i18n_fallback_to_uz(tmp_path: Path) -> None:
    write_json(tmp_path / "uz.json", {"hello": "Salom"})
    write_json(tmp_path / "ru.json", {})
    write_json(tmp_path / "en.json", {})

    i18n = I18nService(locale_dir=tmp_path, default_lang="uz")

    assert i18n.t("hello", lang="ru") == "Salom"


def test_i18n_returns_key_when_missing_everywhere(tmp_path: Path) -> None:
    write_json(tmp_path / "uz.json", {})
    write_json(tmp_path / "ru.json", {})
    write_json(tmp_path / "en.json", {})

    i18n = I18nService(locale_dir=tmp_path, default_lang="uz")

    assert i18n.t("missing.key", lang="en") == "missing.key"


def test_i18n_formats_placeholders(tmp_path: Path) -> None:
    write_json(tmp_path / "uz.json", {"welcome": "Salom, {name}!"})
    write_json(tmp_path / "ru.json", {})
    write_json(tmp_path / "en.json", {"welcome": "Hello, {name}!"})

    i18n = I18nService(locale_dir=tmp_path, default_lang="uz")

    assert i18n.t("welcome", lang="en", name="Ali") == "Hello, Ali!"
