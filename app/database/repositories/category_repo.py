"""Category repository."""
from typing import List, Optional

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.category import CategoryType, TransactionCategory
from app.database.repositories.base_repo import BaseRepository


class CategoryRepository(BaseRepository[TransactionCategory]):
    """Repository for category operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(TransactionCategory, session)

    async def get_categories(
        self,
        user_id: int,
        category_type: CategoryType,
    ) -> List[TransactionCategory]:
        """Get system + user categories for a specific type."""
        result = await self.session.execute(
            select(TransactionCategory)
            .where(
                and_(
                    TransactionCategory.type == category_type,
                    TransactionCategory.is_active.is_(True),
                    or_(
                        TransactionCategory.user_id.is_(None),   # System categories
                        TransactionCategory.user_id == user_id,  # User categories
                    ),
                )
            )
            .order_by(
                TransactionCategory.is_default.desc(),
                TransactionCategory.name,
            )
        )
        return list(result.scalars().all())

    async def create_custom_category(
        self,
        user_id: int,
        name: str,
        category_type: CategoryType,
        icon: str = "📁",
    ) -> TransactionCategory:
        """Create a user-defined category."""
        return await self.create(
            user_id=user_id,
            name=name,
            type=category_type,
            icon=icon,
            is_default=False,
        )

    async def get_by_id_and_user(
        self, category_id: int, user_id: int
    ) -> Optional[TransactionCategory]:
        """Get category with ownership check (system or user's own)."""
        result = await self.session.execute(
            select(TransactionCategory).where(
                and_(
                    TransactionCategory.id == category_id,
                    TransactionCategory.is_active.is_(True),
                    or_(
                        TransactionCategory.user_id.is_(None),
                        TransactionCategory.user_id == user_id,
                    ),
                )
            )
        )
        return result.scalar_one_or_none()
