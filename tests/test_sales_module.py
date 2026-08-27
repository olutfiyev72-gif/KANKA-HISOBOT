"""Comprehensive integration tests for the dedicated 🛒 Sotuvlar (Sales) module,
verifying exact financial calculations, multi-product basket flows, reporting boundaries,
and Telegram delivery lifecycle.
"""
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
import pytest
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.constants import PaymentMethod
from app.database.models import User
from app.services.customer_service import CustomerService
from app.services.finance_service import FinanceService
from app.services.product_service import ProductService
from app.services.report_service import ReportService
from app.services.sale_service import SaleService


@pytest.mark.asyncio
async def test_sale_400k_250k_paid_150k_debt(session: AsyncSession, test_user: User):
    """Test exact required scenario:
    - 400,000 sale total
    - 250,000 paid amount
    - 150,000 new debt
    - Verify customer metrics, cash inflow, debt record, and financial reporting.
    """
    cust_svc = CustomerService(session)
    prod_svc = ProductService(session)
    sale_svc = SaleService(session)
    finance_svc = FinanceService(session)
    report_svc = ReportService(session)

    # 1. Create customer with 50,000 old debt
    c = await cust_svc.create_customer(
        user_id=test_user.id,
        name="Sherzodbek",
        phone="+998901234567",
        telegram_user_id=987654321,
        notifications_enabled=True,
    )
    c.total_purchases = Decimal("50000")
    c.total_debt = Decimal("50000")
    await session.flush()

    # 2. Create product
    p = await prod_svc.create_product(
        user_id=test_user.id,
        name="Kastyum Shim",
        cost_price=Decimal("250000"),
        selling_price=Decimal("400000"),
        quantity=Decimal("5"),
        unit="dona",
    )
    await session.flush()

    mock_bot = MagicMock(spec=Bot)
    mock_bot.send_message = AsyncMock(return_value=True)

    # 3. Execute sale: 1 x 400,000 = 400,000 total, paid 250,000
    res = await sale_svc.process_basket_sale(
        user_id=test_user.id,
        items=[{"product_id": p.id, "quantity": Decimal("1")}],
        customer_id=c.id,
        paid_amount=Decimal("250000"),
        payment_method=PaymentMethod.CASH,
        bot=mock_bot,
        seller_name="KANKA SHOP",
    )

    # Assert exact calculations
    assert res["total_amount"] == Decimal("400000")
    assert res["paid_amount"] == Decimal("250000")
    assert res["new_debt"] == Decimal("150000")
    assert res["old_debt"] == Decimal("50000")
    assert res["total_debt"] == Decimal("200000")
    assert res["notification_sent"] is True

    # Assert database record
    sale = await sale_svc.get_sale(res["sale"].id, test_user.id)
    assert sale.total_amount == Decimal("400000")
    assert sale.paid_amount == Decimal("250000")
    assert sale.debt_amount == Decimal("150000")

    # Assert Kassa cash balance has exact paid amount (250,000)
    balances = await finance_svc.get_balance_summary(test_user.id)
    assert balances.cash_balance == Decimal("250000")

    # Assert Financial Report shows only actual received cash (250,000), NOT total sale (400,000)
    now = datetime.now()
    report = await report_svc.get_period_report(
        user_id=test_user.id,
        start_date=now - timedelta(days=1),
        end_date=now + timedelta(days=1),
    )
    assert report.total_income == Decimal("250000")


@pytest.mark.asyncio
async def test_multiple_sales_and_deleted_sales_exclusion(session: AsyncSession, test_user: User):
    """Test multiple sales aggregate summary and verify deleted sales are never counted."""
    prod_svc = ProductService(session)
    sale_svc = SaleService(session)

    p1 = await prod_svc.create_product(
        user_id=test_user.id,
        name="Sumka",
        cost_price=Decimal("60000"),
        selling_price=Decimal("100000"),
        quantity=Decimal("20"),
    )
    await session.flush()

    cust_svc = CustomerService(session)
    c = await cust_svc.create_customer(
        user_id=test_user.id,
        name="Umidjon",
    )
    await session.flush()

    # Sale 1: 100k total, 100k paid, 0 debt
    s1 = await sale_svc.process_basket_sale(
        user_id=test_user.id,
        items=[{"product_id": p1.id, "quantity": Decimal("1")}],
        paid_amount=Decimal("100000"),
    )

    # Sale 2: 200k total, 150k paid, 50k debt (with customer)
    s2 = await sale_svc.process_basket_sale(
        user_id=test_user.id,
        items=[{"product_id": p1.id, "quantity": Decimal("2")}],
        customer_id=c.id,
        paid_amount=Decimal("150000"),
    )

    # Sale 3: 300k total, 300k paid (will be deleted)
    s3 = await sale_svc.process_basket_sale(
        user_id=test_user.id,
        items=[{"product_id": p1.id, "quantity": Decimal("3")}],
        paid_amount=Decimal("300000"),
    )

    # Soft-delete Sale 3
    sale3_obj = await sale_svc.get_sale(s3["sale"].id, test_user.id)
    sale3_obj.is_deleted = True
    await session.commit()

    # Get summary
    summary = await sale_svc.get_sales_summary(test_user.id)
    assert summary.total_sales_count == 2
    assert summary.total_sales_amount == Decimal("300000")  # 100k + 200k
    assert summary.total_paid_amount == Decimal("250000")   # 100k + 150k
    assert summary.total_debt_amount == Decimal("50000")    # 0 + 50k


@pytest.mark.asyncio
async def test_multi_product_basket_inventory_deduction(session: AsyncSession, test_user: User):
    """Test multi-product sale: 3 items of Prod A and 2 items of Prod B."""
    prod_svc = ProductService(session)
    sale_svc = SaleService(session)

    pA = await prod_svc.create_product(
        user_id=test_user.id,
        name="Telefon g'ilofi",
        cost_price=Decimal("25000"),
        selling_price=Decimal("50000"),
        quantity=Decimal("10"),
    )
    pB = await prod_svc.create_product(
        user_id=test_user.id,
        name="Zaryadka",
        cost_price=Decimal("70000"),
        selling_price=Decimal("125000"),
        quantity=Decimal("10"),
    )
    await session.flush()

    # 3 * 50,000 + 2 * 125,000 = 150,000 + 250,000 = 400,000
    res = await sale_svc.process_basket_sale(
        user_id=test_user.id,
        items=[
            {"product_id": pA.id, "quantity": Decimal("3")},
            {"product_id": pB.id, "quantity": Decimal("2")},
        ],
        paid_amount=Decimal("400000"),
    )

    assert res["total_amount"] == Decimal("400000")
    assert res["paid_amount"] == Decimal("400000")
    assert res["new_debt"] == Decimal("0")

    # Verify inventory counts
    up_pA = await prod_svc.product_repo.get_by_id_and_user(pA.id, test_user.id)
    up_pB = await prod_svc.product_repo.get_by_id_and_user(pB.id, test_user.id)
    assert up_pA.quantity == Decimal("7")
    assert up_pB.quantity == Decimal("8")


@pytest.mark.asyncio
async def test_telegram_notification_delivery_matrix(session: AsyncSession, test_user: User):
    """Test all delivery conditions:
    1. Customer with notifications_enabled=True -> Delivered
    2. Customer with notifications_enabled=False -> Skipped
    3. Customer with no telegram_user_id -> Skipped
    4. Customer who blocked bot (TelegramForbiddenError) -> Handled cleanly without raising exception
    5. Customer not started (TelegramBadRequest) -> Handled cleanly without raising exception
    """
    cust_svc = CustomerService(session)
    prod_svc = ProductService(session)
    sale_svc = SaleService(session)

    p = await prod_svc.create_product(
        user_id=test_user.id,
        name="Kitob",
        cost_price=Decimal("30000"),
        selling_price=Decimal("50000"),
        quantity=Decimal("100"),
    )
    await session.flush()

    # 1. Enabled customer
    c_enabled = await cust_svc.create_customer(
        user_id=test_user.id,
        name="Nodir",
        telegram_user_id=11111,
        notifications_enabled=True,
    )
    mock_bot1 = MagicMock(spec=Bot)
    mock_bot1.send_message = AsyncMock(return_value=True)

    res1 = await sale_svc.process_basket_sale(
        user_id=test_user.id,
        items=[{"product_id": p.id, "quantity": Decimal("1")}],
        customer_id=c_enabled.id,
        paid_amount=Decimal("20000"),  # 30k debt
        bot=mock_bot1,
    )
    assert res1["notification_sent"] is True
    mock_bot1.send_message.assert_called_once()

    # 2. Disabled customer
    c_disabled = await cust_svc.create_customer(
        user_id=test_user.id,
        name="Jamshid",
        telegram_user_id=22222,
        notifications_enabled=False,
    )
    mock_bot2 = MagicMock(spec=Bot)
    mock_bot2.send_message = AsyncMock()

    res2 = await sale_svc.process_basket_sale(
        user_id=test_user.id,
        items=[{"product_id": p.id, "quantity": Decimal("1")}],
        customer_id=c_disabled.id,
        paid_amount=Decimal("20000"),
        bot=mock_bot2,
    )
    assert res2["notification_sent"] is False
    mock_bot2.send_message.assert_not_called()

    # 3. No Telegram ID customer
    c_no_tg = await cust_svc.create_customer(
        user_id=test_user.id,
        name="Mansur",
        telegram_user_id=None,
        notifications_enabled=True,
    )
    mock_bot3 = MagicMock(spec=Bot)
    mock_bot3.send_message = AsyncMock()

    res3 = await sale_svc.process_basket_sale(
        user_id=test_user.id,
        items=[{"product_id": p.id, "quantity": Decimal("1")}],
        customer_id=c_no_tg.id,
        paid_amount=Decimal("20000"),
        bot=mock_bot3,
    )
    assert res3["notification_sent"] is False
    mock_bot3.send_message.assert_not_called()

    # 4. Blocked bot (TelegramForbiddenError)
    c_blocked = await cust_svc.create_customer(
        user_id=test_user.id,
        name="Otabek",
        telegram_user_id=44444,
        notifications_enabled=True,
    )
    mock_bot4 = MagicMock(spec=Bot)
    mock_bot4.send_message = AsyncMock(side_effect=TelegramForbiddenError(method="sendMessage", message="Bot was blocked"))

    res4 = await sale_svc.process_basket_sale(
        user_id=test_user.id,
        items=[{"product_id": p.id, "quantity": Decimal("1")}],
        customer_id=c_blocked.id,
        paid_amount=Decimal("20000"),
        bot=mock_bot4,
    )
    assert res4["notification_sent"] is False

    # 5. Not started bot (TelegramBadRequest)
    c_unstarted = await cust_svc.create_customer(
        user_id=test_user.id,
        name="Ulugbek",
        telegram_user_id=55555,
        notifications_enabled=True,
    )
    mock_bot5 = MagicMock(spec=Bot)
    mock_bot5.send_message = AsyncMock(side_effect=TelegramBadRequest(method="sendMessage", message="Chat not found"))

    res5 = await sale_svc.process_basket_sale(
        user_id=test_user.id,
        items=[{"product_id": p.id, "quantity": Decimal("1")}],
        customer_id=c_unstarted.id,
        paid_amount=Decimal("20000"),
        bot=mock_bot5,
    )
    assert res5["notification_sent"] is False


@pytest.mark.asyncio
async def test_sales_date_range_filtering(session: AsyncSession, test_user: User):
    """Test date filtering for sales summaries."""
    sale_repo = SaleService(session).sale_repo

    now = datetime.now()
    yesterday = now - timedelta(days=1)
    last_week = now - timedelta(days=7)

    # Sale 1: Today
    await sale_repo.create_sale(
        user_id=test_user.id,
        total_amount=Decimal("500000"),
        paid_amount=Decimal("500000"),
        debt_amount=Decimal("0"),
        sale_date=now,
    )

    # Sale 2: Yesterday
    await sale_repo.create_sale(
        user_id=test_user.id,
        total_amount=Decimal("500000"),
        paid_amount=Decimal("300000"),
        debt_amount=Decimal("200000"),
        sale_date=yesterday,
    )

    # Sale 3: Last week
    await sale_repo.create_sale(
        user_id=test_user.id,
        total_amount=Decimal("500000"),
        paid_amount=Decimal("500000"),
        debt_amount=Decimal("0"),
        sale_date=last_week,
    )

    # 1. Summary today only
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
    summary_today = await sale_repo.get_summary(test_user.id, date_from=today_start, date_to=today_end)
    assert summary_today["total_sales_count"] == 1
    assert summary_today["total_sales_amount"] == Decimal("500000")

    # 2. Summary yesterday + today
    summary_2days = await sale_repo.get_summary(
        test_user.id,
        date_from=yesterday.replace(hour=0, minute=0, second=0, microsecond=0),
        date_to=today_end,
    )
    assert summary_2days["total_sales_count"] == 2
    assert summary_2days["total_sales_amount"] == Decimal("1000000")
    assert summary_2days["total_paid_amount"] == Decimal("800000")
    assert summary_2days["total_debt_amount"] == Decimal("200000")
