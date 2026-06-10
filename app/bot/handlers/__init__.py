from app.bot.handlers.birthdays import router as birthdays_router
from app.bot.handlers.children import router as children_router
from app.bot.handlers.help import router as help_router
from app.bot.handlers.language import router as language_router
from app.bot.handlers.people import router as people_router
from app.bot.handlers.relationships import router as relationships_router
from app.bot.handlers.settings import router as settings_router
from app.bot.handlers.start import router as start_router

routers = (
    start_router,
    help_router,
    language_router,
    relationships_router,
    children_router,
    birthdays_router,
    settings_router,
    people_router,
)

__all__ = ["routers"]