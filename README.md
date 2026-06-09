# Networking Relationship Manager Telegram Bot

Python 3.12+, aiogram 3.x, SQLAlchemy 2.x async ORM, Alembic, PostgreSQL/SQLite, pydantic-settings, loguru, Docker va pytest asosidagi Telegram bot foundation.

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
Dockerfile
docker-compose.yml
.env.example
README.md
requirements.txt
pytest.ini