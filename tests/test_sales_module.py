"""Comprehensive integration tests for the dedicated 🛒 Sotuvlar (Sales) module."""
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
import pytest
from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.constants import PaymentMethod
from app.database.models import User
from app.services.customer_service import CustomerService
from app.services.finance_service import FinanceService
from app.services.product_service import ProductService
from app.services.sale_service import SaleService


@pytest.mark.asyncio
async def test_single_product_sale_full_payment(session: AsyncSession, test_user: User):
    """Test single-product sale with full cash payment."""
    prod_svc = ProductService(session)
    sale_svc = SaleService(session)
    finance_svc = FinanceService(session)

    # 1. Create product with 20 items in stock
    p = await prod_svc.create_product(
        user_id=test_user.id,
        name="Futbolka",
        cost_price=Decimal("40000"),
        selling_price=Decimal("75000"),
        quantity=Decimal("20"),
        unit="dona",
    )
    await session.flush()

    # 2. Process sale: 3 items @ 75,000 = 225,000 full cash
    res = await sale_svc.process_basket_sale(
        user_id=test_user.id,
        items=[{"product_id": p.id, "quantity": Decimal("3")}],
        customer_id=None,
        paid_amount=Decimal("225000"),
        payment_method=PaymentMethod.CASH,
    )

    # Verify return dict
    assert res["total_amount"] == Decimal("225000")
    assert res["paid_amount"] == Decimal("225000")
    assert res["new_debt"] == Decimal("0")
    assert res["debt"] is None

    # Verify inventory decrease: 20 - 3 = 17
    updated_prod = await prod_svc.product_repo.get_by_id_and_user(p.id, test_user.id)
    assert updated_prod.quantity == Decimal("17")

    # Verify Sale and SaleItem in DB
    sale = await sale_svc.get_sale(res["sale"].id, test_user.id)
    assert sale is not None
    assert sale.total_amount == Decimal("225000")
    assert len(sale.items) == 1
    assert sale.items[0].product_name == "Futbolka"
    assert sale.items[0].quantity == Decimal("3")
    assert sale.items[0].total_price == Decimal("225000")

    # Verify cash balance
    balances = await finance_svc.get_balance_summary(test_user.id)
    assert balances.cash_balance == Decimal("225000")


@pytest.mark.asyncio
async def test_multiple_product_sale_with_partial_payment_and_debt_accumulation(
    session: AsyncSession, test_user: User
):
    """Test multi-item basket sale with customer and debt accumulation:
    Customer initial debt = 50,000
    Product 1: 2 x 100,000 = 200,000
    Product 2: 1 x 300,000 = 300,000
    Total sale = 500,000
    Paid = 350,000
    New debt = 150,000
    Total debt = 200,000
    """
    cust_svc = CustomerService(session)
    prod_svc = ProductService(session)
    sale_svc = SaleService(session)

    # 1. Customer with 50k initial debt
    c = await cust_svc.create_customer(
        user_id=test_user.id,
        name="Rustam Karimov",
        phone="+998901112233",
        telegram_user_id=123456789,
        notifications_enabled=True,
    )
    c.total_purchases = Decimal("50000")
    c.total_paid = Decimal("0")
    c.total_debt = Decimal("50000")
    await session.flush()

    # 2. Create products
    p1 = await prod_svc.create_product(
        user_id=test_user.id,
        name="Koylak",
        cost_price=Decimal("60000"),
        selling_price=Decimal("100000"),
        quantity=Decimal("10"),
    )
    p2 = await prod_svc.create_product(
        user_id=test_user.id,
        name="Kostyum",
        cost_price=Decimal("180000"),
        selling_price=Decimal("300000"),
        quantity=Decimal("5"),
    )
    await session.flush()

    mock_bot = MagicMock(spec=Bot)
    mock_bot.send_message = AsyncMock(return_value=True)

    # 3. Process basket sale
    res = await sale_svc.process_basket_sale(
        user_id=test_user.id,
        items=[
            {"product_id": p1.id, "quantity": Decimal("2")},
            {"product_id": p2.id, "quantity": Decimal("1")},
        ],
        customer_id=c.id,
        paid_amount=Decimal("350000"),
        payment_method=PaymentMethod.CARD,
        description="To'y kiyimlari",
        bot=mock_bot,
        seller_name="OTANIYOZ LUTFIYEV",
    )

    # Assert calculations
    assert res["total_amount"] == Decimal("500000")
    assert res["paid_amount"] == Decimal("350000")
    assert res["new_debt"] == Decimal("150000")
    assert res["old_debt"] == Decimal("50000")
    assert res["total_debt"] == Decimal("200000")
    assert res["notification_sent"] is True

    # Assert stocks deducted: p1 = 10 - 2 = 8, p2 = 5 - 1 = 4
    updated_p1 = await prod_svc.product_repo.get_by_id_and_user(p1.id, test_user.id)
    updated_p2 = await prod_svc.product_repo.get_by_id_and_user(p2.id, test_user.id)
    assert updated_p1.quantity == Decimal("8")
    assert updated_p2.quantity == Decimal("4")

    # Assert customer metrics updated
    updated_cust = await cust_svc.get_customer(c.id, test_user.id)
    assert updated_cust.total_purchases == Decimal("550000")  # 50k + 500k
    assert updated_cust.total_paid == Decimal("350000")
    assert updated_cust.total_debt == Decimal("200000")

    # Assert Sale and 2 items
    sale = await sale_svc.get_sale(res["sale"].id, test_user.id)
    assert sale is not None
    assert len(sale.items) == 2
    assert sale.debt_amount == Decimal("150000")
    assert sale.customer_id == c.id

    # Assert notification was called with exact breakdown
    mock_bot.send_message.assert_called_once()
    call_args = mock_bot.send_message.call_args[1]
    assert call_args["chat_id"] == 123456789
    assert "500 000" in call_args["text"]
    assert "350 000" in call_args["text"]
    assert "150 000" in call_args["text"]
    assert "50 000" in call_args["text"]
    assert "200 000" in call_args["text"]


@pytest.mark.asyncio
async def test_sales_history_and_search(session: AsyncSession, test_user: User):
    """Test retrieving today's sales, paginated history, and search."""
    prod_svc = ProductService(session)
    cust_svc = CustomerService(session)
    sale_svc = SaleService(session)

    c = await cust_svc.create_customer(
        user_id=test_user.id,
        name="Akmal Fayziyev",
    )
    p = await prod_svc.create_product(
        user_id=test_user.id,
        name="Smart Soat",
        cost_price=Decimal("150000"),
        selling_price=Decimal("250000"),
        quantity=Decimal("10"),
    )
    await session.flush()

    # Record 2 sales
    await sale_svc.process_basket_sale(
        user_id=test_user.id,
        items=[{"product_id": p.id, "quantity": Decimal("1")}],
        customer_id=c.id,
        paid_amount=Decimal("250000"),
    )
    await sale_svc.process_basket_sale(
        user_id=test_user.id,
        items=[{"product_id": p.id, "quantity": Decimal("2")}],
        customer_id=None,
        paid_amount=Decimal("500000"),
    )

    # 1. Test today's sales
    today_sales = await sale_svc.get_today_sales(test_user.id)
    assert len(today_sales) == 2

    # 2. Test history
    history = await sale_svc.get_sales_history(test_user.id, limit=10)
    assert len(history) == 2

    # 3. Test search by customer name
    results = await sale_svc.search_sales(test_user.id, "Akmal")
    assert len(results) == 1
    assert results[0].customer.name == "Akmal Fayziyev"

    # 4. Test search by product name
    prod_results = await sale_svc.search_sales(test_user.id, "Smart")
    assert len(prod_results) == 2
