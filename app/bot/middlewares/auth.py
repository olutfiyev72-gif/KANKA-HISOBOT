"""Authentication middleware - registers users and checks their status."""
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject, Update
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.models.user import User, UserStatus
from app.database.repositories.user_repo import UserRepository


class AuthMiddleware(BaseMiddleware):
    """Middleware to authenticate users and inject user object into handler data."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        # Extract telegram user from data or event
        tg_user = data.get("event_from_user")
        if not tg_user:
            if isinstance(event, Update):
                if event.message:
                    tg_user = event.message.from_user
                elif event.callback_query:
                    tg_user = event.callback_query.from_user
            elif isinstance(event, Message):
                tg_user = event.from_user
            elif isinstance(event, CallbackQuery):
                tg_user = event.from_user

        if not tg_user:
            return await handler(event, data)

        session: AsyncSession = data.get("session")
        if not session:
            return await handler(event, data)

        user_repo = UserRepository(session)

        # Get or create user
        user, is_new = await user_repo.get_or_create(
            telegram_id=tg_user.id,
            full_name=tg_user.full_name or "Foydalanuvchi",
            username=tg_user.username,
        )

        admin_ids = settings.get_admin_ids()
        # If user is in admin list or if no admins configured (single user mode), grant admin and activate
        if not admin_ids or tg_user.id in admin_ids:
            if not user.is_admin:
                await user_repo.set_admin(user, True)
                user.is_admin = True
            if user.status != UserStatus.ACTIVE:
                await user_repo.activate_user(user)
                user.status = UserStatus.ACTIVE
        elif user.status == UserStatus.PENDING and settings.is_development:
            # Auto-activate in development mode
            await user_repo.activate_user(user)
            user.status = UserStatus.ACTIVE

        # Check if user is blocked
        if user.status == UserStatus.BLOCKED:
            if isinstance(event, Message):
                await event.answer("❌ Sizning hisobingiz bloklangan.")
            elif isinstance(event, CallbackQuery):
                await event.answer("❌ Hisob bloklangan", show_alert=True)
            elif isinstance(event, Update) and event.message:
                await event.message.answer("❌ Sizning hisobingiz bloklangan.")
            return

        # Check if user is pending (awaiting admin approval)
        if user.status == UserStatus.PENDING:
            if (
                isinstance(event, Message)
                and event.text
                and event.text.startswith("/start")
            ) or (
                isinstance(event, Update)
                and event.message
                and event.message.text
                and event.message.text.startswith("/start")
            ):
                data["user"] = user
                data["is_new_user"] = True
                return await handler(event, data)

            msg = "⏳ Sizning hisobingiz tasdiqlanishi kutilmoqda."
            if isinstance(event, Message):
                await event.answer(msg)
            elif isinstance(event, CallbackQuery):
                await event.answer(msg, show_alert=True)
            elif isinstance(event, Update) and event.message:
                await event.message.answer(msg)
            return

        # Inject user into handler data
        data["user"] = user
        data["is_new_user"] = False

        return await handler(event, data)
