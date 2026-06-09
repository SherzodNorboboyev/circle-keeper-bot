from __future__ import annotations

from datetime import UTC, date, datetime, time
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship as orm_relationship


SUPPORTED_LANGUAGES = ("uz", "ru", "en")

GENDERS = ("male", "female", "other", "unknown")

PERSON_CATEGORIES = (
    "father",
    "mother",
    "parent",
    "brother",
    "sister",
    "sibling",
    "child",
    "relative",
    "classmate",
    "coursemate",
    "colleague",
    "friend",
    "acquaintance",
    "spouse",
    "other",
    "custom",
)

RELATIONSHIP_TYPES = (
    "parent",
    "child",
    "sibling",
    "spouse",
    "classmate",
    "coursemate",
    "colleague",
    "friend",
    "relative",
    "acquaintance",
    "custom",
)

REMINDER_TYPES = ("birthday",)
REMINDER_LOG_STATUSES = ("pending", "sent", "failed", "skipped")
BACKUP_TYPES = ("auto", "manual_export", "after_import", "after_restore")
BACKUP_FORMATS = ("json", "sqlite")
BACKUP_STATUSES = ("pending", "sent", "failed")
IMPORT_TYPES = ("excel", "json_backup", "sqlite_backup")
IMPORT_STATUSES = ("pending", "validating", "preview", "importing", "completed", "failed", "cancelled")


def utc_now() -> datetime:
    return datetime.now(UTC)


def sql_values(values: tuple[str, ...]) -> str:
    return "(" + ", ".join(f"'{value}'" for value in values) + ")"


def bigint_type() -> sa.TypeEngine[int]:
    return sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def json_type() -> sa.TypeEngine[dict[str, Any]]:
    return sa.JSON().with_variant(
        postgresql.JSONB(astext_type=sa.Text()),
        "postgresql",
    )


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=sa.func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
        server_default=sa.func.now(),
    )


class SoftDeleteMixin:
    deleted_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(bigint_type(), primary_key=True, autoincrement=True)
    telegram_user_id: Mapped[int] = mapped_column(sa.BigInteger, nullable=False, unique=True)
    chat_id: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)

    username: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)
    first_name: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)
    last_name: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)

    language_code: Mapped[str | None] = mapped_column(sa.String(5), nullable=True)
    timezone: Mapped[str] = mapped_column(sa.String(64), nullable=False, default="Asia/Tashkent")

    is_admin: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=False, server_default=sa.false())
    is_active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=True, server_default=sa.true())

    people: Mapped[list[Person]] = orm_relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    relationships: Mapped[list[Relationship]] = orm_relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    reminders: Mapped[list[Reminder]] = orm_relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    backups: Mapped[list[Backup]] = orm_relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    settings: Mapped[list[UserSetting]] = orm_relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    audit_logs: Mapped[list[AuditLog]] = orm_relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    import_jobs: Mapped[list[ImportJob]] = orm_relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        sa.CheckConstraint(
            f"language_code IS NULL OR language_code IN {sql_values(SUPPORTED_LANGUAGES)}",
            name="chk_users_language",
        ),
        sa.Index("idx_users_chat_id", "chat_id"),
        sa.Index("idx_users_active", "is_active"),
    )


class Person(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "people"

    id: Mapped[int] = mapped_column(bigint_type(), primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        bigint_type(),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    first_name: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    last_name: Mapped[str | None] = mapped_column(sa.String(120), nullable=True)
    middle_name: Mapped[str | None] = mapped_column(sa.String(120), nullable=True)
    nickname: Mapped[str | None] = mapped_column(sa.String(120), nullable=True)
    phone: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    telegram_username: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)

    birth_date: Mapped[date | None] = mapped_column(sa.Date, nullable=True)
    birth_year_known: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=False, server_default=sa.false())
    birth_month: Mapped[int | None] = mapped_column(sa.SmallInteger, nullable=True)
    birth_day: Mapped[int | None] = mapped_column(sa.SmallInteger, nullable=True)

    gender: Mapped[str | None] = mapped_column(sa.String(20), nullable=True)
    category: Mapped[str | None] = mapped_column(sa.String(50), nullable=True)
    custom_category: Mapped[str | None] = mapped_column(sa.String(120), nullable=True)

    note: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    how_met: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    location: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)
    workplace: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)
    education_place: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)

    user: Mapped[User] = orm_relationship(back_populates="people")

    __table_args__ = (
        sa.UniqueConstraint("id", "user_id", name="uq_people_id_user"),
        sa.CheckConstraint(
            f"gender IS NULL OR gender IN {sql_values(GENDERS)}",
            name="chk_people_gender",
        ),
        sa.CheckConstraint(
            f"category IS NULL OR category IN {sql_values(PERSON_CATEGORIES)}",
            name="chk_people_category",
        ),
        sa.CheckConstraint(
            "category IS NULL OR category <> 'custom' OR custom_category IS NOT NULL",
            name="chk_people_custom_category",
        ),
        sa.CheckConstraint(
            "(birth_month IS NULL AND birth_day IS NULL) OR "
            "(birth_month IS NOT NULL AND birth_day IS NOT NULL "
            "AND birth_month BETWEEN 1 AND 12 AND birth_day BETWEEN 1 AND 31)",
            name="chk_people_birth_month_day",
        ),
        sa.CheckConstraint(
            "birth_date IS NULL OR birth_year_known = TRUE",
            name="chk_people_birth_date_year_known",
        ),
        sa.Index("idx_people_user_active", "user_id", "deleted_at"),
        sa.Index(
            "idx_people_name_active",
            "user_id",
            sa.text("lower(first_name)"),
            sa.text("lower(last_name)"),
            postgresql_where=sa.text("deleted_at IS NULL"),
            sqlite_where=sa.text("deleted_at IS NULL"),
        ),
        sa.Index(
            "idx_people_nickname_active",
            "user_id",
            sa.text("lower(nickname)"),
            postgresql_where=sa.text("deleted_at IS NULL AND nickname IS NOT NULL"),
            sqlite_where=sa.text("deleted_at IS NULL AND nickname IS NOT NULL"),
        ),
        sa.Index(
            "idx_people_phone_active",
            "user_id",
            "phone",
            postgresql_where=sa.text("deleted_at IS NULL AND phone IS NOT NULL"),
            sqlite_where=sa.text("deleted_at IS NULL AND phone IS NOT NULL"),
        ),
        sa.Index(
            "idx_people_telegram_active",
            "user_id",
            sa.text("lower(telegram_username)"),
            postgresql_where=sa.text("deleted_at IS NULL AND telegram_username IS NOT NULL"),
            sqlite_where=sa.text("deleted_at IS NULL AND telegram_username IS NOT NULL"),
        ),
        sa.Index(
            "idx_people_category_active",
            "user_id",
            "category",
            postgresql_where=sa.text("deleted_at IS NULL"),
            sqlite_where=sa.text("deleted_at IS NULL"),
        ),
        sa.Index(
            "idx_people_birth_month_day_active",
            "user_id",
            "birth_month",
            "birth_day",
            postgresql_where=sa.text("deleted_at IS NULL"),
            sqlite_where=sa.text("deleted_at IS NULL"),
        ),
    )


class Relationship(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "relationships"

    id: Mapped[int] = mapped_column(bigint_type(), primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        bigint_type(),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    from_person_id: Mapped[int] = mapped_column(bigint_type(), nullable=False)
    to_person_id: Mapped[int] = mapped_column(bigint_type(), nullable=False)

    relationship_type: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    custom_label: Mapped[str | None] = mapped_column(sa.String(120), nullable=True)
    note: Mapped[str | None] = mapped_column(sa.Text, nullable=True)

    is_bidirectional: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=True, server_default=sa.true())
    reverse_relationship_type: Mapped[str | None] = mapped_column(sa.String(50), nullable=True)

    user: Mapped[User] = orm_relationship(back_populates="relationships")

    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["from_person_id", "user_id"],
            ["people.id", "people.user_id"],
            name="fk_relationship_from_person",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["to_person_id", "user_id"],
            ["people.id", "people.user_id"],
            name="fk_relationship_to_person",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("from_person_id <> to_person_id", name="chk_relationship_not_self"),
        sa.CheckConstraint(
            f"relationship_type IN {sql_values(RELATIONSHIP_TYPES)}",
            name="chk_relationship_type",
        ),
        sa.CheckConstraint(
            f"reverse_relationship_type IS NULL OR reverse_relationship_type IN {sql_values(RELATIONSHIP_TYPES)}",
            name="chk_reverse_relationship_type",
        ),
        sa.CheckConstraint(
            "relationship_type <> 'custom' OR custom_label IS NOT NULL",
            name="chk_custom_relationship_label",
        ),
        sa.Index("idx_relationships_user_active", "user_id", "deleted_at"),
        sa.Index(
            "idx_relationships_from_active",
            "user_id",
            "from_person_id",
            postgresql_where=sa.text("deleted_at IS NULL"),
            sqlite_where=sa.text("deleted_at IS NULL"),
        ),
        sa.Index(
            "idx_relationships_to_active",
            "user_id",
            "to_person_id",
            postgresql_where=sa.text("deleted_at IS NULL"),
            sqlite_where=sa.text("deleted_at IS NULL"),
        ),
        sa.Index(
            "idx_relationships_type_active",
            "user_id",
            "relationship_type",
            postgresql_where=sa.text("deleted_at IS NULL"),
            sqlite_where=sa.text("deleted_at IS NULL"),
        ),
        sa.Index(
            "uq_relationships_active_edge",
            "user_id",
            "from_person_id",
            "to_person_id",
            "relationship_type",
            sa.text("coalesce(custom_label, '')"),
            unique=True,
            postgresql_where=sa.text("deleted_at IS NULL"),
            sqlite_where=sa.text("deleted_at IS NULL"),
        ),
    )


class Reminder(TimestampMixin, Base):
    __tablename__ = "reminders"

    id: Mapped[int] = mapped_column(bigint_type(), primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        bigint_type(),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    person_id: Mapped[int] = mapped_column(bigint_type(), nullable=False)

    reminder_type: Mapped[str] = mapped_column(sa.String(50), nullable=False, default="birthday", server_default="birthday")
    days_before: Mapped[int] = mapped_column(sa.SmallInteger, nullable=False, default=1, server_default="1")
    remind_time_local: Mapped[time] = mapped_column(
        sa.Time(),
        nullable=False,
        default=time(hour=9, minute=0),
        server_default=sa.text("'09:00:00'"),
    )
    enabled: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=True, server_default=sa.true())

    user: Mapped[User] = orm_relationship(back_populates="reminders")

    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["person_id", "user_id"],
            ["people.id", "people.user_id"],
            name="fk_reminders_person",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            f"reminder_type IN {sql_values(REMINDER_TYPES)}",
            name="chk_reminders_type",
        ),
        sa.CheckConstraint("days_before BETWEEN 0 AND 30", name="chk_reminders_days_before"),
        sa.UniqueConstraint(
            "user_id",
            "person_id",
            "reminder_type",
            "days_before",
            name="uq_reminders_person_type_days",
        ),
        sa.Index("idx_reminders_due_lookup", "user_id", "enabled", "remind_time_local", "days_before"),
    )


class ReminderLog(Base):
    __tablename__ = "reminder_logs"

    id: Mapped[int] = mapped_column(bigint_type(), primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        bigint_type(),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    person_id: Mapped[int] = mapped_column(bigint_type(), nullable=False)

    event_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    reminder_type: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    days_before: Mapped[int] = mapped_column(sa.SmallInteger, nullable=False, default=1, server_default="1")

    sent_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    telegram_message_id: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)
    status: Mapped[str] = mapped_column(sa.String(30), nullable=False, default="pending", server_default="pending")
    error_message: Mapped[str | None] = mapped_column(sa.Text, nullable=True)

    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["person_id", "user_id"],
            ["people.id", "people.user_id"],
            name="fk_reminder_logs_person",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            f"status IN {sql_values(REMINDER_LOG_STATUSES)}",
            name="chk_reminder_logs_status",
        ),
        sa.UniqueConstraint(
            "user_id",
            "person_id",
            "event_date",
            "reminder_type",
            "days_before",
            name="uq_reminder_logs_no_duplicate",
        ),
        sa.Index("idx_reminder_logs_user_event", "user_id", "event_date"),
        sa.Index("idx_reminder_logs_status", "status"),
    )


class Backup(Base):
    __tablename__ = "backups"

    id: Mapped[int] = mapped_column(bigint_type(), primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        bigint_type(),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    backup_type: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    storage_format: Mapped[str] = mapped_column(sa.String(20), nullable=False)

    telegram_chat_id: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    telegram_message_id: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)
    file_id: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    file_unique_id: Mapped[str | None] = mapped_column(sa.Text, nullable=True)

    filename: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    sha256: Mapped[str | None] = mapped_column(sa.CHAR(64), nullable=True)
    file_size: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)
    schema_version: Mapped[str] = mapped_column(sa.String(32), nullable=False)

    is_latest: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=False, server_default=sa.false())

    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=sa.func.now(),
    )
    status: Mapped[str] = mapped_column(sa.String(30), nullable=False, default="pending", server_default="pending")
    error_message: Mapped[str | None] = mapped_column(sa.Text, nullable=True)

    user: Mapped[User] = orm_relationship(back_populates="backups")

    __table_args__ = (
        sa.CheckConstraint(f"backup_type IN {sql_values(BACKUP_TYPES)}", name="chk_backups_type"),
        sa.CheckConstraint(f"storage_format IN {sql_values(BACKUP_FORMATS)}", name="chk_backups_format"),
        sa.CheckConstraint(f"status IN {sql_values(BACKUP_STATUSES)}", name="chk_backups_status"),
        sa.Index("idx_backups_user_created", "user_id", sa.text("created_at DESC")),
        sa.Index("idx_backups_status", "status"),
        sa.Index(
            "uq_backups_latest_per_user",
            "user_id",
            unique=True,
            postgresql_where=sa.text("is_latest = TRUE"),
            sqlite_where=sa.text("is_latest = 1"),
        ),
    )


class UserSetting(TimestampMixin, Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(bigint_type(), primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        bigint_type(),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    key: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    value: Mapped[dict[str, Any]] = mapped_column(json_type(), nullable=False)

    user: Mapped[User] = orm_relationship(back_populates="settings")

    __table_args__ = (
        sa.UniqueConstraint("user_id", "key", name="uq_settings_user_key"),
        sa.Index("idx_settings_user", "user_id"),
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(bigint_type(), primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        bigint_type(),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    action: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    entity_type: Mapped[str] = mapped_column(sa.String(80), nullable=False)
    entity_id: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)

    old_value: Mapped[dict[str, Any] | None] = mapped_column(json_type(), nullable=True)
    new_value: Mapped[dict[str, Any] | None] = mapped_column(json_type(), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=sa.func.now(),
    )

    user: Mapped[User] = orm_relationship(back_populates="audit_logs")

    __table_args__ = (
        sa.Index("idx_audit_logs_user_created", "user_id", sa.text("created_at DESC")),
        sa.Index("idx_audit_logs_entity", "entity_type", "entity_id"),
    )


class ImportJob(Base):
    __tablename__ = "import_jobs"

    id: Mapped[int] = mapped_column(bigint_type(), primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        bigint_type(),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    import_type: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    filename: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    file_size: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)

    status: Mapped[str] = mapped_column(sa.String(30), nullable=False, default="pending", server_default="pending")

    total_people: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0, server_default="0")
    total_relationships: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0, server_default="0")
    total_errors: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0, server_default="0")

    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=sa.func.now(),
    )
    completed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)

    error_report_file_id: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(sa.Text, nullable=True)

    user: Mapped[User] = orm_relationship(back_populates="import_jobs")
    errors: Mapped[list[ImportErrorRecord]] = orm_relationship(
        back_populates="import_job",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        sa.CheckConstraint(f"import_type IN {sql_values(IMPORT_TYPES)}", name="chk_import_jobs_type"),
        sa.CheckConstraint(f"status IN {sql_values(IMPORT_STATUSES)}", name="chk_import_jobs_status"),
        sa.CheckConstraint("file_size >= 0", name="chk_import_jobs_file_size_non_negative"),
        sa.CheckConstraint("total_people >= 0", name="chk_import_jobs_total_people_non_negative"),
        sa.CheckConstraint("total_relationships >= 0", name="chk_import_jobs_total_relationships_non_negative"),
        sa.CheckConstraint("total_errors >= 0", name="chk_import_jobs_total_errors_non_negative"),
        sa.Index("idx_import_jobs_user_created", "user_id", sa.text("created_at DESC")),
        sa.Index("idx_import_jobs_status", "status"),
    )


class ImportErrorRecord(Base):
    __tablename__ = "import_errors"

    id: Mapped[int] = mapped_column(bigint_type(), primary_key=True, autoincrement=True)
    import_job_id: Mapped[int] = mapped_column(
        bigint_type(),
        sa.ForeignKey("import_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )

    sheet_name: Mapped[str | None] = mapped_column(sa.String(120), nullable=True)
    row_number: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    column_name: Mapped[str | None] = mapped_column(sa.String(120), nullable=True)

    error_code: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    error_message: Mapped[str] = mapped_column(sa.Text, nullable=False)
    suggested_fix: Mapped[str | None] = mapped_column(sa.Text, nullable=True)

    import_job: Mapped[ImportJob] = orm_relationship(back_populates="errors")

    __table_args__ = (
        sa.Index("idx_import_errors_job", "import_job_id"),
        sa.Index("idx_import_errors_code", "error_code"),
    )