"""Finance & Accounting domain service."""
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.constants import (
    DebtStatus,
    DebtType,
    InventoryAction,
    PaymentMethod,
    TransactionType,
)
from app.database.models.inventory import InventoryTransactionType
from app.database.models.transaction import Transaction
from app.database.repositories.category_repo import CategoryRepository
from app.database.repositories.customer_repo import CustomerRepository
from app.database.repositories.debt_repo import DebtRepository
from app.database.repositories.inventory_repo import InventoryRepository
from app.database.repositories.product_repo import ProductRepository
from app.database.repositories.transaction_repo import TransactionRepository
from app.schemas.transaction import BalanceSummary
from app.services.base import BaseService
from app.services.notification_service import NotificationService


class FinanceService(BaseService):
    """Business service orchestrating financial and integrated sales operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(session)
        self.tx_repo = TransactionRepository(session)
        self.cat_repo = CategoryRepository(session)
        self.product_repo = ProductRepository(session)
        self.inventory_repo = InventoryRepository(session)
        self.customer_repo = CustomerRepository(session)
        self.debt_repo = DebtRepository(session)

    async def record_income(
        self,
        user_id: int,
        amount: Decimal,
        category_id: Optional[int] = None,
        payment_method: PaymentMethod = PaymentMethod.CASH,
        description: Optional[str] = None,
        product_id: Optional[int] = None,
        quantity: Optional[Decimal] = None,
        transaction_date: Optional[datetime] = None,
    ) -> Transaction:
        """Record an income transaction with Decimal precision."""
        if amount <= Decimal("0"):
            raise ValueError("Daromad summasi noldan katta bo'lishi kerak")

        date = transaction_date or datetime.now()
        return await self.tx_repo.create_transaction(
            user_id=user_id,
            type=TransactionType.INCOME,
            amount=amount,
            category_id=category_id,
            payment_method=payment_method,
            description=description,
            product_id=product_id,
            product_quantity=quantity,
            transaction_date=date,
        )

    async def record_expense(
        self,
        user_id: int,
        amount: Decimal,
        category_id: Optional[int] = None,
        payment_method: PaymentMethod = PaymentMethod.CASH,
        description: Optional[str] = None,
        transaction_date: Optional[datetime] = None,
    ) -> Transaction:
        """Record an expense transaction with Decimal precision."""
        if amount <= Decimal("0"):
            raise ValueError("Xarajat summasi noldan katta bo'lishi kerak")

        date = transaction_date or datetime.now()
        return await self.tx_repo.create_transaction(
            user_id=user_id,
            type=TransactionType.EXPENSE,
            amount=amount,
            category_id=category_id,
            payment_method=payment_method,
            description=description,
            transaction_date=date,
        )

    async def process_complete_sale(
        self,
        user_id: int,
        product_id: int,
        quantity: Decimal,
        customer_id: Optional[int] = None,
        paid_amount: Optional[Decimal] = None,
        payment_method: PaymentMethod = PaymentMethod.CASH,
        description: Optional[str] = None,
        bot: Optional[Bot] = None,
        seller_name: str = "Do'kon",
    ) -> Dict[str, Any]:
        """Execute complete unified sale flow:
        - Validate product & quantity
        - Deduct inventory
        - Record income transaction for cash flow
        - Accumulate customer debt if unpaid amount exists
        - Atomic DB operations
        - Send Telegram receipt/debt notification
        """
        if quantity <= Decimal("0"):
            raise ValueError("Mahsulot miqdori noldan katta bo'lishi kerak")

        # 1. Fetch & validate product
        product = await self.product_repo.get_by_id_and_user(product_id, user_id)
        if not product:
            raise ValueError("Mahsulot topilmadi")

        if quantity > product.quantity:
            raise ValueError(
                f"Omborda yetarli mahsulot yo'q. Mavjud: {product.quantity} {product.unit}"
            )

        # 2. Financial calculations
        total_amount = quantity * product.selling_price
        paid = paid_amount if paid_amount is not None else total_amount

        if paid < Decimal("0"):
            raise ValueError("To'langan summa manfiy bo'lishi mumkin emas")
        if paid > total_amount:
            raise ValueError("To'langan summa umumiy summadan ko'p bo'lishi mumkin emas")

        new_debt = total_amount - paid
        if new_debt > Decimal("0") and not customer_id:
            raise ValueError("Qarzga sotish uchun mijoz tanlanishi shart")

        # 3. Customer debt calculation & balance update
        customer = None
        old_debt = Decimal("0.00")
        total_debt = Decimal("0.00")

        if customer_id:
            customer = await self.customer_repo.get_by_id_and_user(customer_id, user_id)
            if not customer:
                raise ValueError("Mijoz topilmadi")
            old_debt = customer.total_debt
            total_debt = old_debt + new_debt

            await self.customer_repo.update_balances(
                customer=customer,
                purchase_amount=total_amount,
                paid_amount=paid,
                new_debt=new_debt,
            )

        # 4. Inventory deduction
        await self.product_repo.update_quantity(product, -quantity)

        # 5. Record Financial Income Transaction for paid amount
        tx = None
        now = datetime.now()
        if paid > Decimal("0"):
            desc = description or f"{product.name} sotuvi ({quantity} {product.unit})"
            tx = await self.tx_repo.create_transaction(
                user_id=user_id,
                type=TransactionType.INCOME,
                amount=paid,
                payment_method=payment_method,
                description=desc,
                product_id=product.id,
                product_quantity=quantity,
                transaction_date=now,
            )
            if customer_id:
                tx.customer_id = customer_id
            await self.session.flush()

        # 6. Record Inventory Transaction (Movement Log)
        await self.inventory_repo.add_inventory_transaction(
            product_id=product.id,
            user_id=user_id,
            type=InventoryTransactionType.SALE,
            quantity=quantity,
            price=product.selling_price,
            transaction_id=tx.id if tx else None,
            description=f"{product.name} sotuvi ({quantity} {product.unit})",
        )

        # 7. Record Debt if there is an unpaid amount
        debt = None
        if new_debt > Decimal("0") and customer:
            debt_desc = (
                f"{product.name} ({quantity} {product.unit}) | Jami: {total_amount:,.0f} | To'landi: {paid:,.0f}"
            )
            debt = await self.debt_repo.create(
                user_id=user_id,
                contact_name=customer.name,
                contact_phone=customer.phone,
                amount=new_debt,
                paid_amount=Decimal("0.00"),
                type=DebtType.RECEIVABLE,
                status=DebtStatus.ACTIVE,
                created_date=now,
                description=debt_desc,
            )
            debt.customer_id = customer.id
            await self.session.flush()

        # 8. Dispatch Telegram notification if debt exists and customer opted in
        notification_sent = False
        if customer and new_debt > Decimal("0") and customer.telegram_user_id and customer.notifications_enabled:
            notification_sent = await NotificationService.send_sale_debt_notification(
                bot=bot,
                customer=customer,
                purchase_amount=total_amount,
                paid_amount=paid,
                new_debt=new_debt,
                old_debt=old_debt,
                total_debt=total_debt,
                seller_name=seller_name,
            )

        return {
            "product": product,
            "quantity": quantity,
            "total_amount": total_amount,
            "paid_amount": paid,
            "new_debt": new_debt,
            "old_debt": old_debt,
            "total_debt": total_debt,
            "customer": customer,
            "transaction": tx,
            "debt": debt,
            "notification_sent": notification_sent,
        }

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
        if amount is not None and amount <= Decimal("0"):
            raise ValueError("Summa noldan katta bo'lishi kerak")

        return await self.tx_repo.update_transaction(
            transaction_id=transaction_id,
            user_id=user_id,
            amount=amount,
            category_id=category_id,
            payment_method=payment_method,
            description=description,
            transaction_date=transaction_date,
        )

    async def delete_transaction(self, transaction_id: int, user_id: int) -> bool:
        """Soft delete a transaction."""
        return await self.tx_repo.soft_delete(transaction_id, user_id)

    async def get_transaction(self, transaction_id: int, user_id: int) -> Optional[Transaction]:
        """Get transaction details."""
        return await self.tx_repo.get_user_transaction(transaction_id, user_id)

    async def get_recent_transactions(
        self, user_id: int, limit: int = 10, offset: int = 0
    ) -> List[Transaction]:
        """Get list of recent transactions."""
        return await self.tx_repo.get_user_transactions(
            user_id=user_id, limit=limit, offset=offset
        )

    async def get_balance_summary(self, user_id: int) -> BalanceSummary:
        """Compute cash balance summary across all payment channels."""
        raw = await self.tx_repo.get_cash_summary(user_id)
        return BalanceSummary(
            total_balance=raw["balance"],
            total_income=raw["total_income"],
            total_expense=raw["total_expense"],
            cash_balance=raw.get("cash", Decimal("0")),
            card_balance=raw.get("card", Decimal("0")),
            bank_balance=raw.get("bank", Decimal("0")),
            other_balance=raw.get("other", Decimal("0")),
        )
