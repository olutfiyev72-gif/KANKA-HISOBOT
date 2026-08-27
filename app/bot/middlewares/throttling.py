"""Throttling middleware - rate limiting."""
import asyncio
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject
from loguru import logger

from app.config import settings


class ThrottlingMiddleware(BaseMiddleware):
    """Simple throttling middleware using asyncio locks."""

    def __init__(self, throttle_time: float = None):
        self.throttle_time = throttle_time or settings.throttle_rate
        self._locks: Dict[int, asyncio.Lock] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        if not isinstance(event, Message):
            return await handler(event, data)

        user_id = event.from_user.id if event.from_user else None
        if not user_id:
            return await handler(event, data)

        if user_id not in self._locks:
            self._locks[user_id] = asyncio.Lock()

        lock = self._locks[user_id]
        if lock.locked():
            logger.warning(f"Throttled user {user_id}")
            return

        async with lock:
            result = await handler(event, data)
            await asyncio.sleep(self.throttle_time)
            return result
