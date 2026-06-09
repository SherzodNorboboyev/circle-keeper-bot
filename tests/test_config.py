from __future__ import annotations

from app.config import Settings


def test_config_loading_basic() -> None:
    settings = Settings(
        _env_file=None,
        ENV="test",
        BOT_TOKEN="123456:ABC",
        DATABASE_URL="sqlite:///./data/test.sqlite3",
        ADMIN_TELEGRAM_IDS="1, 2,3",
        DEFAULT_LANGUAGE="uz",
        DEFAULT_TIMEZONE="Asia/Tashkent",
        USE_WEBHOOK="true",
        WEBHOOK_URL="https://example.com/webhook",
        WEBHOOK_SECRET="secret",
    )

    assert settings.ENV == "test"
    assert settings.bot_token == "123456:ABC"
    assert settings.DATABASE_URL == "sqlite+aiosqlite:///./data/test.sqlite3"
    assert settings.ADMIN_TELEGRAM_IDS == (1, 2, 3)
    assert settings.DEFAULT_LANGUAGE == "uz"
    assert settings.DEFAULT_TIMEZONE == "Asia/Tashkent"
    assert settings.USE_WEBHOOK is True
    assert settings.WEBHOOK_URL == "https://example.com/webhook"
    assert settings.webhook_secret == "secret"


def test_config_normalizes_postgres_url() -> None:
    settings = Settings(
        _env_file=None,
        BOT_TOKEN="123456:ABC",
        DATABASE_URL="postgresql://user:password@localhost:5432/dbname",
    )

    assert settings.DATABASE_URL == "postgresql+asyncpg://user:password@localhost:5432/dbname"


def test_empty_admin_ids() -> None:
    settings = Settings(
        _env_file=None,
        BOT_TOKEN="123456:ABC",
        ADMIN_TELEGRAM_IDS="",
    )

    assert settings.ADMIN_TELEGRAM_IDS == ()