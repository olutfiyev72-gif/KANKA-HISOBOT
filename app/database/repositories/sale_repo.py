"""Sale repository."""
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config.constants import PaymentMethod
from app.database.models.customer import Customer
from app.database.models.sale import Sale, SaleItem
from app.database.repositories.base_repo import BaseRepository


class SaleRepository(BaseRepository[Sale]):
    """Repository for managing sales orders and items."""

    def __init__(self, session: AsyncSession):
        super().__init__(Sale, session)

    async def create_sale(
        self,
        user_id: int,
        total_amount: Decimal,
        paid_amount: Decimal,
        debt_amount: Decimal,
        payment_method: PaymentMethod = PaymentMethod.CASH,
        customer_id: Optional[int] = None,
        description: Optional[str] = None,
        sale_date: Optional[datetime] = None,
        items_data: Optional[List[Dict[str, Any]]] = None,
    ) -> Sale:
        """Create a new sale order with line items."""
        now = sale_date or datetime.now()
        sale = Sale(
            user_id=user_id,
            customer_id=customer_id,
            total_amount=total_amount,
            paid_amount=paid_amount,
            debt_amount=debt_amount,
            payment_method=payment_method,
            description=description,
            sale_date=now,
            is_deleted=False,
        )
        self.session.add(sale)
        await self.session.flush()

        if items_data:
            for item in items_data:
                sale_item = SaleItem(
                    sale_id=sale.id,
                    product_id=item.get("product_id"),
                    product_name=item["product_name"],
                    unit=item.get("unit", "dona"),
                    quantity=item["quantity"],
                    unit_price=item["unit_price"],
                    total_price=item["total_price"],
                    cost_price=item.get("cost_price", Decimal("0.00")),
                )
                self.session.add(sale_item)
            await self.session.flush()

        # Reload with relationships
        return await self.get_by_id_and_user(sale.id, user_id) or sale

    async def get_by_id_and_user(
        self, sale_id: int, user_id: int
    ) -> Optional[Sale]:
        """Fetch sale by ID with ownership verification and loaded items."""
        result = await self.session.execute(
            select(Sale)
            .options(selectinload(Sale.items), selectinload(Sale.customer))
            .where(
                and_(
                    Sale.id == sale_id,
                    Sale.user_id == user_id,
                    Sale.is_deleted.is_(False),
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_user_sales(
        self,
        user_id: int,
        limit: int = 20,
        offset: int = 0,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> List[Sale]:
        """Get paginated sales for a user."""
        conditions = [Sale.user_id == user_id, Sale.is_deleted.is_(False)]
        if date_from:
            conditions.append(Sale.sale_date >= date_from)
        if date_to:
            conditions.append(Sale.sale_date <= date_to)

        result = await self.session.execute(
            select(Sale)
            .options(selectinload(Sale.items), selectinload(Sale.customer))
            .where(and_(*conditions))
            .order_by(Sale.sale_date.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def get_today_sales(self, user_id: int) -> List[Sale]:
        """Get all sales created today."""
        now = datetime.now()
        start_of_day = datetime(now.year, now.month, now.day, 0, 0, 0)
        end_of_day = datetime(now.year, now.month, now.day, 23, 59, 59)
        return await self.get_user_sales(
            user_id=user_id,
            limit=50,
            date_from=start_of_day,
            date_to=end_of_day,
        )

    async def search_sales(
        self, user_id: int, query: str, limit: int = 20
    ) -> List[Sale]:
        """Search sales by customer name, product name, or description."""
        clean_query = f"%{query.strip().lower()}%"
        result = await self.session.execute(
            select(Sale)
            .options(selectinload(Sale.items), selectinload(Sale.customer))
            .outerjoin(Sale.customer)
            .outerjoin(Sale.items)
            .where(
                and_(
                    Sale.user_id == user_id,
                    Sale.is_deleted.is_(False),
                    or_(
                        func.lower(Customer.name).like(clean_query),
                        func.lower(SaleItem.product_name).like(clean_query),
                        func.lower(Sale.description).like(clean_query),
                    ),
                )
            )
            .order_by(Sale.sale_date.desc())
            .limit(limit)
            .distinct()
        )
        return list(result.scalars().all())

    async def get_summary(
        self,
        user_id: int,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> dict:
        """Get aggregate metrics for sales."""
        conditions = [Sale.user_id == user_id, Sale.is_deleted.is_(False)]
        if date_from:
            conditions.append(Sale.sale_date >= date_from)
        if date_to:
            conditions.append(Sale.sale_date <= date_to)

        result = await self.session.execute(
            select(
                func.count(Sale.id).label("count"),
                func.coalesce(func.sum(Sale.total_amount), Decimal("0")).label("total_amount"),
                func.coalesce(func.sum(Sale.paid_amount), Decimal("0")).label("paid_amount"),
                func.coalesce(func.sum(Sale.debt_amount), Decimal("0")).label("debt_amount"),
            ).where(and_(*conditions))
        )
        row = result.one()
        return {
            "total_sales_count": row.count or 0,
            "total_sales_amount": row.total_amount or Decimal("0.00"),
            "total_paid_amount": row.paid_amount or Decimal("0.00"),
            "total_debt_amount": row.debt_amount or Decimal("0.00"),
        }
