from aiogram import Router
from bot.handlers.common import router as common_router
from bot.handlers.gmail import router as gmail_router
from bot.handlers.lists import router as lists_router
from bot.handlers.campaigns import router as campaigns_router
from bot.handlers.settings import router as settings_router

# Combine all sub-routers
handlers_router = Router()
handlers_router.include_router(common_router)
handlers_router.include_router(gmail_router)
handlers_router.include_router(lists_router)
handlers_router.include_router(campaigns_router)
handlers_router.include_router(settings_router)
