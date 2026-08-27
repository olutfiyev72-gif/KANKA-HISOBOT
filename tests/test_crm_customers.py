"""Comprehensive test suite for Customer CRM module, sales-debt integration, and notifications."""
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
import pytest
from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.constants import PaymentMethod
from app.database.models import User
from app.services.customer_service import CustomerService
from app.services.notification_service import NotificationService


@pytest.mark.asyncio
async def test_customer_crud_and_search(session: AsyncSession, test_user: User):
    """Test customer creation, updating, search, and user isolation."""
    cust_svc = CustomerService(session)

    # 1. Create customer
    c1 = await cust_svc.create_customer(
        user_id=test_user.id,
        name="Otaniyoz Lutfiyev",
        phone="+998901234567",
        telegram_username="otaniyoz",
        telegram_user_id=123456789,
        notifications_enabled=True,
    )
    assert c1.id is not None
    assert c1.name == "Otaniyoz Lutfiyev"
    assert c1.total_debt == Decimal("0.00")

    # 2. Update customer
    updated = await cust_svc.update_customer(
        customer_id=c1.id,
        user_id=test_user.id,
        phone="+998997654321",
    )
    assert updated is not None
    assert updated.phone == "+998997654321"

    # 3. Search customer by name
    results_name = await cust_svc.search_customers(test_user.id, "Otaniyoz")
    assert len(results_name) == 1
    assert results_name[0].id == c1.id

    # 4. Search customer by phone
    results_phone = await cust_svc.search_customers(test_user.id, "7654321")
    assert len(results_phone) == 1

    # 5. User isolation
    other_user = User(
        telegram_id=999999999,
        full_name="Other User",
    )
    session.add(other_user)
    await session.flush()

    other_results = await cust_svc.search_customers(other_user.id, "Otaniyoz")
    assert len(other_results) == 0


@pytest.mark.asyncio
async def test_customer_purchase_with_debt_and_combination(
    session: AsyncSession, test_user: User
):
    """Test the exact scenario from requirements:
    Old debt = 80,000
    New purchase = 400,000
    Paid = 280,000
    New debt = 120,000
    Total debt = 200,000
    """
    cust_svc = CustomerService(session)

    # Create customer with initial debt of 80,000
    c = await cust_svc.create_customer(
        user_id=test_user.id,
        name="Otaniyoz Lutfiyev",
        phone="+998901234567",
        telegram_user_id=987654321,
    )
    c.total_purchases = Decimal("80000")
    c.total_paid = Decimal("0")
    c.total_debt = Decimal("80000")
    await session.flush()

    # Record new purchase: 400,000 with 280,000 paid
    mock_bot = MagicMock(spec=Bot)
    mock_bot.send_message = AsyncMock(return_value=True)

    res = await cust_svc.record_customer_sale(
        user_id=test_user.id,
        customer_id=c.id,
        total_amount=Decimal("400000"),
        paid_amount=Decimal("280000"),
        payment_method=PaymentMethod.CASH,
        description="Kiyim xaridi",
        bot=mock_bot,
        seller_name="OTANIYOZ LUTFIYEV",
    )

    assert res["old_debt"] == Decimal("80000")
    assert res["new_debt"] == Decimal("120000")
    assert res["total_debt"] == Decimal("200000")
    assert res["notification_sent"] is True

    # Verify updated customer entity
    updated_cust = await cust_svc.get_customer(c.id, test_user.id)
    assert updated_cust.total_purchases == Decimal("480000")  # 80k old + 400k new
    assert updated_cust.total_paid == Decimal("280000")
    assert updated_cust.total_debt == Decimal("200000")

    # Verify transaction created for paid amount (280,000)
    assert res["transaction"] is not None
    assert res["transaction"].amount == Decimal("280000")
    assert res["transaction"].customer_id == c.id

    # Verify debt created for new debt amount (120,000)
    assert res["debt"] is not None
    assert res["debt"].amount == Decimal("120000")
    assert res["debt"].customer_id == c.id


@pytest.mark.asyncio
async def test_customer_debt_payment_and_remaining(
    session: AsyncSession, test_user: User
):
    """Test debt repayment and correct remaining debt calculation."""
    cust_svc = CustomerService(session)

    # Customer with 200,000 total debt
    c = await cust_svc.create_customer(
        user_id=test_user.id,
        name="Sherzod Aliyev",
        telegram_user_id=555444333,
    )
    c.total_purchases = Decimal("500000")
    c.total_paid = Decimal("300000")
    c.total_debt = Decimal("200000")
    await session.flush()

    mock_bot = MagicMock(spec=Bot)
    mock_bot.send_message = AsyncMock(return_value=True)

    # Pay 50,000
    res = await cust_svc.record_customer_debt_payment(
        user_id=test_user.id,
        customer_id=c.id,
        payment_amount=Decimal("50000"),
        payment_method=PaymentMethod.CARD,
        description="Karta orqali qarz to'lovi",
        bot=mock_bot,
        seller_name="BIZNES BOT",
    )

    assert res["old_debt"] == Decimal("200000")
    assert res["paid_amount"] == Decimal("50000")
    assert res["remaining_debt"] == Decimal("150000")
    assert res["notification_sent"] is True

    # Verify updated customer entity
    updated_cust = await cust_svc.get_customer(c.id, test_user.id)
    assert updated_cust.total_paid == Decimal("350000")  # 300k + 50k
    assert updated_cust.total_debt == Decimal("150000")

    # Verify kassa income transaction created for 50,000
    assert res["transaction"] is not None
    assert res["transaction"].amount == Decimal("50000")
    assert res["transaction"].customer_id == c.id


@pytest.mark.asyncio
async def test_notification_conditions(session: AsyncSession, test_user: User):
    """Test that notifications are only dispatched when conditions are met."""
    cust_svc = CustomerService(session)
    mock_bot = MagicMock(spec=Bot)
    mock_bot.send_message = AsyncMock(return_value=True)

    # 1. Customer with notifications disabled
    c_disabled = await cust_svc.create_customer(
        user_id=test_user.id,
        name="No Notif User",
        telegram_user_id=111222333,
        notifications_enabled=False,
    )

    res1 = await cust_svc.record_customer_sale(
        user_id=test_user.id,
        customer_id=c_disabled.id,
        total_amount=Decimal("100000"),
        paid_amount=Decimal("50000"),
        bot=mock_bot,
    )
    assert res1["notification_sent"] is False
    mock_bot.send_message.assert_not_called()

    # 2. Customer with no telegram_user_id
    c_no_tg = await cust_svc.create_customer(
        user_id=test_user.id,
        name="No TG User",
        telegram_user_id=None,
        notifications_enabled=True,
    )

    res2 = await cust_svc.record_customer_sale(
        user_id=test_user.id,
        customer_id=c_no_tg.id,
        total_amount=Decimal("100000"),
        paid_amount=Decimal("50000"),
        bot=mock_bot,
    )
    assert res2["notification_sent"] is False
    mock_bot.send_message.assert_not_called()

    # 3. Customer with full payment (new_debt == 0) -> no debt notification needed
    c_active = await cust_svc.create_customer(
        user_id=test_user.id,
        name="Active User",
        telegram_user_id=999888777,
        notifications_enabled=True,
    )

    res3 = await cust_svc.record_customer_sale(
        user_id=test_user.id,
        customer_id=c_active.id,
        total_amount=Decimal("100000"),
        paid_amount=Decimal("100000"),
        bot=mock_bot,
    )
    assert res3["notification_sent"] is False
    mock_bot.send_message.assert_not_called()
