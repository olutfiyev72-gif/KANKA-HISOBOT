"""Product & Inventory domain service."""
from decimal import Decimal
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.inventory import InventoryTransactionType
from app.database.models.product import Product
from app.database.repositories.inventory_repo import InventoryRepository
from app.database.repositories.product_repo import ProductRepository
from app.services.base import BaseService


class ProductService(BaseService):
    """Business service orchestrating product and inventory operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(session)
        self.product_repo = ProductRepository(session)
        self.inventory_repo = InventoryRepository(session)

    async def create_product(
        self,
        user_id: int,
        name: str,
        cost_price: Decimal,
        selling_price: Decimal,
        quantity: Decimal = Decimal("0"),
        unit: str = "dona",
        sku: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Product:
        """Create a new product catalog entry."""
        return await self.product_repo.create(
            user_id=user_id,
            name=name,
            cost_price=cost_price,
            selling_price=selling_price,
            quantity=quantity,
            unit=unit,
            sku=sku,
            description=description,
        )

    async def sell_stock(
        self,
        product_id: int,
        user_id: int,
        quantity: Decimal,
        transaction_id: Optional[int] = None,
    ) -> Product:
        """Deduct stock when a product is sold and record inventory movement."""
        product = await self.product_repo.get_by_id_and_user(product_id, user_id)
        if not product:
            raise ValueError("Mahsulot topilmadi")

        updated_product = await self.product_repo.update_quantity(
            product=product,
            quantity_change=-quantity,
        )

        await self.inventory_repo.add_inventory_transaction(
            product_id=product_id,
            user_id=user_id,
            type=InventoryTransactionType.SALE,
            quantity=quantity,
            price=product.selling_price,
            transaction_id=transaction_id,
            description=f"{product.name} sotuvi",
        )

        return updated_product

    async def restock(
        self,
        product_id: int,
        user_id: int,
        quantity: Decimal,
        cost_price: Optional[Decimal] = None,
    ) -> Product:
        """Add stock when restocking."""
        product = await self.product_repo.get_by_id_and_user(product_id, user_id)
        if not product:
            raise ValueError("Mahsulot topilmadi")

        updated_product = await self.product_repo.update_quantity(
            product=product,
            quantity_change=quantity,
        )

        await self.inventory_repo.add_inventory_transaction(
            product_id=product_id,
            user_id=user_id,
            type=InventoryTransactionType.PURCHASE,
            quantity=quantity,
            price=cost_price or product.cost_price,
            description="Kirim / Qayta to'ldirish",
        )

        return updated_product

    async def get_low_stock_alerts(
        self, user_id: int, threshold: Decimal = Decimal("5")
    ) -> List[Product]:
        """Fetch products that have reached min stock threshold."""
        return await self.product_repo.get_low_stock(user_id, threshold=threshold)
