"""Main application entry point."""
import asyncio
import sys
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ErrorEvent
from loguru import logger

from app.bot.handlers import get_all_routers
from app.bot.middlewares import (
    AuthMiddleware,
    DatabaseMiddleware,
    LoggingMiddleware,
    ThrottlingMiddleware,
)
from app.config import settings
from app.database.base import create_tables, get_session_maker
from app.database.seeder import seed_categories


def setup_logging() -> None:
    """Configure loguru logging."""
    Path("logs").mkdir(exist_ok=True)
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=settings.log_level,
        colorize=True,
    )
    logger.add(
        settings.log_file,
        rotation="10 MB",
        retention="30 days",
        compression="zip",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
        level="DEBUG",
    )


async def setup_database() -> None:
    """Initialize database tables and seed default categories."""
    logger.info("Initializing database and tables...")
    await create_tables()
    async with get_session_maker()() as session:
        await seed_categories(session)
    logger.info("Database initialized and ready.")


def create_bot() -> Bot:
    """Create and configure bot instance."""
    if not settings.bot_token:
        logger.error(
            "❌ BOT_TOKEN is missing! Please create a .env file and set BOT_TOKEN=<your_telegram_bot_token>"
        )
        sys.exit(1)

    return Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def create_dispatcher() -> Dispatcher:
    """Create and configure dispatcher with middlewares and all routers."""
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Register middlewares (Execution order: Logging -> Database -> Auth -> Throttling)
    dp.update.outer_middleware(LoggingMiddleware())
    dp.update.outer_middleware(DatabaseMiddleware())
    dp.update.outer_middleware(AuthMiddleware())
    dp.message.middleware(ThrottlingMiddleware())

    # Register all 12 feature routers
    routers = get_all_routers()
    router_names = [r.name or getattr(r, "__name__", f"Router_{i}") for i, r in enumerate(routers)]
    logger.info(f"Registering {len(routers)} routers: {', '.join(router_names)}")

    for router in routers:
        dp.include_router(router)

    # Global error handler
    @dp.error()
    async def global_error_handler(event_data: ErrorEvent):
        exception = event_data.exception
        logger.error(f"Unhandled error: {type(exception).__name__}: {exception}")
        try:
            update = event_data.update
            if update and update.message:
                await update.message.answer(
                    "❌ Kutilmagan xatolik yuz berdi. Iltimos qayta urinib ko'ring.\n"
                    "/start ni bosing."
                )
            elif update and update.callback_query:
                await update.callback_query.answer(
                    "❌ Kutilmagan xatolik yuz berdi.", show_alert=True
                )
        except Exception:
            pass
        return True

    return dp


async def on_startup(bot: Bot) -> None:
    """Actions to run on bot startup."""
    me = await bot.get_me()
    logger.info(
        f"🤖 Bot connected successfully: @{me.username} (ID: {me.id}, Name: '{me.first_name}')"
    )
    logger.info(f"🌍 Environment: {settings.environment} | Timezone: {settings.default_timezone}")

    # Notify admins if configured
    admin_ids = settings.get_admin_ids()
    if admin_ids:
        logger.info(f"Found {len(admin_ids)} admin ID(s) configured.")
        for admin_id in admin_ids:
            try:
                await bot.send_message(
                    admin_id,
                    f"✅ <b>Bot ishga tushdi!</b>\n\n"
                    f"🤖 @{me.username}\n"
                    f"🌐 Environment: {settings.environment}\n"
                    f"⏰ Vaqt: {settings.default_timezone}",
                )
            except Exception as e:
                logger.warning(f"Could not notify admin {admin_id}: {e}")


async def on_shutdown(bot: Bot) -> None:
    """Actions to run on bot shutdown."""
    logger.info("Bot shutting down gracefully...")
    admin_ids = settings.get_admin_ids()
    for admin_id in admin_ids:
        try:
            await bot.send_message(admin_id, "⚠️ Bot to'xtatildi.")
        except Exception:
            pass


async def main() -> None:
    """Main application entry point."""
    setup_logging()
    logger.info(f"=== Starting {settings.bot_name} ===")

    await setup_database()

    bot = create_bot()
    dp = create_dispatcher()

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    try:
        logger.info("Starting Telegram long polling...")
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
            drop_pending_updates=True,
        )
    except (asyncio.CancelledError, KeyboardInterrupt):
        logger.info("Bot execution cancelled.")
    finally:
        await bot.session.close()
        logger.info("Bot session closed. Goodbye!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
