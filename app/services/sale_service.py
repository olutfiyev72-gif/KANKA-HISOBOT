"""Sale domain service orchestrating basket multi-item sales, inventory, finance, debts, and notifications."""
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
from app.database.models.sale import Sale
from app.database.repositories.customer_repo import CustomerRepository
from app.database.repositories.debt_repo import DebtRepository
from app.database.repositories.inventory_repo import InventoryRepository
from app.database.repositories.product_repo import ProductRepository
from app.database.repositories.sale_repo import SaleRepository
from app.database.repositories.transaction_repo import TransactionRepository
from app.schemas.sale import SaleSummary
from app.services.base import BaseService
from app.services.notification_service import NotificationService


class SaleService(BaseService):
    """Domain service for multi-product sales, CRM integration, and accounting."""

    def __init__(self, session: AsyncSession):
        super().__init__(session)
        self.sale_repo = SaleRepository(session)
        self.product_repo = ProductRepository(session)
        self.inventory_repo = InventoryRepository(session)
        self.customer_repo = CustomerRepository(session)
        self.tx_repo = TransactionRepository(session)
        self.debt_repo = DebtRepository(session)

    async def process_basket_sale(
        self,
        user_id: int,
        items: List[Dict[str, Any]],
        customer_id: Optional[int] = None,
        paid_amount: Optional[Decimal] = None,
        payment_method: PaymentMethod = PaymentMethod.CASH,
        description: Optional[str] = None,
        bot: Optional[Bot] = None,
        seller_name: str = "Do'kon",
    ) -> Dict[str, Any]:
        """Atomically execute a complete multi-item sale order."""
        if not items:
            raise ValueError("Savat bo'sh. Kamida 1 ta mahsulot bo'lishi kerak")

        # 1. Validate all products and stock availability
        prepared_items = []
        total_amount = Decimal("0.00")

        for item in items:
            p_id = item["product_id"]
            qty = Decimal(str(item["quantity"]))
            if qty <= Decimal("0"):
                raise ValueError("Mahsulot miqdori noldan katta bo'lishi kerak")

            product = await self.product_repo.get_by_id_and_user(p_id, user_id)
            if not product:
                raise ValueError(f"Mahsulot (ID: {p_id}) topilmadi")

            if qty > product.quantity:
                raise ValueError(
                    f"'{product.name}' omborda yetarli emas. Mavjud: {product.quantity} {product.unit}"
                )

            unit_price = Decimal(str(item.get("unit_price") or product.selling_price))
            line_total = qty * unit_price
            total_amount += line_total

            prepared_items.append(
                {
                    "product": product,
                    "product_id": product.id,
                    "product_name": product.name,
                    "unit": product.unit,
                    "quantity": qty,
                    "unit_price": unit_price,
                    "total_price": line_total,
                    "cost_price": product.cost_price,
                }
            )

        # 2. Payment and Debt calculation
        paid = Decimal(str(paid_amount)) if paid_amount is not None else total_amount
        if paid < Decimal("0"):
            raise ValueError("To'langan summa manfiy bo'lishi mumkin emas")
        if paid > total_amount:
            raise ValueError("To'langan summa jami summadan ko'p bo'lishi mumkin emas")

        new_debt = total_amount - paid
        if new_debt > Decimal("0") and not customer_id:
            raise ValueError("Qarzga sotish uchun mijoz tanlanishi shart")

        # 3. Customer debt calculation & updates
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

        # 4. Inventory deduction for each product
        now = datetime.now()
        for p_data in prepared_items:
            prod = p_data["product"]
            qty = p_data["quantity"]
            await self.product_repo.update_quantity(prod, -qty)

        # 5. Create Sale and SaleItem records
        sale = await self.sale_repo.create_sale(
            user_id=user_id,
            customer_id=customer_id,
            total_amount=total_amount,
            paid_amount=paid,
            debt_amount=new_debt,
            payment_method=payment_method,
            description=description,
            sale_date=now,
            items_data=prepared_items,
        )

        # 6. Record financial income transaction for cash flow in Kassa
        tx = None
        if paid > Decimal("0"):
            items_summary = ", ".join(
                [f"{it['product_name']} ({it['quantity']} {it['unit']})" for it in prepared_items[:3]]
            )
            if len(prepared_items) > 3:
                items_summary += f" + yana {len(prepared_items) - 3} ta"

            tx_desc = description or f"Sotuv #{sale.id}: {items_summary}"
            tx = await self.tx_repo.create_transaction(
                user_id=user_id,
                type=TransactionType.INCOME,
                amount=paid,
                payment_method=payment_method,
                description=tx_desc,
                transaction_date=now,
            )
            if customer_id:
                tx.customer_id = customer_id
            await self.session.flush()

        # 7. Record inventory movement transactions for each item
        for p_data in prepared_items:
            await self.inventory_repo.add_inventory_transaction(
                product_id=p_data["product_id"],
                user_id=user_id,
                type=InventoryTransactionType.SALE,
                quantity=p_data["quantity"],
                price=p_data["unit_price"],
                transaction_id=tx.id if tx else None,
                description=f"Sotuv #{sale.id}",
            )

        # 8. Record Debt if unpaid amount exists
        debt = None
        if new_debt > Decimal("0") and customer:
            debt_desc = f"Sotuv #{sale.id} | Jami: {total_amount:,.0f} | To'landi: {paid:,.0f}"
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

        # 9. Explicit atomic commit before sending notification
        await self.session.commit()

        # 10. Post-commit Telegram notification (only after successful DB commit)
        notification_sent = False
        if customer and (new_debt > Decimal("0") or total_debt > Decimal("0")) and customer.telegram_user_id and customer.notifications_enabled:
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
            "sale": sale,
            "items": prepared_items,
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

    async def get_sale(self, sale_id: int, user_id: int) -> Optional[Sale]:
        """Fetch sale with lines."""
        return await self.sale_repo.get_by_id_and_user(sale_id, user_id)

    async def get_today_sales(self, user_id: int) -> List[Sale]:
        """Fetch today's sales."""
        return await self.sale_repo.get_today_sales(user_id)

    async def get_sales_history(
        self,
        user_id: int,
        limit: int = 20,
        offset: int = 0,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> List[Sale]:
        """Fetch historical sales with pagination."""
        return await self.sale_repo.get_user_sales(
            user_id=user_id,
            limit=limit,
            offset=offset,
            date_from=date_from,
            date_to=date_to,
        )

    async def search_sales(
        self, user_id: int, query: str, limit: int = 20
    ) -> List[Sale]:
        """Search sales orders."""
        return await self.sale_repo.search_sales(user_id, query, limit=limit)

    async def get_sales_summary(
        self,
        user_id: int,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> SaleSummary:
        """Get aggregate metrics."""
        raw = await self.sale_repo.get_summary(user_id, date_from, date_to)
        return SaleSummary(**raw)
