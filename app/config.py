from __future__ import annotations

import json
from functools import lru_cache
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


SupportedLanguage = Literal["uz", "ru", "en"]
Environment = Literal["development", "test", "production"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    ENV: Environment = "development"
    LOG_LEVEL: str = "INFO"

    BOT_TOKEN: SecretStr | None = None
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/dev.sqlite3"

    ADMIN_TELEGRAM_IDS: tuple[int, ...] = Field(default_factory=tuple)

    DEFAULT_LANGUAGE: SupportedLanguage = "uz"
    DEFAULT_TIMEZONE: str = "Asia/Tashkent"

    USE_WEBHOOK: bool = False
    WEBHOOK_URL: str | None = None
    WEBHOOK_SECRET: SecretStr | None = None

    HOST: str = "0.0.0.0"
    PORT: int = 8080

    DB_ECHO: bool = False

    ENABLE_SCHEDULER: bool = False
    REMINDER_CHECK_INTERVAL_MINUTES: int = 5
    REMINDER_SCHEDULER_LOOKBACK_MINUTES: int = 10
    REMINDER_SCRIPT_LOOKBACK_MINUTES: int = 1440

    @field_validator("DATABASE_URL")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        value = value.strip()

        if value.startswith("postgres://"):
            value = "postgresql://" + value.removeprefix("postgres://")

        if value.startswith("postgresql://"):
            return "postgresql+asyncpg://" + value.removeprefix("postgresql://")

        if value.startswith("sqlite://") and not value.startswith("sqlite+"):
            return "sqlite+aiosqlite://" + value.removeprefix("sqlite://")

        return value

    @field_validator("ADMIN_TELEGRAM_IDS", mode="before")
    @classmethod
    def parse_admin_telegram_ids(cls, value: object) -> tuple[int, ...]:
        if value is None:
            return ()

        if isinstance(value, int):
            return (value,)

        if isinstance(value, str):
            raw_value = value.strip()
            if not raw_value:
                return ()

            if raw_value.startswith("["):
                parsed = json.loads(raw_value)
                return tuple(int(item) for item in parsed)

            return tuple(
                int(item.strip())
                for item in raw_value.split(",")
                if item.strip()
            )

        if isinstance(value, list | tuple | set):
            return tuple(int(item) for item in value)

        raise TypeError("ADMIN_TELEGRAM_IDS must be a comma-separated string or list of integers.")

    @field_validator("WEBHOOK_URL", mode="before")
    @classmethod
    def empty_webhook_url_to_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("WEBHOOK_SECRET", mode="before")
    @classmethod
    def empty_webhook_secret_to_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("DEFAULT_TIMEZONE")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"Unknown timezone: {value}") from exc
        return value

    @field_validator(
        "REMINDER_CHECK_INTERVAL_MINUTES",
        "REMINDER_SCHEDULER_LOOKBACK_MINUTES",
        "REMINDER_SCRIPT_LOOKBACK_MINUTES",
    )
    @classmethod
    def validate_positive_minutes(cls, value: int) -> int:
        if value < 1:
            raise ValueError("Reminder minute settings must be greater than zero.")
        return value

    @model_validator(mode="after")
    def validate_webhook_configuration(self) -> Settings:
        if self.USE_WEBHOOK and not self.WEBHOOK_URL:
            raise ValueError("WEBHOOK_URL is required when USE_WEBHOOK=true.")
        return self

    @property
    def bot_token(self) -> str:
        token = self.BOT_TOKEN.get_secret_value() if self.BOT_TOKEN else ""
        if not token:
            raise RuntimeError("BOT_TOKEN is required to start the Telegram bot.")
        return token

    @property
    def webhook_secret(self) -> str | None:
        if not self.WEBHOOK_SECRET:
            return None

        secret = self.WEBHOOK_SECRET.get_secret_value()
        return secret or None

    @property
    def admin_ids_set(self) -> set[int]:
        return set(self.ADMIN_TELEGRAM_IDS)


@lru_cache
def get_settings() -> Settings:
    return Settings()