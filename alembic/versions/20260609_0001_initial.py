"""initial schema

Revision ID: 20260609_0001
Revises: None
Create Date: 2026-06-09 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260609_0001"
down_revision = None
branch_labels = None
depends_on = None


def bigint() -> sa.TypeEngine[int]:
    return sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def json_type() -> sa.TypeEngine[dict[str, object]]:
    return sa.JSON().with_variant(
        postgresql.JSONB(astext_type=sa.Text()),
        "postgresql",
    )


def active_where() -> sa.TextClause:
    return sa.text("deleted_at IS NULL")


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", bigint(), primary_key=True, autoincrement=True),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("first_name", sa.String(length=255), nullable=True),
        sa.Column("last_name", sa.String(length=255), nullable=True),
        sa.Column("language_code", sa.String(length=5), nullable=True),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("language_code IS NULL OR language_code IN ('uz', 'ru', 'en')", name="chk_users_language"),
        sa.UniqueConstraint("telegram_user_id", name="uq_users_telegram_user_id"),
    )
    op.create_index("idx_users_chat_id", "users", ["chat_id"])
    op.create_index("idx_users_active", "users", ["is_active"])

    op.create_table(
        "people",
        sa.Column("id", bigint(), primary_key=True, autoincrement=True),
        sa.Column("user_id", bigint(), nullable=False),
        sa.Column("first_name", sa.String(length=120), nullable=False),
        sa.Column("last_name", sa.String(length=120), nullable=True),
        sa.Column("middle_name", sa.String(length=120), nullable=True),
        sa.Column("nickname", sa.String(length=120), nullable=True),
        sa.Column("phone", sa.String(length=64), nullable=True),
        sa.Column("telegram_username", sa.String(length=255), nullable=True),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column("birth_year_known", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("birth_month", sa.SmallInteger(), nullable=True),
        sa.Column("birth_day", sa.SmallInteger(), nullable=True),
        sa.Column("gender", sa.String(length=20), nullable=True),
        sa.Column("category", sa.String(length=50), nullable=True),
        sa.Column("custom_category", sa.String(length=120), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("how_met", sa.Text(), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("workplace", sa.String(length=255), nullable=True),
        sa.Column("education_place", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("gender IS NULL OR gender IN ('male', 'female', 'other', 'unknown')", name="chk_people_gender"),
        sa.CheckConstraint(
            "category IS NULL OR category IN ('father', 'mother', 'parent', 'brother', 'sister', 'sibling', "
            "'child', 'relative', 'classmate', 'coursemate', 'colleague', 'friend', 'acquaintance', "
            "'spouse', 'other', 'custom')",
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_people_user_id_users", ondelete="CASCADE"),
        sa.UniqueConstraint("id", "user_id", name="uq_people_id_user"),
    )
    op.create_index("idx_people_user_active", "people", ["user_id", "deleted_at"])
    op.create_index(
        "idx_people_name_active",
        "people",
        ["user_id", sa.text("lower(first_name)"), sa.text("lower(last_name)")],
        postgresql_where=active_where(),
        sqlite_where=active_where(),
    )
    op.create_index(
        "idx_people_nickname_active",
        "people",
        ["user_id", sa.text("lower(nickname)")],
        postgresql_where=sa.text("deleted_at IS NULL AND nickname IS NOT NULL"),
        sqlite_where=sa.text("deleted_at IS NULL AND nickname IS NOT NULL"),
    )
    op.create_index(
        "idx_people_phone_active",
        "people",
        ["user_id", "phone"],
        postgresql_where=sa.text("deleted_at IS NULL AND phone IS NOT NULL"),
        sqlite_where=sa.text("deleted_at IS NULL AND phone IS NOT NULL"),
    )
    op.create_index(
        "idx_people_telegram_active",
        "people",
        ["user_id", sa.text("lower(telegram_username)")],
        postgresql_where=sa.text("deleted_at IS NULL AND telegram_username IS NOT NULL"),
        sqlite_where=sa.text("deleted_at IS NULL AND telegram_username IS NOT NULL"),
    )
    op.create_index(
        "idx_people_category_active",
        "people",
        ["user_id", "category"],
        postgresql_where=active_where(),
        sqlite_where=active_where(),
    )
    op.create_index(
        "idx_people_birth_month_day_active",
        "people",
        ["user_id", "birth_month", "birth_day"],
        postgresql_where=active_where(),
        sqlite_where=active_where(),
    )

    op.create_table(
        "relationships",
        sa.Column("id", bigint(), primary_key=True, autoincrement=True),
        sa.Column("user_id", bigint(), nullable=False),
        sa.Column("from_person_id", bigint(), nullable=False),
        sa.Column("to_person_id", bigint(), nullable=False),
        sa.Column("relationship_type", sa.String(length=50), nullable=False),
        sa.Column("custom_label", sa.String(length=120), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("is_bidirectional", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("reverse_relationship_type", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_relationships_user_id_users", ondelete="CASCADE"),
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
            "relationship_type IN ('parent', 'child', 'sibling', 'spouse', 'classmate', 'coursemate', "
            "'colleague', 'friend', 'relative', 'acquaintance', 'custom')",
            name="chk_relationship_type",
        ),
        sa.CheckConstraint(
            "reverse_relationship_type IS NULL OR reverse_relationship_type IN "
            "('parent', 'child', 'sibling', 'spouse', 'classmate', 'coursemate', "
            "'colleague', 'friend', 'relative', 'acquaintance', 'custom')",
            name="chk_reverse_relationship_type",
        ),
        sa.CheckConstraint(
            "relationship_type <> 'custom' OR custom_label IS NOT NULL",
            name="chk_custom_relationship_label",
        ),
    )
    op.create_index("idx_relationships_user_active", "relationships", ["user_id", "deleted_at"])
    op.create_index(
        "idx_relationships_from_active",
        "relationships",
        ["user_id", "from_person_id"],
        postgresql_where=active_where(),
        sqlite_where=active_where(),
    )
    op.create_index(
        "idx_relationships_to_active",
        "relationships",
        ["user_id", "to_person_id"],
        postgresql_where=active_where(),
        sqlite_where=active_where(),
    )
    op.create_index(
        "idx_relationships_type_active",
        "relationships",
        ["user_id", "relationship_type"],
        postgresql_where=active_where(),
        sqlite_where=active_where(),
    )
    op.create_index(
        "uq_relationships_active_edge",
        "relationships",
        ["user_id", "from_person_id", "to_person_id", "relationship_type", sa.text("coalesce(custom_label, '')")],
        unique=True,
        postgresql_where=active_where(),
        sqlite_where=active_where(),
    )

    op.create_table(
        "reminders",
        sa.Column("id", bigint(), primary_key=True, autoincrement=True),
        sa.Column("user_id", bigint(), nullable=False),
        sa.Column("person_id", bigint(), nullable=False),
        sa.Column("reminder_type", sa.String(length=50), nullable=False, server_default="birthday"),
        sa.Column("days_before", sa.SmallInteger(), nullable=False, server_default="1"),
        sa.Column("remind_time_local", sa.Time(), nullable=False, server_default=sa.text("'09:00:00'")),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_reminders_user_id_users", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["person_id", "user_id"],
            ["people.id", "people.user_id"],
            name="fk_reminders_person",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("reminder_type IN ('birthday')", name="chk_reminders_type"),
        sa.CheckConstraint("days_before BETWEEN 0 AND 30", name="chk_reminders_days_before"),
        sa.UniqueConstraint("user_id", "person_id", "reminder_type", "days_before", name="uq_reminders_person_type_days"),
    )
    op.create_index("idx_reminders_due_lookup", "reminders", ["user_id", "enabled", "remind_time_local", "days_before"])

    op.create_table(
        "reminder_logs",
        sa.Column("id", bigint(), primary_key=True, autoincrement=True),
        sa.Column("user_id", bigint(), nullable=False),
        sa.Column("person_id", bigint(), nullable=False),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("reminder_type", sa.String(length=50), nullable=False),
        sa.Column("days_before", sa.SmallInteger(), nullable=False, server_default="1"),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("telegram_message_id", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_reminder_logs_user_id_users", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["person_id", "user_id"],
            ["people.id", "people.user_id"],
            name="fk_reminder_logs_person",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("status IN ('pending', 'sent', 'failed', 'skipped')", name="chk_reminder_logs_status"),
        sa.UniqueConstraint(
            "user_id",
            "person_id",
            "event_date",
            "reminder_type",
            "days_before",
            name="uq_reminder_logs_no_duplicate",
        ),
    )
    op.create_index("idx_reminder_logs_user_event", "reminder_logs", ["user_id", "event_date"])
    op.create_index("idx_reminder_logs_status", "reminder_logs", ["status"])

    op.create_table(
        "backups",
        sa.Column("id", bigint(), primary_key=True, autoincrement=True),
        sa.Column("user_id", bigint(), nullable=False),
        sa.Column("backup_type", sa.String(length=50), nullable=False),
        sa.Column("storage_format", sa.String(length=20), nullable=False),
        sa.Column("telegram_chat_id", sa.BigInteger(), nullable=False),
        sa.Column("telegram_message_id", sa.BigInteger(), nullable=True),
        sa.Column("file_id", sa.Text(), nullable=True),
        sa.Column("file_unique_id", sa.Text(), nullable=True),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("sha256", sa.CHAR(length=64), nullable=True),
        sa.Column("file_size", sa.BigInteger(), nullable=True),
        sa.Column("schema_version", sa.String(length=32), nullable=False),
        sa.Column("is_latest", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_backups_user_id_users", ondelete="CASCADE"),
        sa.CheckConstraint("backup_type IN ('auto', 'manual_export', 'after_import', 'after_restore')", name="chk_backups_type"),
        sa.CheckConstraint("storage_format IN ('json', 'sqlite')", name="chk_backups_format"),
        sa.CheckConstraint("status IN ('pending', 'sent', 'failed')", name="chk_backups_status"),
    )
    op.create_index("idx_backups_user_created", "backups", ["user_id", sa.text("created_at DESC")])
    op.create_index("idx_backups_status", "backups", ["status"])
    op.create_index(
        "uq_backups_latest_per_user",
        "backups",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("is_latest = TRUE"),
        sqlite_where=sa.text("is_latest = 1"),
    )

    op.create_table(
        "settings",
        sa.Column("id", bigint(), primary_key=True, autoincrement=True),
        sa.Column("user_id", bigint(), nullable=False),
        sa.Column("key", sa.String(length=120), nullable=False),
        sa.Column("value", json_type(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_settings_user_id_users", ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "key", name="uq_settings_user_key"),
    )
    op.create_index("idx_settings_user", "settings", ["user_id"])

    op.create_table(
        "audit_logs",
        sa.Column("id", bigint(), primary_key=True, autoincrement=True),
        sa.Column("user_id", bigint(), nullable=False),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("entity_id", sa.BigInteger(), nullable=True),
        sa.Column("old_value", json_type(), nullable=True),
        sa.Column("new_value", json_type(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_audit_logs_user_id_users", ondelete="CASCADE"),
    )
    op.create_index("idx_audit_logs_user_created", "audit_logs", ["user_id", sa.text("created_at DESC")])
    op.create_index("idx_audit_logs_entity", "audit_logs", ["entity_type", "entity_id"])

    op.create_table(
        "import_jobs",
        sa.Column("id", bigint(), primary_key=True, autoincrement=True),
        sa.Column("user_id", bigint(), nullable=False),
        sa.Column("import_type", sa.String(length=50), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("total_people", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_relationships", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_errors", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_report_file_id", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_import_jobs_user_id_users", ondelete="CASCADE"),
        sa.CheckConstraint("import_type IN ('excel', 'json_backup', 'sqlite_backup')", name="chk_import_jobs_type"),
        sa.CheckConstraint(
            "status IN ('pending', 'validating', 'preview', 'importing', 'completed', 'failed', 'cancelled')",
            name="chk_import_jobs_status",
        ),
        sa.CheckConstraint("file_size >= 0", name="chk_import_jobs_file_size_non_negative"),
        sa.CheckConstraint("total_people >= 0", name="chk_import_jobs_total_people_non_negative"),
        sa.CheckConstraint("total_relationships >= 0", name="chk_import_jobs_total_relationships_non_negative"),
        sa.CheckConstraint("total_errors >= 0", name="chk_import_jobs_total_errors_non_negative"),
    )
    op.create_index("idx_import_jobs_user_created", "import_jobs", ["user_id", sa.text("created_at DESC")])
    op.create_index("idx_import_jobs_status", "import_jobs", ["status"])

    op.create_table(
        "import_errors",
        sa.Column("id", bigint(), primary_key=True, autoincrement=True),
        sa.Column("import_job_id", bigint(), nullable=False),
        sa.Column("sheet_name", sa.String(length=120), nullable=True),
        sa.Column("row_number", sa.Integer(), nullable=True),
        sa.Column("column_name", sa.String(length=120), nullable=True),
        sa.Column("error_code", sa.String(length=120), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=False),
        sa.Column("suggested_fix", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["import_job_id"], ["import_jobs.id"], name="fk_import_errors_import_job_id_import_jobs", ondelete="CASCADE"),
    )
    op.create_index("idx_import_errors_job", "import_errors", ["import_job_id"])
    op.create_index("idx_import_errors_code", "import_errors", ["error_code"])


def downgrade() -> None:
    op.drop_index("idx_import_errors_code", table_name="import_errors")
    op.drop_index("idx_import_errors_job", table_name="import_errors")
    op.drop_table("import_errors")

    op.drop_index("idx_import_jobs_status", table_name="import_jobs")
    op.drop_index("idx_import_jobs_user_created", table_name="import_jobs")
    op.drop_table("import_jobs")

    op.drop_index("idx_audit_logs_entity", table_name="audit_logs")
    op.drop_index("idx_audit_logs_user_created", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index("idx_settings_user", table_name="settings")
    op.drop_table("settings")

    op.drop_index("uq_backups_latest_per_user", table_name="backups")
    op.drop_index("idx_backups_status", table_name="backups")
    op.drop_index("idx_backups_user_created", table_name="backups")
    op.drop_table("backups")

    op.drop_index("idx_reminder_logs_status", table_name="reminder_logs")
    op.drop_index("idx_reminder_logs_user_event", table_name="reminder_logs")
    op.drop_table("reminder_logs")

    op.drop_index("idx_reminders_due_lookup", table_name="reminders")
    op.drop_table("reminders")

    op.drop_index("uq_relationships_active_edge", table_name="relationships")
    op.drop_index("idx_relationships_type_active", table_name="relationships")
    op.drop_index("idx_relationships_to_active", table_name="relationships")
    op.drop_index("idx_relationships_from_active", table_name="relationships")
    op.drop_index("idx_relationships_user_active", table_name="relationships")
    op.drop_table("relationships")

    op.drop_index("idx_people_birth_month_day_active", table_name="people")
    op.drop_index("idx_people_category_active", table_name="people")
    op.drop_index("idx_people_telegram_active", table_name="people")
    op.drop_index("idx_people_phone_active", table_name="people")
    op.drop_index("idx_people_nickname_active", table_name="people")
    op.drop_index("idx_people_name_active", table_name="people")
    op.drop_index("idx_people_user_active", table_name="people")
    op.drop_table("people")

    op.drop_index("idx_users_active", table_name="users")
    op.drop_index("idx_users_chat_id", table_name="users")
    op.drop_table("users")