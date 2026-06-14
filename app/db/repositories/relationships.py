from __future__ import annotations

from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Relationship, utc_now


class RelationshipsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_relationship(
        self,
        user_id: int,
        from_person_id: int,
        to_person_id: int,
        relationship_type: str,
        custom_label: str | None = None,
        note: str | None = None,
        is_bidirectional: bool | None = None,
        reverse_relationship_type: str | None = None,
    ) -> Relationship:
        relationship = Relationship(
            user_id=user_id,
            from_person_id=from_person_id,
            to_person_id=to_person_id,
            relationship_type=relationship_type,
            custom_label=custom_label,
            note=note,
            is_bidirectional=True if is_bidirectional is None else is_bidirectional,
            reverse_relationship_type=reverse_relationship_type,
        )

        self.session.add(relationship)
        await self.session.flush()
        await self.session.refresh(relationship)

        return relationship

    async def get_relationship_by_id(
        self,
        user_id: int,
        relationship_id: int,
    ) -> Relationship | None:
        result = await self.session.execute(
            select(Relationship).where(
                Relationship.id == relationship_id,
                Relationship.user_id == user_id,
                Relationship.deleted_at.is_(None),
            ),
        )

        return result.scalar_one_or_none()

    async def list_relationships_for_person(
        self,
        user_id: int,
        person_id: int,
    ) -> list[Relationship]:
        result = await self.session.execute(
            select(Relationship)
            .where(
                Relationship.user_id == user_id,
                Relationship.deleted_at.is_(None),
                or_(
                    Relationship.from_person_id == person_id,
                    Relationship.to_person_id == person_id,
                ),
            )
            .order_by(Relationship.created_at.desc(), Relationship.id.desc()),
        )

        return list(result.scalars().all())

    async def list_relationships(
        self,
        user_id: int,
        page: int = 1,
        page_size: int = 10,
    ) -> list[Relationship]:
        page, page_size, offset = self._normalize_pagination(page=page, page_size=page_size)

        result = await self.session.execute(
            select(Relationship)
            .where(
                Relationship.user_id == user_id,
                Relationship.deleted_at.is_(None),
            )
            .order_by(Relationship.created_at.desc(), Relationship.id.desc())
            .limit(page_size)
            .offset(offset),
        )

        return list(result.scalars().all())

    async def count_relationships(self, user_id: int) -> int:
        result = await self.session.execute(
            select(func.count(Relationship.id)).where(
                Relationship.user_id == user_id,
                Relationship.deleted_at.is_(None),
            ),
        )

        return int(result.scalar_one())

    async def update_relationship(
        self,
        user_id: int,
        relationship_id: int,
        data: dict[str, Any],
    ) -> Relationship | None:
        relationship = await self.get_relationship_by_id(
            user_id=user_id,
            relationship_id=relationship_id,
        )

        if relationship is None:
            return None

        allowed_fields = {
            "relationship_type",
            "custom_label",
            "note",
            "is_bidirectional",
            "reverse_relationship_type",
        }

        for field_name, value in data.items():
            if field_name in allowed_fields:
                setattr(relationship, field_name, value)

        await self.session.flush()
        await self.session.refresh(relationship)

        return relationship

    async def soft_delete_relationship(
        self,
        user_id: int,
        relationship_id: int,
    ) -> Relationship | None:
        relationship = await self.get_relationship_by_id(
            user_id=user_id,
            relationship_id=relationship_id,
        )

        if relationship is None:
            return None

        relationship.deleted_at = utc_now()

        await self.session.flush()
        await self.session.refresh(relationship)

        return relationship

    async def soft_delete_relationships_for_person(
        self,
        user_id: int,
        person_id: int,
    ) -> list[Relationship]:
        relationships = await self.list_relationships_for_person(
            user_id=user_id,
            person_id=person_id,
        )

        if not relationships:
            return []

        deleted_at = utc_now()

        for relationship in relationships:
            relationship.deleted_at = deleted_at

        await self.session.flush()

        for relationship in relationships:
            await self.session.refresh(relationship)

        return relationships

    async def relationship_exists(
        self,
        user_id: int,
        from_person_id: int,
        to_person_id: int,
        relationship_type: str,
        custom_label: str | None = None,
    ) -> bool:
        statement = select(Relationship.id).where(
            Relationship.user_id == user_id,
            Relationship.from_person_id == from_person_id,
            Relationship.to_person_id == to_person_id,
            Relationship.relationship_type == relationship_type,
            Relationship.deleted_at.is_(None),
        )

        if custom_label is None:
            statement = statement.where(Relationship.custom_label.is_(None))
        else:
            statement = statement.where(Relationship.custom_label == custom_label)

        result = await self.session.execute(statement.limit(1))
        return result.scalar_one_or_none() is not None

    async def create(
        self,
        user_id: int,
        from_person_id: int,
        to_person_id: int,
        relationship_type: str,
        custom_label: str | None = None,
        note: str | None = None,
        is_bidirectional: bool = True,
        reverse_relationship_type: str | None = None,
    ) -> Relationship:
        return await self.create_relationship(
            user_id=user_id,
            from_person_id=from_person_id,
            to_person_id=to_person_id,
            relationship_type=relationship_type,
            custom_label=custom_label,
            note=note,
            is_bidirectional=is_bidirectional,
            reverse_relationship_type=reverse_relationship_type,
        )

    async def get_by_id(
        self,
        user_id: int,
        relationship_id: int,
        include_deleted: bool = False,
    ) -> Relationship | None:
        statement = select(Relationship).where(
            Relationship.id == relationship_id,
            Relationship.user_id == user_id,
        )

        if not include_deleted:
            statement = statement.where(Relationship.deleted_at.is_(None))

        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def list_for_person(
        self,
        user_id: int,
        person_id: int,
    ) -> list[Relationship]:
        return await self.list_relationships_for_person(
            user_id=user_id,
            person_id=person_id,
        )

    async def soft_delete(self, user_id: int, relationship_id: int) -> bool:
        relationship = await self.soft_delete_relationship(
            user_id=user_id,
            relationship_id=relationship_id,
        )

        return relationship is not None

    @staticmethod
    def _normalize_pagination(page: int, page_size: int) -> tuple[int, int, int]:
        normalized_page = max(1, page)
        normalized_page_size = max(1, min(page_size, 100))
        offset = (normalized_page - 1) * normalized_page_size

        return normalized_page, normalized_page_size, offset
