from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.services.admin_service import AdminService, AdminStats
from app.services.i18n import I18nService


router = Router(name="admin")


@router.message(Command("stats"))
async def stats_command(
    message: Message,
    session: AsyncSession,
    current_user: User,
    i18n: I18nService,
    lang: str,
) -> None:
    if not current_user.is_admin:
        await message.answer(i18n.t("admin.forbidden", lang=lang))
        return

    stats = await AdminService(session).get_stats()

    await message.answer(
        render_admin_stats(stats=stats, i18n=i18n, lang=lang),
    )


def render_admin_stats(stats: AdminStats, i18n: I18nService, lang: str) -> str:
    recent_imports = ", ".join(
        f"{status}: {count}"
        for status, count in sorted(stats.recent_import_job_counts.items())
    ) or "—"

    return i18n.t(
        "admin.stats",
        lang=lang,
        total_users=stats.total_users,
        active_users=stats.active_users,
        total_people=stats.total_people,
        total_active_people=stats.total_active_people,
        total_relationships=stats.total_relationships,
        total_active_relationships=stats.total_active_relationships,
        failed_backups=stats.failed_backups,
        failed_imports=stats.failed_imports,
        recent_imports=recent_imports,
        reminder_sent_count=stats.reminder_sent_count,
        reminder_failed_count=stats.reminder_failed_count,
    )