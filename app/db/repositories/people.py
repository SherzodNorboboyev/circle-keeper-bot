from __future__ import annotations

from datetime import date
from typing import Any

import sqlalchemy as sa
from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Person, utc_now


class PeopleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_person(self, user_id: int, data: dict[str, Any]) -> Person:
        person = Person(user_id=user_id, **data)

        self.session.add(person)
        await self.session.flush()
        await self.session.refresh(person)

        return person

    async def get_person_by_id(
        self,
        user_id: int,
        person_id: int,
        include_deleted: bool = False,
    ) -> Person | None:
        statement = select(Person).where(
            Person.id == person_id,
            Person.user_id == user_id,
        )

        if not include_deleted:
            statement = statement.where(Person.deleted_at.is_(None))

        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def list_people(
        self,
        user_id: int,
        page: int = 1,
        page_size: int = 10,
    ) -> list[Person]:
        page, page_size, offset = self._normalize_pagination(page=page, page_size=page_size)

        result = await self.session.execute(
            select(Person)
            .where(
                Person.user_id == user_id,
                Person.deleted_at.is_(None),
            )
            .order_by(Person.first_name.asc(), Person.last_name.asc(), Person.id.asc())
            .limit(page_size)
            .offset(offset),
        )

        return list(result.scalars().all())

    async def search_people(
        self,
        user_id: int,
        query: str,
        filters: dict[str, Any] | None = None,
        page: int = 1,
        page_size: int = 10,
    ) -> list[Person]:
        page, page_size, offset = self._normalize_pagination(page=page, page_size=page_size)

        statement = (
            select(Person)
            .where(
                Person.user_id == user_id,
                Person.deleted_at.is_(None),
            )
            .order_by(Person.first_name.asc(), Person.last_name.asc(), Person.id.asc())
            .limit(page_size)
            .offset(offset)
        )

        statement = self._apply_search(statement=statement, query=query)
        statement = self._apply_filters(statement=statement, filters=filters)

        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def update_person(
        self,
        user_id: int,
        person_id: int,
        data: dict[str, Any],
    ) -> Person | None:
        person = await self.get_person_by_id(
            user_id=user_id,
            person_id=person_id,
            include_deleted=False,
        )

        if person is None:
            return None

        allowed_fields = {
            "first_name",
            "last_name",
            "middle_name",
            "nickname",
            "phone",
            "telegram_username",
            "birth_date",
            "birth_year_known",
            "birth_month",
            "birth_day",
            "gender",
            "category",
            "custom_category",
            "note",
            "how_met",
            "location",
            "workplace",
            "education_place",
        }

        for field_name, value in data.items():
            if field_name in allowed_fields:
                setattr(person, field_name, value)

        await self.session.flush()
        await self.session.refresh(person)

        return person

    async def soft_delete_person(self, user_id: int, person_id: int) -> Person | None:
        person = await self.get_person_by_id(
            user_id=user_id,
            person_id=person_id,
            include_deleted=False,
        )

        if person is None:
            return None

        person.deleted_at = utc_now()

        await self.session.flush()
        await self.session.refresh(person)

        return person

    async def count_people(self, user_id: int) -> int:
        result = await self.session.execute(
            select(func.count(Person.id)).where(
                Person.user_id == user_id,
                Person.deleted_at.is_(None),
            ),
        )

        return int(result.scalar_one())

    async def count_search_people(
        self,
        user_id: int,
        query: str,
        filters: dict[str, Any] | None = None,
    ) -> int:
        statement = select(func.count(Person.id)).where(
            Person.user_id == user_id,
            Person.deleted_at.is_(None),
        )

        statement = self._apply_search(statement=statement, query=query)
        statement = self._apply_filters(statement=statement, filters=filters)

        result = await self.session.execute(statement)
        return int(result.scalar_one())

    async def find_duplicates(
        self,
        user_id: int,
        phone: str | None = None,
        telegram_username: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        birth_date: date | None = None,
        nickname: str | None = None,
    ) -> list[Person]:
        conditions: list[sa.ColumnElement[bool]] = []

        if phone:
            conditions.append(Person.phone == phone)

        if telegram_username:
            conditions.append(func.lower(Person.telegram_username) == telegram_username.lower())

        if first_name and last_name and birth_date:
            conditions.append(
                and_(
                    func.lower(Person.first_name) == first_name.lower(),
                    func.lower(Person.last_name) == last_name.lower(),
                    Person.birth_date == birth_date,
                ),
            )

        if nickname and phone:
            conditions.append(
                and_(
                    func.lower(Person.nickname) == nickname.lower(),
                    Person.phone == phone,
                ),
            )

        if not conditions:
            return []

        result = await self.session.execute(
            select(Person)
            .where(
                Person.user_id == user_id,
                Person.deleted_at.is_(None),
                or_(*conditions),
            )
            .order_by(Person.first_name.asc(), Person.last_name.asc(), Person.id.asc()),
        )

        return list(result.scalars().all())

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
        return await self.create_person(
            user_id=user_id,
            data={
                "first_name": first_name,
                "last_name": last_name,
                "middle_name": middle_name,
                "nickname": nickname,
                "phone": phone,
                "telegram_username": telegram_username,
                "birth_date": birth_date,
                "birth_year_known": birth_year_known,
                "birth_month": birth_month,
                "birth_day": birth_day,
                "gender": gender,
                "category": category,
                "custom_category": custom_category,
                "note": note,
                "how_met": how_met,
                "location": location,
                "workplace": workplace,
                "education_place": education_place,
            },
        )

    async def get_by_id(
        self,
        user_id: int,
        person_id: int,
        include_deleted: bool = False,
    ) -> Person | None:
        return await self.get_person_by_id(
            user_id=user_id,
            person_id=person_id,
            include_deleted=include_deleted,
        )

    async def list_active(
        self,
        user_id: int,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Person]:
        page_size = max(1, min(limit, 100))
        page = max(1, offset // page_size + 1)

        return await self.list_people(
            user_id=user_id,
            page=page,
            page_size=page_size,
        )

    async def soft_delete(self, user_id: int, person_id: int) -> bool:
        person = await self.soft_delete_person(
            user_id=user_id,
            person_id=person_id,
        )

        return person is not None

    @staticmethod
    def _normalize_pagination(page: int, page_size: int) -> tuple[int, int, int]:
        normalized_page = max(1, page)
        normalized_page_size = max(1, min(page_size, 100))
        offset = (normalized_page - 1) * normalized_page_size

        return normalized_page, normalized_page_size, offset

    @staticmethod
    def _apply_search(statement: Select[Any], query: str) -> Select[Any]:
        normalized_query = query.strip().lower()

        if not normalized_query:
            return statement

        compact_query = normalized_query.replace(" ", "").replace("-", "").replace("–", "").replace("—", "")

        like_query = f"%{normalized_query}%"
        like_compact_query = f"%{compact_query}%"

        return statement.where(
            or_(
                func.lower(Person.first_name).like(like_query),
                func.lower(Person.last_name).like(like_query),
                func.lower(Person.nickname).like(like_query),
                func.lower(Person.phone).like(like_compact_query),
                func.lower(Person.telegram_username).like(like_query),
                func.lower(Person.category).like(like_query),
                func.lower(Person.custom_category).like(like_query),
                func.lower(Person.note).like(like_query),
                func.lower(Person.location).like(like_query),
                func.lower(Person.workplace).like(like_query),
                func.lower(Person.education_place).like(like_query),
            ),
        )

    @staticmethod
    def _apply_filters(
        statement: Select[Any],
        filters: dict[str, Any] | None,
    ) -> Select[Any]:
        if not filters:
            return statement

        if filters.get("category"):
            statement = statement.where(Person.category == filters["category"])

        if filters.get("gender"):
            statement = statement.where(Person.gender == filters["gender"])

        if filters.get("birth_month"):
            statement = statement.where(Person.birth_month == int(filters["birth_month"]))

        if filters.get("birth_day"):
            statement = statement.where(Person.birth_day == int(filters["birth_day"]))

        return statement
