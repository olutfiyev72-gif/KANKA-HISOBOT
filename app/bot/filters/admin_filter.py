"""Admin filter - only allows admin users."""
from aiogram.filters import BaseFilter
from aiogram.types import Message

from app.database.models.user import User


class AdminFilter(BaseFilter):
    """Filter to allow only admin users."""

    async def __call__(self, message: Message, user: User = None) -> bool:
        if user is None:
            return False
        return user.is_admin
