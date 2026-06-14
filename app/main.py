from __future__ import annotations

import asyncio
from urllib.parse import urlparse

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from loguru import logger

from app.bot.handlers import routers
from app.bot.middlewares.auth import CurrentUserMiddleware
from app.bot.middlewares.db import DatabaseSessionMiddleware
from app.bot.middlewares.i18n import I18nMiddleware
from app.config import Settings, get_settings
from app.db.session import close_engine, get_session_maker, init_db
from app.logging import setup_logging
from app.services.backup_trigger import configure_backup_trigger, shutdown_backup_trigger
from app.services.i18n import I18nService
from app.services.scheduler_service import SchedulerService


async def health_handler(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


def setup_dispatcher(settings: Settings, i18n: I18nService) -> Dispatcher:
    session_maker = init_db(settings.DATABASE_URL, echo=settings.DB_ECHO)

    dispatcher = Dispatcher()

    database_middleware = DatabaseSessionMiddleware(session_maker)
    current_user_middleware = CurrentUserMiddleware(
        admin_ids=settings.admin_ids_set,
        default_timezone=settings.DEFAULT_TIMEZONE,
    )
    i18n_middleware = I18nMiddleware(
        i18n=i18n,
        default_language=settings.DEFAULT_LANGUAGE,
    )

    for observer in (dispatcher.message, dispatcher.callback_query):
        observer.outer_middleware(database_middleware)
        observer.outer_middleware(current_user_middleware)
        observer.outer_middleware(i18n_middleware)

    for router in routers:
        dispatcher.include_router(router)

    return dispatcher


async def start_health_server(settings: Settings) -> web.AppRunner:
    app = web.Application()
    app.router.add_get("/health", health_handler)

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, settings.HOST, settings.PORT)
    await site.start()

    logger.info(f"Health endpoint started on {settings.HOST}:{settings.PORT}")
    return runner


async def run_polling(bot: Bot, dispatcher: Dispatcher, settings: Settings) -> None:
    runner = await start_health_server(settings)

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Bot started in long polling mode.")
        await dispatcher.start_polling(bot)
    finally:
        await runner.cleanup()


async def run_webhook(bot: Bot, dispatcher: Dispatcher, settings: Settings) -> None:
    if not settings.WEBHOOK_URL:
        raise RuntimeError("WEBHOOK_URL is required for webhook mode.")

    parsed_url = urlparse(settings.WEBHOOK_URL)
    webhook_path = parsed_url.path or "/webhook"

    app = web.Application()
    app.router.add_get("/health", health_handler)

    webhook_handler = SimpleRequestHandler(
        dispatcher=dispatcher,
        bot=bot,
        secret_token=settings.webhook_secret,
    )
    webhook_handler.register(app, path=webhook_path)
    setup_application(app, dispatcher, bot=bot)

    await bot.set_webhook(
        url=settings.WEBHOOK_URL,
        secret_token=settings.webhook_secret,
        drop_pending_updates=False,
    )

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, settings.HOST, settings.PORT)
    await site.start()

    logger.info(f"Bot started in webhook mode on {settings.HOST}:{settings.PORT}{webhook_path}")

    try:
        await asyncio.Event().wait()
    finally:
        await bot.delete_webhook(drop_pending_updates=False)
        await runner.cleanup()


async def main() -> None:
    settings = get_settings()
    setup_logging(env=settings.ENV, level=settings.LOG_LEVEL)

    i18n = I18nService(default_lang=settings.DEFAULT_LANGUAGE)
    dispatcher = setup_dispatcher(settings=settings, i18n=i18n)
    session_maker = get_session_maker()

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    configure_backup_trigger(
        session_maker=session_maker,
        bot=bot,
        debounce_seconds=45,
        default_language=settings.DEFAULT_LANGUAGE,
    )

    scheduler_service: SchedulerService | None = None

    try:
        if settings.ENABLE_SCHEDULER:
            scheduler_service = SchedulerService(
                bot=bot,
                session_maker=session_maker,
                interval_minutes=settings.REMINDER_CHECK_INTERVAL_MINUTES,
                lookback_minutes=settings.REMINDER_SCHEDULER_LOOKBACK_MINUTES,
            )
            scheduler_service.start()

        if settings.USE_WEBHOOK:
            await run_webhook(bot=bot, dispatcher=dispatcher, settings=settings)
        else:
            await run_polling(bot=bot, dispatcher=dispatcher, settings=settings)
    finally:
        await shutdown_backup_trigger()

        if scheduler_service is not None:
            scheduler_service.shutdown()

        await close_engine()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())