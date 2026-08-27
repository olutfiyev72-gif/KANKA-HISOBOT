"""Transaction repository."""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Tuple

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.database.models.transaction import (
    PaymentMethod, Transaction, TransactionType,
)
from app.database.repositories.base_repo import BaseRepository


class TransactionRepository(BaseRepository[Transaction]):
    """Repository for transaction operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(Transaction, session)

    async def create_transaction(
        self,
        user_id: int,
        type: TransactionType,
        amount: Decimal,
        transaction_date: datetime,
        category_id: Optional[int] = None,
        payment_method: PaymentMethod = PaymentMethod.CASH,
        description: Optional[str] = None,
        product_id: Optional[int] = None,
        product_quantity: Optional[Decimal] = None,
    ) -> Transaction:
        """Create a new transaction."""
        return await self.create(
            user_id=user_id,
            type=type,
            amount=amount,
            category_id=category_id,
            payment_method=payment_method,
            description=description,
            transaction_date=transaction_date,
            product_id=product_id,
            product_quantity=product_quantity,
        )

    async def get_user_transactions(
        self,
        user_id: int,
        limit: int = 10,
        offset: int = 0,
        type: Optional[TransactionType] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[Transaction]:
        """Get user transactions with filters."""
        conditions = [
            Transaction.user_id == user_id,
            Transaction.is_deleted.is_(False),
        ]
        if type:
            conditions.append(Transaction.type == type)
        if start_date:
            conditions.append(Transaction.transaction_date >= start_date)
        if end_date:
            conditions.append(Transaction.transaction_date <= end_date)

        result = await self.session.execute(
            select(Transaction)
            .options(joinedload(Transaction.category))
            .where(and_(*conditions))
            .order_by(Transaction.transaction_date.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def get_summary(
        self,
        user_id: int,
        start_date: datetime,
        end_date: datetime,
    ) -> dict:
        """Get income/expense summary for a period."""
        result = await self.session.execute(
            select(
                Transaction.type,
                func.sum(Transaction.amount).label("total"),
                func.count(Transaction.id).label("count"),
            )
            .where(
                and_(
                    Transaction.user_id == user_id,
                    Transaction.is_deleted.is_(False),
                    Transaction.transaction_date >= start_date,
                    Transaction.transaction_date <= end_date,
                )
            )
            .group_by(Transaction.type)
        )
        rows = result.all()
        summary = {
            "income": Decimal("0"),
            "expense": Decimal("0"),
            "income_count": 0,
            "expense_count": 0,
        }
        for row in rows:
            if row.type == TransactionType.INCOME:
                summary["income"] = row.total or Decimal("0")
                summary["income_count"] = row.count or 0
            elif row.type == TransactionType.EXPENSE:
                summary["expense"] = row.total or Decimal("0")
                summary["expense_count"] = row.count or 0
        summary["profit"] = summary["income"] - summary["expense"]
        if summary["income"] > 0:
            summary["margin"] = (
                summary["profit"] / summary["income"] * 100
            ).quantize(Decimal("0.01"))
        else:
            summary["margin"] = Decimal("0")
        return summary

    async def get_cash_summary(
        self,
        user_id: int,
    ) -> dict:
        """Get cash balance by payment method."""
        result = await self.session.execute(
            select(
                Transaction.type,
                Transaction.payment_method,
                func.sum(Transaction.amount).label("total"),
            )
            .where(
                and_(
                    Transaction.user_id == user_id,
                    Transaction.is_deleted.is_(False),
                )
            )
            .group_by(Transaction.type, Transaction.payment_method)
        )
        rows = result.all()

        methods = {m.value: Decimal("0") for m in PaymentMethod}
        totals = {"income": Decimal("0"), "expense": Decimal("0")}

        for row in rows:
            amount = row.total or Decimal("0")
            if row.type == TransactionType.INCOME:
                methods[row.payment_method.value] += amount
                totals["income"] += amount
            else:
                methods[row.payment_method.value] -= amount
                totals["expense"] += amount

        return {
            "cash": methods.get("cash", Decimal("0")),
            "card": methods.get("card", Decimal("0")),
            "bank": methods.get("bank", Decimal("0")),
            "other": methods.get("other", Decimal("0")),
            "total_income": totals["income"],
            "total_expense": totals["expense"],
            "balance": totals["income"] - totals["expense"],
        }

    async def get_by_category(
        self,
        user_id: int,
        start_date: datetime,
        end_date: datetime,
        transaction_type: TransactionType,
    ) -> List[Tuple]:
        """Get totals grouped by category."""
        from app.database.models.category import TransactionCategory
        result = await self.session.execute(
            select(
                TransactionCategory.name,
                TransactionCategory.icon,
                func.sum(Transaction.amount).label("total"),
                func.count(Transaction.id).label("count"),
            )
            .join(TransactionCategory, Transaction.category_id == TransactionCategory.id, isouter=True)
            .where(
                and_(
                    Transaction.user_id == user_id,
                    Transaction.type == transaction_type,
                    Transaction.is_deleted.is_(False),
                    Transaction.transaction_date >= start_date,
                    Transaction.transaction_date <= end_date,
                )
            )
            .group_by(TransactionCategory.name, TransactionCategory.icon)
            .order_by(func.sum(Transaction.amount).desc())
        )
        return result.all()

    async def soft_delete(self, transaction_id: int, user_id: int) -> bool:
        """Soft delete a transaction (user ownership check)."""
        result = await self.session.execute(
            select(Transaction).where(
                and_(
                    Transaction.id == transaction_id,
                    Transaction.user_id == user_id,
                    Transaction.is_deleted.is_(False),
                )
            )
        )
        transaction = result.scalar_one_or_none()
        if not transaction:
            return False
        transaction.is_deleted = True
        await self.session.flush()
        return True

    async def get_user_transaction(
        self, transaction_id: int, user_id: int
    ) -> Optional[Transaction]:
        """Get transaction by ID with user ownership check."""
        result = await self.session.execute(
            select(Transaction)
            .options(joinedload(Transaction.category))
            .where(
                and_(
                    Transaction.id == transaction_id,
                    Transaction.user_id == user_id,
                    Transaction.is_deleted.is_(False),
                )
            )
        )
        return result.scalar_one_or_none()

    async def update_transaction(
        self,
        transaction_id: int,
        user_id: int,
        amount: Optional[Decimal] = None,
        category_id: Optional[int] = None,
        payment_method: Optional[PaymentMethod] = None,
        description: Optional[str] = None,
        transaction_date: Optional[datetime] = None,
    ) -> Optional[Transaction]:
        """Update an existing transaction with ownership check."""
        tx = await self.get_user_transaction(transaction_id, user_id)
        if not tx:
            return None
        if amount is not None:
            tx.amount = amount
        if category_id is not None:
            tx.category_id = category_id
        if payment_method is not None:
            tx.payment_method = payment_method
        if description is not None:
            tx.description = description
        if transaction_date is not None:
            tx.transaction_date = transaction_date
        await self.session.flush()
        return tx

    async def count_all(self) -> int:
        """Count all non-deleted transactions (admin)."""
        result = await self.session.execute(
            select(func.count(Transaction.id)).where(
                Transaction.is_deleted.is_(False)
            )
        )
        return result.scalar() or 0

    async def get_daily_totals(
        self, user_id: int, start_date: datetime, end_date: datetime
    ) -> List[Tuple]:
        """Get daily income/expense totals for analytics."""
        result = await self.session.execute(
            select(
                func.date(Transaction.transaction_date).label("date"),
                Transaction.type,
                func.sum(Transaction.amount).label("total"),
            )
            .where(
                and_(
                    Transaction.user_id == user_id,
                    Transaction.is_deleted.is_(False),
                    Transaction.transaction_date >= start_date,
                    Transaction.transaction_date <= end_date,
                )
            )
            .group_by(func.date(Transaction.transaction_date), Transaction.type)
            .order_by(func.date(Transaction.transaction_date))
        )
        return result.all()
