"""Debt and Receivables/Payables domain service."""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.constants import DebtStatus, DebtType
from app.database.models.debt import Debt, DebtPayment
from app.database.repositories.debt_repo import DebtRepository
from app.schemas.debt import DebtSummary
from app.services.base import BaseService


class DebtService(BaseService):
    """Business service orchestrating debt management."""

    def __init__(self, session: AsyncSession):
        super().__init__(session)
        self.debt_repo = DebtRepository(session)

    async def create_debt(
        self,
        user_id: int,
        contact_name: str,
        amount: Decimal,
        debt_type: DebtType,
        contact_phone: Optional[str] = None,
        due_date: Optional[datetime] = None,
        created_date: Optional[datetime] = None,
        description: Optional[str] = None,
    ) -> Debt:
        """Register a new debt (receivable or payable)."""
        if amount <= Decimal("0"):
            raise ValueError("Qarz summasi noldan katta bo'lishi kerak")

        return await self.debt_repo.create(
            user_id=user_id,
            contact_name=contact_name,
            contact_phone=contact_phone,
            amount=amount,
            paid_amount=Decimal("0"),
            type=debt_type,
            status=DebtStatus.ACTIVE,
            due_date=due_date,
            created_date=created_date or datetime.now(),
            description=description,
        )

    async def record_payment(
        self,
        debt_id: int,
        user_id: int,
        amount: Decimal,
        payment_date: Optional[datetime] = None,
        description: Optional[str] = None,
    ) -> DebtPayment:
        """Record a partial or full repayment for a debt."""
        debt = await self.debt_repo.get_by_id_and_user(debt_id, user_id)
        if not debt:
            raise ValueError("Qarz topilmadi")

        date = payment_date or datetime.now()
        return await self.debt_repo.add_payment(
            debt=debt,
            amount=amount,
            payment_date=date,
            description=description,
        )

    async def get_summary(self, user_id: int) -> DebtSummary:
        """Get summary metrics for debts."""
        raw = await self.debt_repo.get_summary(user_id)
        return DebtSummary(**raw)
