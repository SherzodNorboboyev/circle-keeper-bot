from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, ClassVar

from loguru import logger

from app.db.models import GENDERS, PERSON_CATEGORIES, Person


@dataclass(frozen=True)
class BirthDateParts:
    birth_date: date | None
    birth_year_known: bool
    birth_month: int | None
    birth_day: int | None


class PeopleValidationError(ValueError):
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


class PeopleService:
    text_fields: ClassVar[set[str]] = {
        "first_name",
        "last_name",
        "middle_name",
        "nickname",
        "phone",
        "telegram_username",
        "gender",
        "category",
        "custom_category",
        "note",
        "how_met",
        "location",
        "workplace",
        "education_place",
    }

    editable_fields: ClassVar[set[str]] = {
        "first_name",
        "last_name",
        "middle_name",
        "nickname",
        "phone",
        "telegram_username",
        "birth_date",
        "gender",
        "category",
        "custom_category",
        "note",
        "how_met",
        "location",
        "workplace",
        "education_place",
    }

    def prepare_create_data(self, data: dict[str, Any]) -> dict[str, Any]:
        first_name = self.clean_required_text(
            data.get("first_name"),
            message_key="error.required_field",
            field="first_name",
        )

        prepared: dict[str, Any] = {
            "first_name": first_name,
            "last_name": self.clean_optional_text(data.get("last_name")),
            "middle_name": self.clean_optional_text(data.get("middle_name")),
            "nickname": self.clean_optional_text(data.get("nickname")),
            "phone": self.normalize_phone(data.get("phone")),
            "telegram_username": self.normalize_telegram_username(data.get("telegram_username")),
            "gender": self.normalize_gender(data.get("gender")),
            "category": self.normalize_category(data.get("category")),
            "custom_category": self.clean_optional_text(data.get("custom_category")),
            "note": self.clean_optional_text(data.get("note")),
            "how_met": self.clean_optional_text(data.get("how_met")),
            "location": self.clean_optional_text(data.get("location")),
            "workplace": self.clean_optional_text(data.get("workplace")),
            "education_place": self.clean_optional_text(data.get("education_place")),
        }

        birth_parts = self.parse_birth_date(data.get("birth_date"))
        prepared.update(
            {
                "birth_date": birth_parts.birth_date,
                "birth_year_known": birth_parts.birth_year_known,
                "birth_month": birth_parts.birth_month,
                "birth_day": birth_parts.birth_day,
            },
        )

        self.validate_custom_category(
            category=prepared["category"],
            custom_category=prepared["custom_category"],
        )

        if prepared["category"] != "custom":
            prepared["custom_category"] = None

        return prepared

    def prepare_update_data(
        self,
        existing_person: Person,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        prepared: dict[str, Any] = {}

        unknown_fields = set(data) - self.editable_fields

        if unknown_fields:
            unknown_fields_text = ", ".join(sorted(unknown_fields))
            raise PeopleValidationError(
                message_key="person.invalid_field",
                detail=unknown_fields_text,
            )

        if "first_name" in data:
            prepared["first_name"] = self.clean_required_text(
                data.get("first_name"),
                message_key="error.required_field",
                field="first_name",
            )

        for field_name in (
            "last_name",
            "middle_name",
            "nickname",
            "custom_category",
            "note",
            "how_met",
            "location",
            "workplace",
            "education_place",
        ):
            if field_name in data:
                prepared[field_name] = self.clean_optional_text(data.get(field_name))

        if "phone" in data:
            prepared["phone"] = self.normalize_phone(data.get("phone"))

        if "telegram_username" in data:
            prepared["telegram_username"] = self.normalize_telegram_username(data.get("telegram_username"))

        if "gender" in data:
            prepared["gender"] = self.normalize_gender(data.get("gender"))

        if "category" in data:
            prepared["category"] = self.normalize_category(data.get("category"))

        if "birth_date" in data:
            birth_parts = self.parse_birth_date(data.get("birth_date"))
            prepared.update(
                {
                    "birth_date": birth_parts.birth_date,
                    "birth_year_known": birth_parts.birth_year_known,
                    "birth_month": birth_parts.birth_month,
                    "birth_day": birth_parts.birth_day,
                },
            )

        effective_category = prepared.get("category", existing_person.category)
        effective_custom_category = prepared.get("custom_category", existing_person.custom_category)

        self.validate_custom_category(
            category=effective_category,
            custom_category=effective_custom_category,
        )

        if "category" in prepared and prepared["category"] != "custom":
            prepared["custom_category"] = None

        return prepared

    def parse_birth_date(self, value: Any) -> BirthDateParts:
        if value is None:
            return BirthDateParts(
                birth_date=None,
                birth_year_known=False,
                birth_month=None,
                birth_day=None,
            )

        if isinstance(value, date) and not isinstance(value, datetime):
            return BirthDateParts(
                birth_date=value,
                birth_year_known=True,
                birth_month=value.month,
                birth_day=value.day,
            )

        raw_value = str(value).strip()

        if not raw_value:
            return BirthDateParts(
                birth_date=None,
                birth_year_known=False,
                birth_month=None,
                birth_day=None,
            )

        iso_full_match = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", raw_value)
        if iso_full_match:
            year, month, day = map(int, iso_full_match.groups())
            return self._build_full_birth_date(year=year, month=month, day=day)

        iso_month_day_match = re.fullmatch(r"(\d{2})-(\d{2})", raw_value)
        if iso_month_day_match:
            month, day = map(int, iso_month_day_match.groups())
            return self._build_month_day_birth_date(month=month, day=day)

        dot_full_match = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", raw_value)
        if dot_full_match:
            day, month, year = map(int, dot_full_match.groups())
            return self._build_full_birth_date(year=year, month=month, day=day)

        dot_day_month_match = re.fullmatch(r"(\d{1,2})\.(\d{1,2})", raw_value)
        if dot_day_month_match:
            day, month = map(int, dot_day_month_match.groups())
            return self._build_month_day_birth_date(month=month, day=day)

        raise PeopleValidationError(
            message_key="person.invalid_birth_date",
            field="birth_date",
            detail=raw_value,
        )

    def format_full_name(self, person: Person | dict[str, Any]) -> str:
        first_name = self._get_value(person, "first_name")
        middle_name = self._get_value(person, "middle_name")
        last_name = self._get_value(person, "last_name")

        parts = [
            str(part).strip() for part in (first_name, middle_name, last_name) if part is not None and str(part).strip()
        ]

        return " ".join(parts) if parts else "—"

    def calculate_age(
        self,
        person: Person | dict[str, Any],
        today: date | None = None,
    ) -> int | None:
        birth_year_known = self._get_value(person, "birth_year_known")
        birth_date_value = self._get_value(person, "birth_date")

        if not birth_year_known or birth_date_value is None:
            return None

        if isinstance(birth_date_value, str):
            birth_date_value = date.fromisoformat(birth_date_value)

        if not isinstance(birth_date_value, date):
            return None

        today = today or date.today()

        age = today.year - birth_date_value.year

        if (today.month, today.day) < (birth_date_value.month, birth_date_value.day):
            age -= 1

        return max(0, age)

    def format_birth_date(
        self,
        person: Person | dict[str, Any],
        lang: str = "uz",
    ) -> str:
        birth_year_known = self._get_value(person, "birth_year_known")
        birth_date_value = self._get_value(person, "birth_date")
        birth_month = self._get_value(person, "birth_month")
        birth_day = self._get_value(person, "birth_day")

        if birth_year_known and birth_date_value:
            if isinstance(birth_date_value, str):
                birth_date_value = date.fromisoformat(birth_date_value)

            if lang == "en":
                return birth_date_value.strftime("%Y-%m-%d")

            return birth_date_value.strftime("%d.%m.%Y")

        if birth_month and birth_day:
            if lang == "en":
                return f"{int(birth_month):02d}-{int(birth_day):02d}"

            return f"{int(birth_day):02d}.{int(birth_month):02d}"

        return "—"

    def person_to_dict(self, person: Person) -> dict[str, Any]:
        fields = (
            "id",
            "user_id",
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
            "created_at",
            "updated_at",
            "deleted_at",
        )

        result: dict[str, Any] = {}

        for field_name in fields:
            value = getattr(person, field_name)

            if isinstance(value, datetime):
                result[field_name] = value.isoformat()
            elif isinstance(value, date):
                result[field_name] = value.isoformat()
            else:
                result[field_name] = value

        return result

    async def run_after_person_deleted_hooks(self, user_id: int, person_id: int) -> None:
        logger.bind(user_id=user_id, person_id=person_id).info("person_deleted_lifecycle_hooks_called")

    @staticmethod
    def normalize_phone(value: Any) -> str | None:
        if value is None:
            return None

        normalized = str(value).strip()

        if not normalized:
            return None

        for item in (" ", "\t", "\n", "\r", "-", "–", "—", "\u00a0"):
            normalized = normalized.replace(item, "")

        return normalized or None

    @staticmethod
    def normalize_telegram_username(value: Any) -> str | None:
        if value is None:
            return None

        normalized = str(value).strip()

        if not normalized:
            return None

        prefixes = (
            "https://t.me/",
            "http://t.me/",
            "t.me/",
        )

        lowered = normalized.lower()

        for prefix in prefixes:
            if lowered.startswith(prefix):
                normalized = normalized[len(prefix) :]
                break

        normalized = normalized.strip().lstrip("@").strip("/")
        normalized = normalized.lower()

        return normalized or None

    @staticmethod
    def clean_optional_text(value: Any) -> str | None:
        if value is None:
            return None

        cleaned = str(value).strip()

        return cleaned or None

    @staticmethod
    def clean_required_text(
        value: Any,
        message_key: str,
        field: str,
    ) -> str:
        cleaned = PeopleService.clean_optional_text(value)

        if not cleaned:
            raise PeopleValidationError(
                message_key=message_key,
                field=field,
            )

        return cleaned

    @staticmethod
    def normalize_category(value: Any) -> str | None:
        cleaned = PeopleService.clean_optional_text(value)

        if cleaned is None:
            return None

        normalized = cleaned.lower()

        if normalized not in PERSON_CATEGORIES:
            raise PeopleValidationError(
                message_key="person.invalid_category",
                field="category",
                detail=normalized,
            )

        return normalized

    @staticmethod
    def normalize_gender(value: Any) -> str | None:
        cleaned = PeopleService.clean_optional_text(value)

        if cleaned is None:
            return None

        normalized = cleaned.lower()

        if normalized not in GENDERS:
            raise PeopleValidationError(
                message_key="person.invalid_gender",
                field="gender",
                detail=normalized,
            )

        return normalized

    @staticmethod
    def validate_custom_category(
        category: str | None,
        custom_category: str | None,
    ) -> None:
        if category == "custom" and not custom_category:
            raise PeopleValidationError(
                message_key="person.custom_category_required",
                field="custom_category",
            )

    def _build_full_birth_date(self, year: int, month: int, day: int) -> BirthDateParts:
        try:
            parsed_date = date(year=year, month=month, day=day)
        except ValueError as exc:
            raise PeopleValidationError(
                message_key="person.invalid_birth_date",
                field="birth_date",
            ) from exc

        return BirthDateParts(
            birth_date=parsed_date,
            birth_year_known=True,
            birth_month=parsed_date.month,
            birth_day=parsed_date.day,
        )

    def _build_month_day_birth_date(self, month: int, day: int) -> BirthDateParts:
        try:
            date(year=2000, month=month, day=day)
        except ValueError as exc:
            raise PeopleValidationError(
                message_key="person.invalid_birth_date",
                field="birth_date",
            ) from exc

        return BirthDateParts(
            birth_date=None,
            birth_year_known=False,
            birth_month=month,
            birth_day=day,
        )

    @staticmethod
    def _get_value(person: Person | dict[str, Any], field_name: str) -> Any:
        if isinstance(person, dict):
            return person.get(field_name)

        return getattr(person, field_name, None)
