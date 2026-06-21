import asyncio
import logging
import uvicorn

from aiogram.exceptions import TelegramNetworkError

from config import settings
from database import async_engine
from models import Base
from bot import bot, dp
from bot.handlers import handlers_router
from bot.middlewares import ApprovalMiddleware
from scheduler import scheduler, check_and_process_pending_campaigns
from web_app import web_app

logger = logging.getLogger("main")

async def run_bot_polling():
    """Keep retrying Telegram polling when the API is temporarily unreachable."""
    while True:
        try:
            await dp.start_polling(bot)
            return
        except TelegramNetworkError as exc:
            logger.warning("Telegram API unreachable (%s). Retrying in 30 seconds...", exc)
            await asyncio.sleep(30)

async def main():
    # 1. Boot database tables dynamically (creates missing tables on start)
    logger.info("Initializing SQLAlchemy database models...")
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 2. Wire Telegram Bot structures
    dp.message.middleware(ApprovalMiddleware())
    dp.callback_query.middleware(ApprovalMiddleware())
    dp.include_router(handlers_router)

    # 3. Schedule the recurring Campaign Queue Scanner (check pending jobs every 30 seconds)
    logger.info("Scheduling Campaign Queue Scanner job...")
    scheduler.add_job(
        check_and_process_pending_campaigns,
        trigger='interval',
        seconds=30,
        id="campaign_queue_scanner",
        replace_existing=True
    )

    # 4. Initialize background scheduling engine
    logger.info("Booting background campaign scheduler...")
    scheduler.start()

    # 5. Set up non-blocking HTTP web server configuration
    web_config = uvicorn.Config(
        app=web_app, 
        host="0.0.0.0", 
        port=8000, 
        log_level="info", 
        loop="asyncio"
    )
    web_server = uvicorn.Server(web_config)

    # 6. Gather and execute polling loops concurrently in the main event loop
    logger.info("Launching Bot Polling Loop and FastAPI endpoints concurrently...")
    try:
        await asyncio.gather(
            run_bot_polling(),
            web_server.serve()
        )
    except (KeyboardInterrupt, SystemExit):
        logger.info("Application shutting down gracefully...")
    finally:
        if scheduler.running:
            scheduler.shutdown()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
