from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Person, utc_now


class PeopleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        user_id: int,
        first_name: str,
        last_name: str | None = None,
        middle_name: str | None = None,
        nickname: str | None = None,
        phone: str | None = None,
        telegram_username: str | None = None,
        birth_date: date | None = None,
        birth_year_known: bool = False,
        birth_month: int | None = None,
        birth_day: int | None = None,
        gender: str | None = None,
        category: str | None = None,
        custom_category: str | None = None,
        note: str | None = None,
        how_met: str | None = None,
        location: str | None = None,
        workplace: str | None = None,
        education_place: str | None = None,
    ) -> Person:
        person = Person(
            user_id=user_id,
            first_name=first_name,
            last_name=last_name,
            middle_name=middle_name,
            nickname=nickname,
            phone=phone,
            telegram_username=telegram_username,
            birth_date=birth_date,
            birth_year_known=birth_year_known,
            birth_month=birth_month,
            birth_day=birth_day,
            gender=gender,
            category=category,
            custom_category=custom_category,
            note=note,
            how_met=how_met,
            location=location,
            workplace=workplace,
            education_place=education_place,
        )

        self.session.add(person)
        await self.session.flush()
        return person

    async def get_by_id(self, user_id: int, person_id: int, include_deleted: bool = False) -> Person | None:
        statement = select(Person).where(
            Person.id == person_id,
            Person.user_id == user_id,
        )

        if not include_deleted:
            statement = statement.where(Person.deleted_at.is_(None))

        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def list_active(self, user_id: int, limit: int = 20, offset: int = 0) -> list[Person]:
        result = await self.session.execute(
            select(Person)
            .where(
                Person.user_id == user_id,
                Person.deleted_at.is_(None),
            )
            .order_by(Person.first_name.asc(), Person.last_name.asc())
            .limit(limit)
            .offset(offset),
        )
        return list(result.scalars().all())

    async def soft_delete(self, user_id: int, person_id: int) -> bool:
        person = await self.get_by_id(user_id=user_id, person_id=person_id)

        if person is None:
            return False

        person.deleted_at = utc_now()
        await self.session.flush()
        return True