from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import RELATIONSHIP_TYPES, Person, Relationship
from app.db.repositories.people import PeopleRepository
from app.db.repositories.relationships import RelationshipsRepository
from app.services.i18n import I18nService
from app.services.people_service import PeopleService

SYMMETRIC_RELATIONSHIP_TYPES = {
    "sibling",
    "spouse",
    "classmate",
    "coursemate",
    "colleague",
    "friend",
    "acquaintance",
}

DIRECTED_REVERSE_DEFAULTS = {
    "parent": "child",
    "child": "parent",
}

PARENT_ROLE_LABELS = {
    "father",
    "mother",
    "parent",
}


@dataclass(frozen=True)
class RelationshipDisplay:
    relationship: Relationship
    other_person_id: int
    display_type: str
    display_label: str


class RelationshipValidationError(ValueError):
    def __init__(
        self,
        message_key: str,
        field: str | None = None,
        detail: str | None = None,
    ) -> None:
        self.message_key = message_key
        self.field = field
        self.detail = detail

        super().__init__(message_key)


class RelationshipService:
    async def create_relationship(
        self,
        session: AsyncSession,
        user_id: int,
        from_person_id: int,
        to_person_id: int,
        relationship_type: str,
        custom_label: str | None = None,
        note: str | None = None,
        is_bidirectional: bool | None = None,
        reverse_relationship_type: str | None = None,
    ) -> Relationship:
        prepared_data = await self.prepare_create_data(
            session=session,
            user_id=user_id,
            from_person_id=from_person_id,
            to_person_id=to_person_id,
            relationship_type=relationship_type,
            custom_label=custom_label,
            note=note,
            is_bidirectional=is_bidirectional,
            reverse_relationship_type=reverse_relationship_type,
        )

        repository = RelationshipsRepository(session)

        try:
            return await repository.create_relationship(
                user_id=user_id,
                from_person_id=prepared_data["from_person_id"],
                to_person_id=prepared_data["to_person_id"],
                relationship_type=prepared_data["relationship_type"],
                custom_label=prepared_data["custom_label"],
                note=prepared_data["note"],
                is_bidirectional=prepared_data["is_bidirectional"],
                reverse_relationship_type=prepared_data["reverse_relationship_type"],
            )
        except IntegrityError as exc:
            raise RelationshipValidationError(message_key="relationship.duplicate") from exc

    async def prepare_create_data(
        self,
        session: AsyncSession,
        user_id: int,
        from_person_id: int,
        to_person_id: int,
        relationship_type: str,
        custom_label: str | None = None,
        note: str | None = None,
        is_bidirectional: bool | None = None,
        reverse_relationship_type: str | None = None,
    ) -> dict[str, Any]:
        if from_person_id == to_person_id:
            raise RelationshipValidationError(
                message_key="relationship.self_not_allowed",
                field="to_person_id",
            )

        normalized_type = self.normalize_relationship_type(relationship_type)
        normalized_custom_label = self.clean_optional_text(custom_label)
        normalized_note = self.clean_optional_text(note)

        if normalized_type == "custom" and not normalized_custom_label:
            raise RelationshipValidationError(
                message_key="relationship.custom_label_required",
                field="custom_label",
            )

        normalized_reverse_type = self.normalize_reverse_relationship_type(
            reverse_relationship_type,
        )

        normalized_is_bidirectional = self.resolve_is_bidirectional(
            relationship_type=normalized_type,
            is_bidirectional=is_bidirectional,
        )

        if normalized_reverse_type is None:
            normalized_reverse_type = self.default_reverse_relationship_type(
                relationship_type=normalized_type,
                is_bidirectional=normalized_is_bidirectional,
            )

        await self.ensure_active_people_belong_to_user(
            session=session,
            user_id=user_id,
            from_person_id=from_person_id,
            to_person_id=to_person_id,
        )

        await self.ensure_relationship_does_not_exist(
            session=session,
            user_id=user_id,
            from_person_id=from_person_id,
            to_person_id=to_person_id,
            relationship_type=normalized_type,
            custom_label=normalized_custom_label,
            is_bidirectional=normalized_is_bidirectional,
        )

        return {
            "from_person_id": from_person_id,
            "to_person_id": to_person_id,
            "relationship_type": normalized_type,
            "custom_label": normalized_custom_label,
            "note": normalized_note,
            "is_bidirectional": normalized_is_bidirectional,
            "reverse_relationship_type": normalized_reverse_type,
        }

    async def ensure_active_people_belong_to_user(
        self,
        session: AsyncSession,
        user_id: int,
        from_person_id: int,
        to_person_id: int,
    ) -> tuple[Person, Person]:
        people_repository = PeopleRepository(session)

        from_person = await people_repository.get_person_by_id(
            user_id=user_id,
            person_id=from_person_id,
        )
        to_person = await people_repository.get_person_by_id(
            user_id=user_id,
            person_id=to_person_id,
        )

        if from_person is None or to_person is None:
            raise RelationshipValidationError(
                message_key="relationship.person_not_found",
            )

        return from_person, to_person

    async def ensure_relationship_does_not_exist(
        self,
        session: AsyncSession,
        user_id: int,
        from_person_id: int,
        to_person_id: int,
        relationship_type: str,
        custom_label: str | None,
        is_bidirectional: bool,
    ) -> None:
        repository = RelationshipsRepository(session)

        direct_exists = await repository.relationship_exists(
            user_id=user_id,
            from_person_id=from_person_id,
            to_person_id=to_person_id,
            relationship_type=relationship_type,
            custom_label=custom_label,
        )

        if direct_exists:
            raise RelationshipValidationError(
                message_key="relationship.duplicate",
            )

        if is_bidirectional or relationship_type in SYMMETRIC_RELATIONSHIP_TYPES:
            reverse_exists = await repository.relationship_exists(
                user_id=user_id,
                from_person_id=to_person_id,
                to_person_id=from_person_id,
                relationship_type=relationship_type,
                custom_label=custom_label,
            )

            if reverse_exists:
                raise RelationshipValidationError(
                    message_key="relationship.duplicate",
                )

        reverse_semantic_type = DIRECTED_REVERSE_DEFAULTS.get(relationship_type)

        if reverse_semantic_type is not None:
            semantic_reverse_exists = await repository.relationship_exists(
                user_id=user_id,
                from_person_id=to_person_id,
                to_person_id=from_person_id,
                relationship_type=reverse_semantic_type,
                custom_label=custom_label,
            )

            if semantic_reverse_exists:
                raise RelationshipValidationError(
                    message_key="relationship.duplicate",
                )

    def get_display_relationship_type_for_viewer(
        self,
        relationship: Relationship,
        viewer_person_id: int,
    ) -> str:
        if viewer_person_id not in {relationship.from_person_id, relationship.to_person_id}:
            raise RelationshipValidationError(
                message_key="relationship.person_not_found",
            )

        viewer_is_from = viewer_person_id == relationship.from_person_id

        if relationship.relationship_type == "parent":
            return "child" if viewer_is_from else "parent"

        if relationship.relationship_type == "child":
            return "parent" if viewer_is_from else "child"

        if viewer_is_from:
            return relationship.relationship_type

        if relationship.is_bidirectional:
            return relationship.relationship_type

        if relationship.reverse_relationship_type:
            return relationship.reverse_relationship_type

        return relationship.relationship_type

    def get_other_person_id(
        self,
        relationship: Relationship,
        viewer_person_id: int,
    ) -> int:
        if viewer_person_id == relationship.from_person_id:
            return relationship.to_person_id

        if viewer_person_id == relationship.to_person_id:
            return relationship.from_person_id

        raise RelationshipValidationError(
            message_key="relationship.person_not_found",
        )

    def get_display_label(
        self,
        relationship: Relationship,
        viewer_person_id: int,
        i18n: I18nService,
        lang: str,
    ) -> str:
        display_type = self.get_display_relationship_type_for_viewer(
            relationship=relationship,
            viewer_person_id=viewer_person_id,
        )

        viewer_is_to = viewer_person_id == relationship.to_person_id

        if (
            relationship.relationship_type == "parent"
            and viewer_is_to
            and relationship.custom_label in PARENT_ROLE_LABELS
        ):
            return i18n.t(
                f"relationship.parent_roles.{relationship.custom_label}",
                lang=lang,
            )

        if display_type == "custom" and relationship.custom_label:
            return relationship.custom_label

        return i18n.t(f"relationship.labels.{display_type}", lang=lang)

    def build_display(
        self,
        relationship: Relationship,
        viewer_person_id: int,
        i18n: I18nService,
        lang: str,
    ) -> RelationshipDisplay:
        display_type = self.get_display_relationship_type_for_viewer(
            relationship=relationship,
            viewer_person_id=viewer_person_id,
        )
        display_label = self.get_display_label(
            relationship=relationship,
            viewer_person_id=viewer_person_id,
            i18n=i18n,
            lang=lang,
        )
        other_person_id = self.get_other_person_id(
            relationship=relationship,
            viewer_person_id=viewer_person_id,
        )

        return RelationshipDisplay(
            relationship=relationship,
            other_person_id=other_person_id,
            display_type=display_type,
            display_label=display_label,
        )

    async def get_profile_relationship_lines(
        self,
        session: AsyncSession,
        user_id: int,
        person_id: int,
        i18n: I18nService,
        lang: str,
    ) -> list[str]:
        repository = RelationshipsRepository(session)
        people_repository = PeopleRepository(session)
        people_service = PeopleService()

        relationships = await repository.list_relationships_for_person(
            user_id=user_id,
            person_id=person_id,
        )

        lines: list[str] = []

        for relationship in relationships:
            display = self.build_display(
                relationship=relationship,
                viewer_person_id=person_id,
                i18n=i18n,
                lang=lang,
            )

            other_person = await people_repository.get_person_by_id(
                user_id=user_id,
                person_id=display.other_person_id,
            )

            if other_person is None:
                continue

            lines.append(
                i18n.t(
                    "relationship.profile_line",
                    lang=lang,
                    full_name=people_service.format_full_name(other_person),
                    label=display.display_label,
                ),
            )

        return lines

    def relationship_to_dict(self, relationship: Relationship) -> dict[str, Any]:
        fields = (
            "id",
            "user_id",
            "from_person_id",
            "to_person_id",
            "relationship_type",
            "custom_label",
            "note",
            "is_bidirectional",
            "reverse_relationship_type",
            "created_at",
            "updated_at",
            "deleted_at",
        )

        result: dict[str, Any] = {}

        for field_name in fields:
            value = getattr(relationship, field_name)

            if isinstance(value, datetime):
                result[field_name] = value.isoformat()
            elif isinstance(value, date):
                result[field_name] = value.isoformat()
            else:
                result[field_name] = value

        return result

    @staticmethod
    def resolve_is_bidirectional(
        relationship_type: str,
        is_bidirectional: bool | None,
    ) -> bool:
        if is_bidirectional is not None:
            return is_bidirectional

        if relationship_type in {"parent", "child"}:
            return False

        if relationship_type in SYMMETRIC_RELATIONSHIP_TYPES:
            return True

        if relationship_type == "relative":
            return True

        if relationship_type == "custom":
            return True

        return True

    @staticmethod
    def default_reverse_relationship_type(
        relationship_type: str,
        is_bidirectional: bool,
    ) -> str | None:
        if relationship_type in DIRECTED_REVERSE_DEFAULTS:
            return DIRECTED_REVERSE_DEFAULTS[relationship_type]

        if is_bidirectional:
            return None

        return None

    @staticmethod
    def normalize_relationship_type(value: str | None) -> str:
        normalized = RelationshipService.clean_optional_text(value)

        if normalized is None:
            raise RelationshipValidationError(
                message_key="relationship.invalid_type",
                field="relationship_type",
            )

        normalized = normalized.lower()

        if normalized not in RELATIONSHIP_TYPES:
            raise RelationshipValidationError(
                message_key="relationship.invalid_type",
                field="relationship_type",
                detail=normalized,
            )

        return normalized

    @staticmethod
    def normalize_reverse_relationship_type(value: str | None) -> str | None:
        normalized = RelationshipService.clean_optional_text(value)

        if normalized is None:
            return None

        normalized = normalized.lower()

        if normalized not in RELATIONSHIP_TYPES:
            raise RelationshipValidationError(
                message_key="relationship.invalid_type",
                field="reverse_relationship_type",
                detail=normalized,
            )

        return normalized

    @staticmethod
    def clean_optional_text(value: Any) -> str | None:
        if value is None:
            return None

        cleaned = str(value).strip()

        return cleaned or None
