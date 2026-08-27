"""Customer / CRM domain service."""
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from aiogram import Bot
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.constants import DebtStatus, DebtType, PaymentMethod, TransactionType
from app.database.models.customer import Customer
from app.database.models.debt import Debt
from app.database.models.transaction import Transaction
from app.database.repositories.customer_repo import CustomerRepository
from app.database.repositories.debt_repo import DebtRepository
from app.database.repositories.transaction_repo import TransactionRepository
from app.schemas.customer import CustomerSummary
from app.services.base import BaseService
from app.services.notification_service import NotificationService


class CustomerService(BaseService):
    """Business service orchestrating Customer CRM, sales, and debt operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(session)
        self.customer_repo = CustomerRepository(session)
        self.tx_repo = TransactionRepository(session)
        self.debt_repo = DebtRepository(session)

    async def create_customer(
        self,
        user_id: int,
        name: str,
        phone: Optional[str] = None,
        telegram_username: Optional[str] = None,
        telegram_user_id: Optional[int] = None,
        notifications_enabled: bool = True,
    ) -> Customer:
        """Create a new CRM customer."""
        if not name or not name.strip():
            raise ValueError("Mijoz ismi kiritilishi shart")

        return await self.customer_repo.create_customer(
            user_id=user_id,
            name=name,
            phone=phone,
            telegram_username=telegram_username,
            telegram_user_id=telegram_user_id,
            notifications_enabled=notifications_enabled,
        )

    async def get_customer(
        self, customer_id: int, user_id: int
    ) -> Optional[Customer]:
        """Fetch customer with ownership verification."""
        return await self.customer_repo.get_by_id_and_user(customer_id, user_id)

    async def search_customers(
        self, user_id: int, query: str, limit: int = 20
    ) -> List[Customer]:
        """Search customers by name, phone or username."""
        return await self.customer_repo.search_customers(user_id, query, limit=limit)

    async def get_user_customers(
        self,
        user_id: int,
        active_only: bool = True,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Customer]:
        """Get paginated customer list."""
        return await self.customer_repo.get_user_customers(
            user_id=user_id, active_only=active_only, limit=limit, offset=offset
        )

    async def update_customer(
        self,
        customer_id: int,
        user_id: int,
        name: Optional[str] = None,
        phone: Optional[str] = None,
        telegram_username: Optional[str] = None,
        telegram_user_id: Optional[int] = None,
        notifications_enabled: Optional[bool] = None,
        is_active: Optional[bool] = None,
    ) -> Optional[Customer]:
        """Update customer profile information."""
        customer = await self.customer_repo.get_by_id_and_user(customer_id, user_id)
        if not customer:
            return None

        if name is not None:
            customer.name = name.strip()
        if phone is not None:
            customer.phone = phone.strip() if phone else None
        if telegram_username is not None:
            customer.telegram_username = (
                telegram_username.strip().lstrip("@") if telegram_username else None
            )
        if telegram_user_id is not None:
            customer.telegram_user_id = telegram_user_id
        if notifications_enabled is not None:
            customer.notifications_enabled = notifications_enabled
        if is_active is not None:
            customer.is_active = is_active

        await self.session.flush()
        return customer

    async def toggle_notifications(
        self, customer_id: int, user_id: int
    ) -> Optional[Customer]:
        """Toggle customer notification preference."""
        customer = await self.customer_repo.get_by_id_and_user(customer_id, user_id)
        if not customer:
            return None
        customer.notifications_enabled = not customer.notifications_enabled
        await self.session.flush()
        return customer

    async def toggle_active(
        self, customer_id: int, user_id: int
    ) -> Optional[Customer]:
        """Activate/deactivate customer."""
        customer = await self.customer_repo.get_by_id_and_user(customer_id, user_id)
        if not customer:
            return None
        customer.is_active = not customer.is_active
        await self.session.flush()
        return customer

    async def record_customer_sale(
        self,
        user_id: int,
        customer_id: int,
        total_amount: Decimal,
        paid_amount: Decimal,
        payment_method: PaymentMethod = PaymentMethod.CASH,
        description: Optional[str] = None,
        bot: Optional[Bot] = None,
        seller_name: str = "Do'kon",
    ) -> Dict[str, Any]:
        """Record customer purchase, handle partial payment debt accumulation, and notify customer."""
        if total_amount <= Decimal("0"):
            raise ValueError("Xarid summasi noldan katta bo'lishi kerak")
        if paid_amount < Decimal("0"):
            raise ValueError("To'langan summa manfiy bo'lishi mumkin emas")
        if paid_amount > total_amount:
            raise ValueError("To'langan summa umumiy xariddan ko'p bo'lishi mumkin emas")

        customer = await self.customer_repo.get_by_id_and_user(customer_id, user_id)
        if not customer:
            raise ValueError("Mijoz topilmadi")

        old_debt = customer.total_debt
        new_debt = total_amount - paid_amount
        total_debt = old_debt + new_debt

        # 1. Update customer financial metrics
        await self.customer_repo.update_balances(
            customer=customer,
            purchase_amount=total_amount,
            paid_amount=paid_amount,
            new_debt=new_debt,
        )

        # 2. Record income transaction for cash flow if paid_amount > 0
        tx = None
        if paid_amount > Decimal("0"):
            tx_desc = description or f"Mijoz ({customer.name}) xaridi"
            tx = await self.tx_repo.create_transaction(
                user_id=user_id,
                type=TransactionType.INCOME,
                amount=paid_amount,
                payment_method=payment_method,
                description=tx_desc,
                transaction_date=datetime.now(),
            )
            tx.customer_id = customer.id
            await self.session.flush()

        # 3. If there is unpaid balance, record a receivable debt
        debt = None
        if new_debt > Decimal("0"):
            debt_desc = (
                f"Xarid: {total_amount:,.0f} so'm | To'landi: {paid_amount:,.0f} so'm | {description or ''}"
            ).strip(" | ")
            debt = await self.debt_repo.create(
                user_id=user_id,
                contact_name=customer.name,
                contact_phone=customer.phone,
                amount=new_debt,
                paid_amount=Decimal("0.00"),
                type=DebtType.RECEIVABLE,
                status=DebtStatus.ACTIVE,
                created_date=datetime.now(),
                description=debt_desc,
            )
            debt.customer_id = customer.id
            await self.session.flush()

        # 4. Dispatch Telegram notification if debt exists
        notification_sent = False
        if new_debt > Decimal("0") and customer.telegram_user_id and customer.notifications_enabled:
            notification_sent = await NotificationService.send_sale_debt_notification(
                bot=bot,
                customer=customer,
                purchase_amount=total_amount,
                paid_amount=paid_amount,
                new_debt=new_debt,
                old_debt=old_debt,
                total_debt=total_debt,
                seller_name=seller_name,
            )

        return {
            "customer": customer,
            "transaction": tx,
            "debt": debt,
            "old_debt": old_debt,
            "new_debt": new_debt,
            "total_debt": total_debt,
            "notification_sent": notification_sent,
        }

    async def record_customer_debt_payment(
        self,
        user_id: int,
        customer_id: int,
        payment_amount: Decimal,
        payment_method: PaymentMethod = PaymentMethod.CASH,
        description: Optional[str] = None,
        bot: Optional[Bot] = None,
        seller_name: str = "Do'kon",
    ) -> Dict[str, Any]:
        """Record repayment of customer debt, update kassa balance, and notify customer."""
        if payment_amount <= Decimal("0"):
            raise ValueError("To'lov summasi noldan katta bo'lishi kerak")

        customer = await self.customer_repo.get_by_id_and_user(customer_id, user_id)
        if not customer:
            raise ValueError("Mijoz topilmadi")

        old_debt = customer.total_debt
        remaining_debt = max(Decimal("0.00"), old_debt - payment_amount)

        # 1. Update customer debt and paid totals
        await self.customer_repo.record_debt_payment(
            customer=customer, payment_amount=payment_amount
        )

        # 2. Record Income transaction for cash flow in Kassa
        tx = await self.tx_repo.create_transaction(
            user_id=user_id,
            type=TransactionType.INCOME,
            amount=payment_amount,
            payment_method=payment_method,
            description=f"Mijoz ({customer.name}) qarz to'lovi: {description or ''}".strip(),
            transaction_date=datetime.now(),
        )
        tx.customer_id = customer.id
        await self.session.flush()

        # 3. Also apply payment to open customer debts in debt repository
        remaining_to_apply = payment_amount
        result = await self.session.execute(
            select(Debt)
            .where(
                and_(
                    Debt.user_id == user_id,
                    Debt.customer_id == customer_id,
                    Debt.type == DebtType.RECEIVABLE,
                    Debt.is_deleted.is_(False),
                    Debt.status.in_([DebtStatus.ACTIVE, DebtStatus.PARTIAL, DebtStatus.OVERDUE]),
                )
            )
            .order_by(Debt.created_date.asc())
        )
        debts = list(result.scalars().all())
        for d in debts:
            if remaining_to_apply <= Decimal("0"):
                break
            debt_rem = d.remaining_amount
            apply_amount = min(debt_rem, remaining_to_apply)
            if apply_amount > Decimal("0"):
                await self.debt_repo.add_payment(
                    debt=d,
                    amount=apply_amount,
                    payment_date=datetime.now(),
                    description=description or "Mijoz to'lovi",
                )
                remaining_to_apply -= apply_amount

        # 4. Dispatch Telegram notification
        notification_sent = False
        if customer.telegram_user_id and customer.notifications_enabled:
            notification_sent = await NotificationService.send_debt_payment_notification(
                bot=bot,
                customer=customer,
                paid_amount=payment_amount,
                old_debt=old_debt,
                remaining_debt=remaining_debt,
                seller_name=seller_name,
            )

        return {
            "customer": customer,
            "transaction": tx,
            "old_debt": old_debt,
            "paid_amount": payment_amount,
            "remaining_debt": remaining_debt,
            "notification_sent": notification_sent,
        }

    async def get_customer_history(
        self, customer_id: int, user_id: int
    ) -> Dict[str, Any]:
        """Fetch transactions and debts associated with a customer."""
        customer = await self.customer_repo.get_by_id_and_user(customer_id, user_id)
        if not customer:
            raise ValueError("Mijoz topilmadi")

        tx_result = await self.session.execute(
            select(Transaction)
            .where(
                and_(
                    Transaction.user_id == user_id,
                    Transaction.customer_id == customer_id,
                    Transaction.is_deleted.is_(False),
                )
            )
            .order_by(Transaction.transaction_date.desc())
            .limit(20)
        )
        transactions = list(tx_result.scalars().all())

        debt_result = await self.session.execute(
            select(Debt)
            .where(
                and_(
                    Debt.user_id == user_id,
                    Debt.customer_id == customer_id,
                    Debt.is_deleted.is_(False),
                )
            )
            .order_by(Debt.created_date.desc())
            .limit(20)
        )
        debts = list(debt_result.scalars().all())

        return {
            "customer": customer,
            "transactions": transactions,
            "debts": debts,
        }

    async def get_crm_summary(self, user_id: int) -> CustomerSummary:
        """Get aggregate CRM summary stats."""
        raw = await self.customer_repo.get_summary(user_id)
        return CustomerSummary(**raw)
