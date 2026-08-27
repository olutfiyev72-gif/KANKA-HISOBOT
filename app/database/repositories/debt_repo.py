"""Debt repository."""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.database.models.debt import Debt, DebtPayment, DebtStatus, DebtType
from app.database.repositories.base_repo import BaseRepository


class DebtRepository(BaseRepository[Debt]):
    """Repository for debt operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(Debt, session)

    async def get_user_debts(
        self,
        user_id: int,
        debt_type: Optional[DebtType] = None,
        status: Optional[DebtStatus] = None,
    ) -> List[Debt]:
        """Get user debts with optional filters."""
        conditions = [
            Debt.user_id == user_id,
            Debt.is_deleted.is_(False),
        ]
        if debt_type:
            conditions.append(Debt.type == debt_type)
        if status:
            conditions.append(Debt.status == status)

        result = await self.session.execute(
            select(Debt)
            .options(joinedload(Debt.payments))
            .where(and_(*conditions))
            .order_by(Debt.created_date.desc())
        )
        return list(result.scalars().unique().all())

    async def get_by_id_and_user(
        self, debt_id: int, user_id: int
    ) -> Optional[Debt]:
        """Get debt by ID with user ownership check."""
        result = await self.session.execute(
            select(Debt)
            .options(joinedload(Debt.payments))
            .where(
                and_(
                    Debt.id == debt_id,
                    Debt.user_id == user_id,
                    Debt.is_deleted.is_(False),
                )
            )
        )
        return result.scalars().unique().one_or_none()

    async def add_payment(
        self,
        debt: Debt,
        amount: Decimal,
        payment_date: datetime,
        description: Optional[str] = None,
    ) -> DebtPayment:
        """Add a payment to a debt."""
        # Validate payment amount
        remaining = debt.amount - debt.paid_amount
        if amount > remaining:
            raise ValueError(
                f"To'lov summasi qoldiqdan ({remaining:,.2f}) ko'p bo'lishi mumkin emas"
            )

        payment = DebtPayment(
            debt_id=debt.id,
            amount=amount,
            payment_date=payment_date,
            description=description,
        )
        self.session.add(payment)

        # Update paid amount
        debt.paid_amount += amount

        # Update status
        if debt.paid_amount >= debt.amount:
            debt.status = DebtStatus.PAID
        else:
            debt.status = DebtStatus.PARTIAL

        await self.session.flush()
        return payment

    async def get_overdue_debts(self, user_id: int) -> List[Debt]:
        """Get overdue debts."""
        now = datetime.now()
        result = await self.session.execute(
            select(Debt).where(
                and_(
                    Debt.user_id == user_id,
                    Debt.is_deleted.is_(False),
                    Debt.status.in_([DebtStatus.ACTIVE, DebtStatus.PARTIAL]),
                    Debt.due_date < now,
                    Debt.due_date.is_not(None),
                )
            ).order_by(Debt.due_date)
        )
        return list(result.scalars().all())

    async def get_summary(self, user_id: int) -> dict:
        """Get debt summary totals."""
        result = await self.session.execute(
            select(
                Debt.type,
                func.sum(Debt.amount).label("total"),
                func.sum(Debt.paid_amount).label("paid"),
                func.count(Debt.id).label("count"),
            )
            .where(
                and_(
                    Debt.user_id == user_id,
                    Debt.is_deleted.is_(False),
                    Debt.status.in_([DebtStatus.ACTIVE, DebtStatus.PARTIAL, DebtStatus.OVERDUE]),
                )
            )
            .group_by(Debt.type)
        )
        rows = result.all()
        summary = {
            "receivable_total": Decimal("0"),
            "receivable_remaining": Decimal("0"),
            "receivable_count": 0,
            "payable_total": Decimal("0"),
            "payable_remaining": Decimal("0"),
            "payable_count": 0,
        }
        for row in rows:
            remaining = (row.total or Decimal("0")) - (row.paid or Decimal("0"))
            if row.type == DebtType.RECEIVABLE:
                summary["receivable_total"] = row.total or Decimal("0")
                summary["receivable_remaining"] = remaining
                summary["receivable_count"] = row.count or 0
            elif row.type == DebtType.PAYABLE:
                summary["payable_total"] = row.total or Decimal("0")
                summary["payable_remaining"] = remaining
                summary["payable_count"] = row.count or 0
        return summary

    async def update_overdue_statuses(self, user_id: int) -> int:
        """Mark overdue debts. Returns count of updated records."""
        now = datetime.now()
        result = await self.session.execute(
            select(Debt).where(
                and_(
                    Debt.user_id == user_id,
                    Debt.is_deleted.is_(False),
                    Debt.status.in_([DebtStatus.ACTIVE, DebtStatus.PARTIAL]),
                    Debt.due_date < now,
                    Debt.due_date.is_not(None),
                )
            )
        )
        debts = result.scalars().all()
        for debt in debts:
            debt.status = DebtStatus.OVERDUE
        await self.session.flush()
        return len(debts)

    async def soft_delete(self, debt_id: int, user_id: int) -> bool:
        """Soft delete a debt."""
        debt = await self.get_by_id_and_user(debt_id, user_id)
        if not debt:
            return False
        debt.is_deleted = True
        await self.session.flush()
        return True
