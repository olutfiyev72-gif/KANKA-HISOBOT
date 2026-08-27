"""Product repository."""
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.product import Product
from app.database.models.inventory import InventoryTransaction, InventoryTransactionType
from app.database.repositories.base_repo import BaseRepository


class ProductRepository(BaseRepository[Product]):
    """Repository for product operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(Product, session)

    async def get_user_products(
        self, user_id: int, active_only: bool = True
    ) -> List[Product]:
        """Get all products for a user."""
        conditions = [Product.user_id == user_id]
        if active_only:
            conditions.append(Product.is_active.is_(True))

        result = await self.session.execute(
            select(Product)
            .where(and_(*conditions))
            .order_by(Product.name)
        )
        return list(result.scalars().all())

    async def get_by_id_and_user(
        self, product_id: int, user_id: int
    ) -> Optional[Product]:
        """Get product by ID with user ownership check."""
        result = await self.session.execute(
            select(Product).where(
                and_(
                    Product.id == product_id,
                    Product.user_id == user_id,
                    Product.is_active.is_(True),
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_by_sku(self, sku: str, user_id: int) -> Optional[Product]:
        """Get product by SKU."""
        result = await self.session.execute(
            select(Product).where(
                and_(Product.sku == sku, Product.user_id == user_id)
            )
        )
        return result.scalar_one_or_none()

    async def update_quantity(
        self, product: Product, quantity_change: Decimal
    ) -> Product:
        """Update product quantity (positive = add, negative = subtract)."""
        new_qty = product.quantity + quantity_change
        if new_qty < 0:
            raise ValueError(
                f"Yetarli mahsulot yo'q. Mavjud: {product.quantity} {product.unit}"
            )
        product.quantity = new_qty
        return await self.save(product)

    async def get_low_stock(
        self, user_id: int, threshold: Decimal = Decimal("5")
    ) -> List[Product]:
        """Get products with low stock."""
        result = await self.session.execute(
            select(Product).where(
                and_(
                    Product.user_id == user_id,
                    Product.is_active.is_(True),
                    Product.quantity <= threshold,
                )
            ).order_by(Product.quantity)
        )
        return list(result.scalars().all())

    async def get_best_sellers(
        self, user_id: int, limit: int = 5
    ) -> List[tuple]:
        """Get most sold products by quantity."""
        result = await self.session.execute(
            select(
                Product.name,
                func.sum(InventoryTransaction.quantity).label("total_sold"),
                func.sum(
                    InventoryTransaction.quantity * Product.selling_price
                ).label("total_revenue"),
            )
            .join(Product, InventoryTransaction.product_id == Product.id)
            .where(
                and_(
                    Product.user_id == user_id,
                    InventoryTransaction.type == InventoryTransactionType.SALE,
                )
            )
            .group_by(Product.id, Product.name)
            .order_by(func.sum(InventoryTransaction.quantity).desc())
            .limit(limit)
        )
        return result.all()

    async def get_most_profitable(
        self, user_id: int, limit: int = 5
    ) -> List[Product]:
        """Get most profitable products by margin."""
        result = await self.session.execute(
            select(Product)
            .where(
                and_(
                    Product.user_id == user_id,
                    Product.is_active.is_(True),
                )
            )
            .order_by((Product.selling_price - Product.cost_price).desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def deactivate(self, product: Product) -> Product:
        """Soft delete product."""
        product.is_active = False
        return await self.save(product)
