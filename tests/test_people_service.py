from __future__ import annotations

from datetime import date

import pytest

from app.services.people_service import PeopleService, PeopleValidationError


def test_birth_date_parser_full_iso() -> None:
    service = PeopleService()

    result = service.parse_birth_date("1995-04-21")

    assert result.birth_date == date(1995, 4, 21)
    assert result.birth_year_known is True
    assert result.birth_month == 4
    assert result.birth_day == 21


def test_birth_date_parser_month_day_iso() -> None:
    service = PeopleService()

    result = service.parse_birth_date("04-21")

    assert result.birth_date is None
    assert result.birth_year_known is False
    assert result.birth_month == 4
    assert result.birth_day == 21


def test_birth_date_parser_full_dot_format() -> None:
    service = PeopleService()

    result = service.parse_birth_date("21.04.1995")

    assert result.birth_date == date(1995, 4, 21)
    assert result.birth_year_known is True
    assert result.birth_month == 4
    assert result.birth_day == 21


def test_birth_date_parser_day_month_dot_format() -> None:
    service = PeopleService()

    result = service.parse_birth_date("21.04")

    assert result.birth_date is None
    assert result.birth_year_known is False
    assert result.birth_month == 4
    assert result.birth_day == 21


def test_birth_date_parser_invalid_date() -> None:
    service = PeopleService()

    with pytest.raises(PeopleValidationError) as exc:
        service.parse_birth_date("31.02.1995")

    assert exc.value.message_key == "person.invalid_birth_date"


def test_custom_category_validation_requires_custom_category() -> None:
    service = PeopleService()

    with pytest.raises(PeopleValidationError) as exc:
        service.prepare_create_data(
            {
                "first_name": "Ali",
                "category": "custom",
                "custom_category": "",
            },
        )

    assert exc.value.message_key == "person.custom_category_required"


def test_phone_and_username_normalization() -> None:
    service = PeopleService()

    prepared = service.prepare_create_data(
        {
            "first_name": "Ali",
            "phone": "+998 90-123-45-67",
            "telegram_username": "@AliUser",
            "category": "friend",
        },
    )

    assert prepared["phone"] == "+998901234567"
    assert prepared["telegram_username"] == "aliuser"


def test_age_calculator_only_when_year_known() -> None:
    service = PeopleService()

    with_year = {
        "birth_date": date(1995, 4, 21),
        "birth_year_known": True,
        "birth_month": 4,
        "birth_day": 21,
    }

    without_year = {
        "birth_date": None,
        "birth_year_known": False,
        "birth_month": 4,
        "birth_day": 21,
    }

    assert service.calculate_age(with_year, today=date(2026, 4, 22)) == 31
    assert service.calculate_age(without_year, today=date(2026, 4, 22)) is None