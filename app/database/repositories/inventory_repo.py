"""Inventory transaction repository."""
from decimal import Decimal
from typing import List

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.database.models.inventory import InventoryTransaction, InventoryTransactionType
from app.database.repositories.base_repo import BaseRepository


class InventoryRepository(BaseRepository[InventoryTransaction]):
    """Repository for inventory operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(InventoryTransaction, session)

    async def add_inventory_transaction(
        self,
        product_id: int,
        user_id: int,
        type: InventoryTransactionType,
        quantity: Decimal,
        price: Decimal = None,
        transaction_id: int = None,
        description: str = None,
    ) -> InventoryTransaction:
        """Record an inventory movement."""
        return await self.create(
            product_id=product_id,
            user_id=user_id,
            type=type,
            quantity=quantity,
            price=price,
            transaction_id=transaction_id,
            description=description,
        )

    async def get_product_history(
        self, product_id: int, user_id: int, limit: int = 20
    ) -> List[InventoryTransaction]:
        """Get inventory history for a product."""
        result = await self.session.execute(
            select(InventoryTransaction)
            .where(
                and_(
                    InventoryTransaction.product_id == product_id,
                    InventoryTransaction.user_id == user_id,
                )
            )
            .order_by(InventoryTransaction.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
