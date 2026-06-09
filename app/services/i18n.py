from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from loguru import logger


SUPPORTED_LANGUAGES = frozenset({"uz", "ru", "en"})


class I18nService:
    def __init__(self, locale_dir: Path | None = None, default_lang: str = "uz") -> None:
        self.locale_dir = locale_dir or Path(__file__).resolve().parents[1] / "locales"
        self.default_lang = default_lang if default_lang in SUPPORTED_LANGUAGES else "uz"
        self._translations: dict[str, dict[str, str]] = {}

        self.reload()

    def reload(self) -> None:
        loaded_translations: dict[str, dict[str, str]] = {}

        for lang in SUPPORTED_LANGUAGES:
            path = self.locale_dir / f"{lang}.json"

            if not path.exists():
                logger.bind(lang=lang, path=str(path)).warning("locale_file_missing")
                loaded_translations[lang] = {}
                continue

            with path.open("r", encoding="utf-8") as file:
                raw_data = json.load(file)

            loaded_translations[lang] = {
                str(key): str(value)
                for key, value in raw_data.items()
            }

        self._translations = loaded_translations

    def t(self, key: str, lang: str = "uz", **kwargs: Any) -> str:
        normalized_lang = lang if lang in SUPPORTED_LANGUAGES else self.default_lang

        text = self._translations.get(normalized_lang, {}).get(key)

        if text is None and normalized_lang != "uz":
            text = self._translations.get("uz", {}).get(key)

        if text is None:
            logger.bind(key=key, lang=lang).warning("translation_key_missing")
            return key

        try:
            return text.format(**kwargs)
        except KeyError as exc:
            logger.bind(key=key, lang=lang, missing_placeholder=str(exc)).warning(
                "translation_placeholder_missing",
            )
            return text