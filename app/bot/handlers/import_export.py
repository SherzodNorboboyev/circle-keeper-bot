from __future__ import annotations

import tempfile
from pathlib import Path

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.main_menu import main_menu_keyboard
from app.bot.states.import_states import ExcelImportStates, RestoreStates
from app.config import get_settings
from app.db.models import User
from app.services.backup_service import BackupService
from app.services.excel_error_report_service import ExcelErrorReportService
from app.services.excel_export_service import ExcelExportService
from app.services.excel_import_service import ExcelImportService, ExcelImportValidationError
from app.services.excel_template_service import ExcelTemplateService
from app.services.i18n import I18nService
from app.services.restore_service import RestoreService, RestoreValidationError


router = Router(name="import_export")


def export_format_keyboard() -> InlineKeyboardMarkup:
    settings = get_settings()
    rows = [
        [
            InlineKeyboardButton(text="JSON", callback_data="backup_export:json"),
        ],
    ]

    if settings.DATABASE_URL.startswith("sqlite"):
        rows.append(
            [
                InlineKeyboardButton(text="SQLite", callback_data="backup_export:sqlite"),
            ],
        )

    return InlineKeyboardMarkup(inline_keyboard=rows)


def restore_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Replace all", callback_data="restore:replace_all"),
            ],
            [
                InlineKeyboardButton(text="Cancel", callback_data="restore:cancel"),
            ],
        ],
    )


def excel_import_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Import", callback_data="excel_import:confirm"),
            ],
            [
                InlineKeyboardButton(text="Cancel", callback_data="excel_import:cancel"),
            ],
        ],
    )


@router.message(Command("export"))
async def export_command(
    message: Message,
    i18n: I18nService,
    lang: str,
) -> None:
    await message.answer(
        i18n.t("backup.export_choose_format", lang=lang),
        reply_markup=export_format_keyboard(),
    )


@router.callback_query(F.data == "backup_export:json")
async def export_json_callback(
    callback: CallbackQuery,
    session: AsyncSession,
    bot: Bot,
    current_user: User,
    i18n: I18nService,
    lang: str,
) -> None:
    result = await BackupService(
        session=session,
        bot=bot,
        i18n=i18n,
    ).create_and_send_json_backup(
        user_id=current_user.id,
        backup_type="manual_export",
        reason="/export",
        notify_on_failure=True,
    )

    if result.success:
        await callback.message.answer(
            i18n.t(
                "backup.export_success",
                lang=lang,
                filename=result.filename,
            ),
            reply_markup=main_menu_keyboard(i18n=i18n, lang=lang),
        )
    else:
        await callback.message.answer(
            i18n.t("backup.export_failed", lang=lang),
            reply_markup=main_menu_keyboard(i18n=i18n, lang=lang),
        )

    await callback.answer()


@router.callback_query(F.data == "backup_export:sqlite")
async def export_sqlite_callback(
    callback: CallbackQuery,
    session: AsyncSession,
    bot: Bot,
    current_user: User,
    i18n: I18nService,
    lang: str,
) -> None:
    result = await BackupService(
        session=session,
        bot=bot,
        i18n=i18n,
    ).create_and_send_sqlite_backup(
        user_id=current_user.id,
        backup_type="manual_export",
        reason="/export sqlite",
    )

    if result.success:
        await callback.message.answer(
            i18n.t(
                "backup.export_success",
                lang=lang,
                filename=result.filename,
            ),
            reply_markup=main_menu_keyboard(i18n=i18n, lang=lang),
        )
    else:
        await callback.message.answer(
            i18n.t("backup.export_failed", lang=lang),
            reply_markup=main_menu_keyboard(i18n=i18n, lang=lang),
        )

    await callback.answer()


@router.message(Command("import"))
async def import_command(
    message: Message,
    state: FSMContext,
    i18n: I18nService,
    lang: str,
) -> None:
    await state.clear()
    await state.set_state(RestoreStates.waiting_for_file)

    await message.answer(i18n.t("restore.ask_file", lang=lang))


@router.message(RestoreStates.waiting_for_file, F.document)
async def restore_file_received(
    message: Message,
    state: FSMContext,
    bot: Bot,
    i18n: I18nService,
    lang: str,
) -> None:
    document = message.document
    service = RestoreService()

    try:
        service.validate_document(
            filename=document.file_name or "",
            content_type=document.mime_type,
            file_size=document.file_size or 0,
        )
        content = await download_document(bot=bot, file_id=document.file_id)
        payload = service.parse_backup(content)
        preview = service.build_preview(payload)
    except RestoreValidationError as exc:
        await message.answer(i18n.t(exc.message_key, lang=lang))
        return

    temporary_path = write_temporary_file(
        prefix="restore_",
        suffix=".json",
        content=content,
    )

    await state.update_data(restore_path=str(temporary_path))
    await state.set_state(RestoreStates.confirm)

    await message.answer(
        i18n.t(
            "restore.preview",
            lang=lang,
            generated_at=preview.generated_at or "—",
            people_count=preview.people_count,
            relationships_count=preview.relationships_count,
            reminders_count=preview.reminders_count,
            schema_version=preview.schema_version,
        ),
        reply_markup=restore_confirm_keyboard(),
    )


@router.callback_query(RestoreStates.confirm, F.data == "restore:replace_all")
async def restore_replace_all_callback(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    bot: Bot,
    current_user: User,
    i18n: I18nService,
    lang: str,
) -> None:
    data = await state.get_data()
    restore_path = Path(str(data["restore_path"]))
    service = RestoreService()

    try:
        payload = service.parse_backup(restore_path.read_bytes())
        result = await service.replace_all(
            session=session,
            user_id=current_user.id,
            payload=payload,
        )
        await BackupService(
            session=session,
            bot=bot,
            i18n=i18n,
        ).create_and_send_json_backup(
            user_id=current_user.id,
            backup_type="after_restore",
            reason="restore.completed",
            notify_on_failure=True,
        )
    finally:
        restore_path.unlink(missing_ok=True)

    await state.clear()

    await callback.message.answer(
        i18n.t(
            "restore.completed",
            lang=lang,
            people_count=result.people_count,
            relationships_count=result.relationships_count,
            reminders_count=result.reminders_count,
        ),
        reply_markup=main_menu_keyboard(i18n=i18n, lang=lang),
    )
    await callback.answer()


@router.callback_query(RestoreStates.confirm, F.data == "restore:cancel")
async def restore_cancel_callback(
    callback: CallbackQuery,
    state: FSMContext,
    i18n: I18nService,
    lang: str,
) -> None:
    data = await state.get_data()
    restore_path = data.get("restore_path")

    if restore_path:
        Path(str(restore_path)).unlink(missing_ok=True)

    await state.clear()

    await callback.message.answer(
        i18n.t("restore.cancelled", lang=lang),
        reply_markup=main_menu_keyboard(i18n=i18n, lang=lang),
    )
    await callback.answer()


@router.message(Command("excel_template"))
async def excel_template_command(
    message: Message,
    i18n: I18nService,
    lang: str,
) -> None:
    template = ExcelTemplateService().create_template()

    await message.answer_document(
        document=BufferedInputFile(
            template.content,
            filename=template.filename,
        ),
        caption=i18n.t("excel.template_ready", lang=lang),
    )


@router.message(Command("import_excel"))
async def import_excel_command(
    message: Message,
    state: FSMContext,
    i18n: I18nService,
    lang: str,
) -> None:
    await state.clear()
    await state.set_state(ExcelImportStates.waiting_for_file)

    await message.answer(i18n.t("excel.ask_file", lang=lang))


@router.message(ExcelImportStates.waiting_for_file, F.document)
async def import_excel_file_received(
    message: Message,
    state: FSMContext,
    bot: Bot,
    session: AsyncSession,
    current_user: User,
    i18n: I18nService,
    lang: str,
) -> None:
    document = message.document
    service = ExcelImportService()

    try:
        service.validate_document(
            filename=document.file_name or "",
            content_type=document.mime_type,
            file_size=document.file_size or 0,
        )
        content = await download_document(bot=bot, file_id=document.file_id)
        parsed = await service.parse_file(
            session=session,
            user_id=current_user.id,
            content=content,
        )
    except ExcelImportValidationError as exc:
        await message.answer(i18n.t(exc.message_key, lang=lang))
        return

    if parsed.errors:
        await service.record_failed_import_job(
            session=session,
            user_id=current_user.id,
            filename=document.file_name or "import.xlsx",
            file_size=document.file_size or len(content),
            errors=parsed.errors,
        )

        error_report = ExcelErrorReportService().create_error_report(parsed.errors)

        await message.answer_document(
            document=BufferedInputFile(
                error_report.content,
                filename=error_report.filename,
            ),
            caption=i18n.t("excel.error_report_ready", lang=lang),
        )
        await state.clear()
        return

    temporary_path = write_temporary_file(
        prefix="excel_import_",
        suffix=".xlsx",
        content=content,
    )

    await state.update_data(
        excel_import_path=str(temporary_path),
        excel_import_filename=document.file_name or "import.xlsx",
        excel_import_file_size=document.file_size or len(content),
    )
    await state.set_state(ExcelImportStates.confirm)

    preview = parsed.preview

    await message.answer(
        i18n.t(
            "excel.import_preview",
            lang=lang,
            people_count=preview.people_count,
            relationships_count=preview.relationships_count,
            children_count=preview.children_count,
            duplicate_count=preview.duplicate_count,
            error_count=preview.error_count,
            import_mode=preview.import_mode,
        ),
        reply_markup=excel_import_confirm_keyboard(),
    )


@router.callback_query(ExcelImportStates.confirm, F.data == "excel_import:confirm")
async def excel_import_confirm_callback(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    bot: Bot,
    current_user: User,
    i18n: I18nService,
    lang: str,
) -> None:
    data = await state.get_data()
    import_path = Path(str(data["excel_import_path"]))
    filename = str(data["excel_import_filename"])
    file_size = int(data["excel_import_file_size"])

    service = ExcelImportService()

    try:
        content = import_path.read_bytes()
        parsed = await service.parse_file(
            session=session,
            user_id=current_user.id,
            content=content,
        )

        if parsed.errors:
            error_report = ExcelErrorReportService().create_error_report(parsed.errors)

            await callback.message.answer_document(
                document=BufferedInputFile(
                    error_report.content,
                    filename=error_report.filename,
                ),
                caption=i18n.t("excel.error_report_ready", lang=lang),
            )
            return

        result = await service.import_parsed(
            session=session,
            user_id=current_user.id,
            filename=filename,
            file_size=file_size,
            parsed=parsed,
        )

        await BackupService(
            session=session,
            bot=bot,
            i18n=i18n,
        ).create_and_send_json_backup(
            user_id=current_user.id,
            backup_type="after_import",
            reason="excel.import.completed",
            notify_on_failure=True,
        )
    finally:
        import_path.unlink(missing_ok=True)

    await state.clear()

    await callback.message.answer(
        i18n.t(
            "excel.import_completed",
            lang=lang,
            people_count=result.imported_people_count,
            relationships_count=result.imported_relationships_count,
            skipped_duplicates_count=result.skipped_duplicates_count,
        ),
        reply_markup=main_menu_keyboard(i18n=i18n, lang=lang),
    )
    await callback.answer()


@router.callback_query(ExcelImportStates.confirm, F.data == "excel_import:cancel")
async def excel_import_cancel_callback(
    callback: CallbackQuery,
    state: FSMContext,
    i18n: I18nService,
    lang: str,
) -> None:
    data = await state.get_data()
    import_path = data.get("excel_import_path")

    if import_path:
        Path(str(import_path)).unlink(missing_ok=True)

    await state.clear()

    await callback.message.answer(
        i18n.t("restore.cancelled", lang=lang),
        reply_markup=main_menu_keyboard(i18n=i18n, lang=lang),
    )
    await callback.answer()


@router.message(Command("export_excel"))
async def export_excel_command(
    message: Message,
    session: AsyncSession,
    current_user: User,
    i18n: I18nService,
    lang: str,
) -> None:
    export_file = await ExcelExportService().create_export(
        session=session,
        user_id=current_user.id,
    )

    if export_file is None:
        await message.answer(i18n.t("excel.no_data", lang=lang))
        return

    await message.answer_document(
        document=BufferedInputFile(
            export_file.content,
            filename=export_file.filename,
        ),
        caption=i18n.t("excel.export_ready", lang=lang),
    )


async def download_document(bot: Bot, file_id: str) -> bytes:
    file = await bot.get_file(file_id)
    buffer = bytearray()

    destination = tempfile.NamedTemporaryFile(delete=False)
    destination_path = Path(destination.name)
    destination.close()

    try:
        await bot.download_file(
            file_path=file.file_path,
            destination=destination_path,
        )
        buffer.extend(destination_path.read_bytes())
    finally:
        destination_path.unlink(missing_ok=True)

    return bytes(buffer)


def write_temporary_file(
    prefix: str,
    suffix: str,
    content: bytes,
) -> Path:
    temporary_file = tempfile.NamedTemporaryFile(
        prefix=prefix,
        suffix=suffix,
        delete=False,
    )
    temporary_path = Path(temporary_file.name)

    try:
        temporary_file.write(content)
    finally:
        temporary_file.close()

    return temporary_path