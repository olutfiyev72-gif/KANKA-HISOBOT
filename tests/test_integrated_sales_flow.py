"""Comprehensive integration tests for the connected Sales Flow:
Customer -> Product -> Inventory -> Cash/Income -> Debt -> Telegram Notification
"""
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


@pytest.mark.asyncio
async def test_integrated_sale_with_customer_and_debt(
    session: AsyncSession, test_user: User
):
    """Test full flow:
    Customer with initial debt = 80,000
    Product with stock = 10, selling_price = 200,000
    Sell quantity = 2 -> Total = 400,000
    Paid = 280,000 -> New debt = 120,000 -> Total customer debt = 200,000
    Inventory stock -> 8
    Cash transaction -> +280,000
    Notification sent -> True
    """
    cust_svc = CustomerService(session)
    prod_svc = ProductService(session)
    finance_svc = FinanceService(session)

    # 1. Create customer with 80k initial debt
    c = await cust_svc.create_customer(
        user_id=test_user.id,
        name="Otaniyoz Lutfiyev",
        phone="+998901234567",
        telegram_user_id=6161501903,
        notifications_enabled=True,
    )
    c.total_purchases = Decimal("80000")
    c.total_paid = Decimal("0")
    c.total_debt = Decimal("80000")
    await session.flush()

    # 2. Create product with 10 units in stock
    p = await prod_svc.create_product(
        user_id=test_user.id,
        name="Kurtka",
        cost_price=Decimal("120000"),
        selling_price=Decimal("200000"),
        quantity=Decimal("10"),
        unit="dona",
    )
    await session.flush()

    mock_bot = MagicMock(spec=Bot)
    mock_bot.send_message = AsyncMock(return_value=True)

    # 3. Execute complete sale
    res = await finance_svc.process_complete_sale(
        user_id=test_user.id,
        product_id=p.id,
        quantity=Decimal("2"),
        customer_id=c.id,
        paid_amount=Decimal("280000"),
        payment_method=PaymentMethod.CASH,
        description="2 ta kurtka sotildi",
        bot=mock_bot,
        seller_name="OTANIYOZ LUTFIYEV",
    )

    # Assert calculations
    assert res["total_amount"] == Decimal("400000")
    assert res["paid_amount"] == Decimal("280000")
    assert res["new_debt"] == Decimal("120000")
    assert res["old_debt"] == Decimal("80000")
    assert res["total_debt"] == Decimal("200000")
    assert res["notification_sent"] is True

    # Assert inventory decreased: 10 - 2 = 8
    updated_prod = await prod_svc.product_repo.get_by_id_and_user(p.id, test_user.id)
    assert updated_prod.quantity == Decimal("8")

    # Assert cash balance has +280,000
    balances = await finance_svc.get_balance_summary(test_user.id)
    assert balances.total_income == Decimal("280000")
    assert balances.total_balance == Decimal("280000")
    assert balances.cash_balance == Decimal("280000")

    # Assert customer metrics
    updated_cust = await cust_svc.get_customer(c.id, test_user.id)
    assert updated_cust.total_purchases == Decimal("480000")
    assert updated_cust.total_paid == Decimal("280000")
    assert updated_cust.total_debt == Decimal("200000")

    # Assert debt record created
    assert res["debt"] is not None
    assert res["debt"].amount == Decimal("120000")
    assert res["debt"].customer_id == c.id

    # Assert notification was called with receipt format
    mock_bot.send_message.assert_called_once()
    call_args = mock_bot.send_message.call_args[1]
    assert call_args["chat_id"] == 6161501903
    assert "400 000" in call_args["text"]
    assert "280 000" in call_args["text"]
    assert "120 000" in call_args["text"]
    assert "80 000" in call_args["text"]
    assert "200 000" in call_args["text"]
    assert "OTANIYOZ LUTFIYEV" in call_args["text"]


@pytest.mark.asyncio
async def test_integrated_sale_anonymous_full_payment(
    session: AsyncSession, test_user: User
):
    """Test selling without a customer with full cash payment."""
    prod_svc = ProductService(session)
    finance_svc = FinanceService(session)

    p = await prod_svc.create_product(
        user_id=test_user.id,
        name="Koylak",
        cost_price=Decimal("50000"),
        selling_price=Decimal("90000"),
        quantity=Decimal("5"),
        unit="dona",
    )
    await session.flush()

    res = await finance_svc.process_complete_sale(
        user_id=test_user.id,
        product_id=p.id,
        quantity=Decimal("3"),
        customer_id=None,
        paid_amount=Decimal("270000"),
        payment_method=PaymentMethod.CARD,
    )

    assert res["total_amount"] == Decimal("270000")
    assert res["paid_amount"] == Decimal("270000")
    assert res["new_debt"] == Decimal("0")
    assert res["customer"] is None
    assert res["debt"] is None
    assert res["notification_sent"] is False

    # Check inventory stock: 5 - 3 = 2
    updated_prod = await prod_svc.product_repo.get_by_id_and_user(p.id, test_user.id)
    assert updated_prod.quantity == Decimal("2")

    # Check card balance: 270,000
    balances = await finance_svc.get_balance_summary(test_user.id)
    assert balances.card_balance == Decimal("270000")


@pytest.mark.asyncio
async def test_oversell_and_validation_errors(
    session: AsyncSession, test_user: User
):
    """Test that overselling is prevented and raises ValueError without modifying stock."""
    prod_svc = ProductService(session)
    finance_svc = FinanceService(session)

    p = await prod_svc.create_product(
        user_id=test_user.id,
        name="Poyabzal",
        cost_price=Decimal("100000"),
        selling_price=Decimal("180000"),
        quantity=Decimal("2"),
        unit="juft",
    )
    await session.flush()

    # Attempt to sell 5 units when only 2 exist
    with pytest.raises(ValueError, match="yetarli mahsulot yo'q"):
        await finance_svc.process_complete_sale(
            user_id=test_user.id,
            product_id=p.id,
            quantity=Decimal("5"),
            paid_amount=Decimal("900000"),
        )

    # Verify product stock unchanged
    updated_prod = await prod_svc.product_repo.get_by_id_and_user(p.id, test_user.id)
    assert updated_prod.quantity == Decimal("2")

    # Attempt to sell with debt without selecting customer
    with pytest.raises(ValueError, match="mijoz tanlanishi shart"):
        await finance_svc.process_complete_sale(
            user_id=test_user.id,
            product_id=p.id,
            quantity=Decimal("1"),
            customer_id=None,
            paid_amount=Decimal("100000"),  # total is 180k, so 80k debt without customer
        )


@pytest.mark.asyncio
async def test_debt_repayment_after_integrated_sale(
    session: AsyncSession, test_user: User
):
    """Test debt repayment after an integrated sale."""
    cust_svc = CustomerService(session)
    prod_svc = ProductService(session)
    finance_svc = FinanceService(session)

    c = await cust_svc.create_customer(
        user_id=test_user.id,
        name="Javohir",
        telegram_user_id=777888999,
        notifications_enabled=True,
    )
    p = await prod_svc.create_product(
        user_id=test_user.id,
        name="Telefon g'ilofi",
        cost_price=Decimal("20000"),
        selling_price=Decimal("50000"),
        quantity=Decimal("10"),
    )
    await session.flush()

    mock_bot = MagicMock(spec=Bot)
    mock_bot.send_message = AsyncMock(return_value=True)

    # 1. Sale: 1 item @ 50,000, 20,000 paid -> 30,000 debt
    await finance_svc.process_complete_sale(
        user_id=test_user.id,
        product_id=p.id,
        quantity=Decimal("1"),
        customer_id=c.id,
        paid_amount=Decimal("20000"),
        bot=mock_bot,
    )

    # Customer debt = 30,000
    updated_cust = await cust_svc.get_customer(c.id, test_user.id)
    assert updated_cust.total_debt == Decimal("30000")

    # 2. Customer repays 30,000 in full
    repay_res = await cust_svc.record_customer_debt_payment(
        user_id=test_user.id,
        customer_id=c.id,
        payment_amount=Decimal("30000"),
        payment_method=PaymentMethod.CASH,
        bot=mock_bot,
        seller_name="OTANIYOZ LUTFIYEV",
    )

    assert repay_res["old_debt"] == Decimal("30000")
    assert repay_res["remaining_debt"] == Decimal("0")
    assert repay_res["notification_sent"] is True

    # Customer debt is now 0
    final_cust = await cust_svc.get_customer(c.id, test_user.id)
    assert final_cust.total_debt == Decimal("0")
    assert final_cust.total_paid == Decimal("50000")  # 20k initial + 30k repayment
