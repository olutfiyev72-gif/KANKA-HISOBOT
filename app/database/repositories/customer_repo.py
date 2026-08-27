"""Customer repository."""
from decimal import Decimal
from typing import List, Optional
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.customer import Customer
from app.database.repositories.base_repo import BaseRepository


class CustomerRepository(BaseRepository[Customer]):
    """Repository for customer CRM operations with user isolation."""

    def __init__(self, session: AsyncSession):
        super().__init__(Customer, session)

    async def create_customer(
        self,
        user_id: int,
        name: str,
        phone: Optional[str] = None,
        telegram_username: Optional[str] = None,
        telegram_user_id: Optional[int] = None,
        notifications_enabled: bool = True,
    ) -> Customer:
        """Create a new customer linked to a user."""
        customer = Customer(
            user_id=user_id,
            name=name.strip(),
            phone=phone.strip() if phone else None,
            telegram_username=telegram_username.strip().lstrip("@") if telegram_username else None,
            telegram_user_id=telegram_user_id,
            notifications_enabled=notifications_enabled,
            total_purchases=Decimal("0.00"),
            total_paid=Decimal("0.00"),
            total_debt=Decimal("0.00"),
            is_active=True,
        )
        self.session.add(customer)
        await self.session.flush()
        return customer

    async def get_by_id_and_user(
        self, customer_id: int, user_id: int
    ) -> Optional[Customer]:
        """Get customer with user ownership check."""
        result = await self.session.execute(
            select(Customer).where(
                and_(
                    Customer.id == customer_id,
                    Customer.user_id == user_id,
                )
            )
        )
        return result.scalar_one_or_none()

    async def search_customers(
        self, user_id: int, query: str, limit: int = 20, offset: int = 0
    ) -> List[Customer]:
        """Search customers by name, phone, or username."""
        clean_query = f"%{query.strip().lower()}%"
        result = await self.session.execute(
            select(Customer)
            .where(
                and_(
                    Customer.user_id == user_id,
                    or_(
                        func.lower(Customer.name).like(clean_query),
                        Customer.phone.like(clean_query),
                        func.lower(Customer.telegram_username).like(clean_query),
                    ),
                )
            )
            .order_by(Customer.name.asc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def get_user_customers(
        self,
        user_id: int,
        active_only: bool = True,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Customer]:
        """Get paginated list of customers."""
        conditions = [Customer.user_id == user_id]
        if active_only:
            conditions.append(Customer.is_active.is_(True))

        result = await self.session.execute(
            select(Customer)
            .where(and_(*conditions))
            .order_by(Customer.name.asc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def update_balances(
        self,
        customer: Customer,
        purchase_amount: Decimal,
        paid_amount: Decimal,
        new_debt: Decimal,
    ) -> Customer:
        """Update customer financial totals with exact Decimal precision."""
        customer.total_purchases += purchase_amount
        customer.total_paid += paid_amount
        customer.total_debt += new_debt
        await self.session.flush()
        return customer

    async def record_debt_payment(
        self,
        customer: Customer,
        payment_amount: Decimal,
    ) -> Customer:
        """Apply debt payment to customer totals."""
        customer.total_paid += payment_amount
        customer.total_debt = max(Decimal("0.00"), customer.total_debt - payment_amount)
        await self.session.flush()
        return customer

    async def count_user_customers(self, user_id: int) -> int:
        """Count total customers of a user."""
        result = await self.session.execute(
            select(func.count(Customer.id)).where(Customer.user_id == user_id)
        )
        return result.scalar() or 0

    async def get_summary(self, user_id: int) -> dict:
        """Compute aggregated CRM stats for user."""
        result = await self.session.execute(
            select(
                func.count(Customer.id).label("total"),
                func.count(Customer.id).filter(Customer.is_active.is_(True)).label("active"),
                func.count(Customer.id).filter(Customer.total_debt > Decimal("0")).label("debtors"),
                func.coalesce(func.sum(Customer.total_debt), Decimal("0")).label("total_debt"),
                func.coalesce(func.sum(Customer.total_purchases), Decimal("0")).label("total_purchases"),
            ).where(Customer.user_id == user_id)
        )
        row = result.one()
        return {
            "total_customers": row.total or 0,
            "active_customers": row.active or 0,
            "total_debtors": row.debtors or 0,
            "total_customer_debt": row.total_debt or Decimal("0.00"),
            "total_customer_purchases": row.total_purchases or Decimal("0.00"),
        }
