from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Person, Relationship
from app.db.repositories.people import PeopleRepository
from app.services.audit_service import AuditService
from app.services.backup_trigger import BackupTriggerService
from app.services.people_service import PeopleService
from app.services.relationship_service import RelationshipService, RelationshipValidationError
from app.services.reminder_service import ReminderService


@dataclass(frozen=True)
class ChildCreationResult:
    parent: Person
    child: Person
    relationship: Relationship
    reminder_count: int


class ChildService:
    async def create_child_for_parent(
        self,
        session: AsyncSession,
        user_id: int,
        parent_person_id: int,
        child_data: dict[str, Any],
    ) -> ChildCreationResult:
        people_repository = PeopleRepository(session)
        people_service = PeopleService()

        parent = await people_repository.get_person_by_id(
            user_id=user_id,
            person_id=parent_person_id,
        )

        if parent is None:
            raise RelationshipValidationError(
                message_key="relationship.person_not_found",
            )

        prepared_child_data = people_service.prepare_create_data(
            {
                **child_data,
                "category": "child",
                "custom_category": None,
            },
        )

        child = await people_repository.create_person(
            user_id=user_id,
            data=prepared_child_data,
        )

        parent_role = self.determine_parent_role(parent)

        relationship_service = RelationshipService()
        relationship = await relationship_service.create_relationship(
            session=session,
            user_id=user_id,
            from_person_id=parent.id,
            to_person_id=child.id,
            relationship_type="parent",
            custom_label=parent_role,
            note=prepared_child_data.get("note"),
            is_bidirectional=False,
            reverse_relationship_type="child",
        )

        audit_service = AuditService(session)
        await audit_service.log_person_created(
            user_id=user_id,
            person_id=child.id,
            new_value=people_service.person_to_dict(child),
        )
        await audit_service.log_relationship_created(
            user_id=user_id,
            relationship_id=relationship.id,
            new_value=relationship_service.relationship_to_dict(relationship),
        )

        reminder_count = 0

        if child.birth_month and child.birth_day:
            reminders = await ReminderService().ensure_default_birthday_reminders_for_person(
                session=session,
                user_id=user_id,
                person=child,
            )
            reminder_count = len(reminders)

        backup_trigger = BackupTriggerService()
        await backup_trigger.trigger_user_backup(
            user_id=user_id,
            reason="child.created",
            metadata={
                "parent_person_id": parent.id,
                "child_person_id": child.id,
                "relationship_id": relationship.id,
                "reminder_count": reminder_count,
            },
        )

        return ChildCreationResult(
            parent=parent,
            child=child,
            relationship=relationship,
            reminder_count=reminder_count,
        )

    @staticmethod
    def determine_parent_role(parent: Person) -> str:
        if parent.category == "father" or parent.gender == "male":
            return "father"

        if parent.category == "mother" or parent.gender == "female":
            return "mother"

        return "parent"
