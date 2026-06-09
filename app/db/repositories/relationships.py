from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Relationship, utc_now


class RelationshipsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

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
        if from_person_id == to_person_id:
            raise ValueError("A person cannot have a relationship with itself.")

        relationship = Relationship(
            user_id=user_id,
            from_person_id=from_person_id,
            to_person_id=to_person_id,
            relationship_type=relationship_type,
            custom_label=custom_label,
            note=note,
            is_bidirectional=is_bidirectional,
            reverse_relationship_type=reverse_relationship_type,
        )

        self.session.add(relationship)
        await self.session.flush()
        return relationship

    async def get_by_id(self, user_id: int, relationship_id: int, include_deleted: bool = False) -> Relationship | None:
        statement = select(Relationship).where(
            Relationship.id == relationship_id,
            Relationship.user_id == user_id,
        )

        if not include_deleted:
            statement = statement.where(Relationship.deleted_at.is_(None))

        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def list_for_person(self, user_id: int, person_id: int) -> list[Relationship]:
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
            .order_by(Relationship.created_at.desc()),
        )
        return list(result.scalars().all())

    async def soft_delete(self, user_id: int, relationship_id: int) -> bool:
        relationship = await self.get_by_id(user_id=user_id, relationship_id=relationship_id)

        if relationship is None:
            return False

        relationship.deleted_at = utc_now()
        await self.session.flush()
        return True