# Networking Relationship Manager Telegram Bot

Telegram ichida shaxsiy networking bazasini yuritish uchun Python backend Telegram bot. Bot odamlar profili, relationship graph, tug‘ilgan kun eslatmalari, backup/restore, Excel import/export va ko‘p tilli interfeysni qo‘llab-quvvatlaydi.

## Features

- User onboarding: `/start`, `/language`, `/help`
- Person management: `/add`, `/list`, `/search`, `/view`, `/edit`, `/delete`
- Relationship graph: `/relationships`
- Farzandni alohida person sifatida qo‘shish: `/add_child`
- Birthday reminder: `/birthdays`
- User settings: `/settings`
- JSON backup/export: `/export`
- JSON restore: `/import`
- Excel template: `/excel_template`
- Excel import: `/import_excel`
- Excel export: `/export_excel`
- Admin aggregate stats: `/stats`
- Disabled placeholder: `/delete_my_data`

## Tech stack

- Python 3.12+
- aiogram 3.x
- SQLAlchemy 2.x async ORM
- Alembic
- PostgreSQL production uchun
- SQLite local/dev uchun
- pydantic-settings
- loguru
- openpyxl
- APScheduler
- Docker
- pytest, pytest-asyncio
- ruff, black, mypy

## Project structure

```text
app/
  bot/
    handlers/
    keyboards/
    middlewares/
    states/
  db/
    repositories/
  services/
  scripts/
  locales/
  config.py
  logging.py
  main.py
tests/
alembic/
.github/workflows/
Dockerfile
docker-compose.yml
.env.example
README.md
requirements.txt
pyproject.toml