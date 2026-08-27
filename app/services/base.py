"""Base service layer."""
from typing import Generic, TypeVar
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


class BaseService:
    """Base class for all business services."""

    def __init__(self, session: AsyncSession):
        self.session = session
