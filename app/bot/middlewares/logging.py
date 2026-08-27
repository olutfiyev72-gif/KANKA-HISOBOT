"""Logging middleware - logs all incoming messages and callbacks."""
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject, Update
from loguru import logger


class LoggingMiddleware(BaseMiddleware):
    """Middleware to log all incoming events."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        tg_user = data.get("event_from_user")
        user_str = f"{tg_user.id} (@{tg_user.username})" if tg_user else "unknown"

        if isinstance(event, Update):
            if event.message and event.message.text:
                logger.info(f"Incoming message from {user_str}: {event.message.text!r}")
            elif event.callback_query and event.callback_query.data:
                logger.info(f"Incoming callback from {user_str}: {event.callback_query.data!r}")
        elif isinstance(event, Message) and event.text:
            logger.info(f"Incoming message from {user_str}: {event.text!r}")
        elif isinstance(event, CallbackQuery) and event.data:
            logger.info(f"Incoming callback from {user_str}: {event.data!r}")

        return await handler(event, data)
