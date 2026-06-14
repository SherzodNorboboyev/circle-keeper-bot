from __future__ import annotations

import asyncio

from loguru import logger

from app.config import get_settings
from app.db.repositories.people import PeopleRepository
from app.db.repositories.relationships import RelationshipsRepository
from app.db.repositories.users import UserRepository
from app.db.session import close_engine, init_db
from app.logging import setup_logging
from app.services.people_service import PeopleService
from app.services.relationship_service import RelationshipService


DEMO_TELEGRAM_USER_ID = 100000001


async def main() -> None:
    settings = get_settings()
    setup_logging(env=settings.ENV, level=settings.LOG_LEVEL)

    if settings.ENV == "production":
        raise RuntimeError("seed_demo_data.py must not be used in production.")

    session_maker = init_db(settings.DATABASE_URL, echo=settings.DB_ECHO)

    async with session_maker() as session:
        user_repository = UserRepository(session)
        people_repository = PeopleRepository(session)

        user = await user_repository.upsert_from_telegram(
            telegram_user_id=DEMO_TELEGRAM_USER_ID,
            chat_id=DEMO_TELEGRAM_USER_ID,
            username="demo_user",
            first_name="Demo",
            last_name="User",
            language_code="uz",
            is_admin=True,
            default_timezone=settings.DEFAULT_TIMEZONE,
        )

        people_service = PeopleService()

        ali = await people_repository.create_person(
            user_id=user.id,
            data=people_service.prepare_create_data(
                {
                    "first_name": "Ali",
                    "last_name": "Valiyev",
                    "telegram_username": "ali_demo",
                    "birth_date": "1995-04-21",
                    "gender": "male",
                    "category": "friend",
                    "note": "Demo do‘st.",
                    "location": "Toshkent",
                    "workplace": "Example LLC",
                },
            ),
        )

        sardor = await people_repository.create_person(
            user_id=user.id,
            data=people_service.prepare_create_data(
                {
                    "first_name": "Sardor",
                    "last_name": "Karimov",
                    "birth_date": "04-22",
                    "gender": "male",
                    "category": "colleague",
                    "note": "Demo hamkasb.",
                    "location": "Toshkent",
                },
            ),
        )

        relationship_service = RelationshipService()
        await relationship_service.create_relationship(
            session=session,
            user_id=user.id,
            from_person_id=ali.id,
            to_person_id=sardor.id,
            relationship_type="friend",
        )

        await session.commit()

    await close_engine()
    logger.info("Demo data seeded.", telegram_user_id=DEMO_TELEGRAM_USER_ID)


if __name__ == "__main__":
    asyncio.run(main())