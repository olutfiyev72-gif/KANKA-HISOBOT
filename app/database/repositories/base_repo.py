"""Base repository with common CRUD operations."""
from typing import Generic, List, Optional, Type, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """Generic base repository."""

    def __init__(self, model: Type[ModelType], session: AsyncSession):
        self.model = model
        self.session = session

    async def get_by_id(self, id: int) -> Optional[ModelType]:
        """Get record by primary key."""
        return await self.session.get(self.model, id)

    async def get_all(self) -> List[ModelType]:
        """Get all records."""
        result = await self.session.execute(select(self.model))
        return list(result.scalars().all())

    async def create(self, **kwargs) -> ModelType:
        """Create a new record."""
        instance = self.model(**kwargs)
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def update(self, instance: ModelType, **kwargs) -> ModelType:
        """Update an existing record."""
        for key, value in kwargs.items():
            setattr(instance, key, value)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def delete(self, instance: ModelType) -> None:
        """Hard delete a record."""
        await self.session.delete(instance)
        await self.session.flush()

    async def save(self, instance: ModelType) -> ModelType:
        """Save changes to an instance."""
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance
