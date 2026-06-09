from app.bot.handlers.help import router as help_router
from app.bot.handlers.language import router as language_router
from app.bot.handlers.people import router as people_router
from app.bot.handlers.start import router as start_router

routers = (
    start_router,
    help_router,
    language_router,
    people_router,
)

__all__ = ["routers"]