"""Tests for the complete finance workflows: Income, Expense, Kassa, Reports, History & Quick Entry."""
from datetime import datetime, timedelta
from decimal import Decimal
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.constants import PaymentMethod, TransactionType
from app.database.models import User, TransactionCategory, CategoryType
from app.services.finance_service import FinanceService
from app.services.report_service import ReportService
from app.utils.quick_parser import parse_quick_entry, is_quick_entry
from app.utils.validators import validate_amount


def test_quick_parser_variations():
    """Test parsing various positive and negative quick inputs."""
    # Standard formats
    e1 = parse_quick_entry("+250000 savdo")
    assert e1 is not None
    assert e1.type == TransactionType.INCOME
    assert e1.amount == Decimal("250000")
    assert e1.description == "savdo"

    e2 = parse_quick_entry("-80000 reklama")
    assert e2 is not None
    assert e2.type == TransactionType.EXPENSE
    assert e2.amount == Decimal("80000")
    assert e2.description == "reklama"

    # Space between sign and amount
    e3 = parse_quick_entry("+ 500 000 tushum")
    assert e3 is not None
    assert e3.type == TransactionType.INCOME
    assert e3.amount == Decimal("500000")
    assert e3.description == "tushum"

    # With currency
    e4 = parse_quick_entry("-120,000 so'm ijara")
    assert e4 is not None
    assert e4.type == TransactionType.EXPENSE
    assert e4.amount == Decimal("120000")
    assert e4.description == "ijara"

    # Keyword infer
    e5 = parse_quick_entry("500000 savdo")
    assert e5.type == TransactionType.INCOME

    e6 = parse_quick_entry("150000 transport")
    assert e6.type == TransactionType.EXPENSE


def test_amount_validator():
    """Test amount validation with spaces, commas, and suffixes."""
    ok1, val1, _ = validate_amount("250 000")
    assert ok1 is True
    assert val1 == Decimal("250000")

    ok2, val2, _ = validate_amount("1,500,000.50")
    assert ok2 is True
    assert val2 == Decimal("1500000.50")

    ok3, val3, _ = validate_amount("100k")
    assert ok3 is True
    assert val3 == Decimal("100000")

    ok4, _, err4 = validate_amount("-5000")
    assert ok4 is False


@pytest.mark.asyncio
async def test_finance_workflow_crud_and_balance(
    session: AsyncSession, test_user: User
):
    """Test income/expense CRUD, update, delete, and real-time cash balance recalculation."""
    finance_svc = FinanceService(session)

    # 1. Record Income
    tx1 = await finance_svc.record_income(
        user_id=test_user.id,
        amount=Decimal("1000000"),
        payment_method=PaymentMethod.CASH,
        description="Mijozdan to'lov",
    )
    assert tx1.id is not None

    # 2. Record Expense
    tx2 = await finance_svc.record_expense(
        user_id=test_user.id,
        amount=Decimal("300000"),
        payment_method=PaymentMethod.CASH,
        description="Tushlik",
    )
    assert tx2.id is not None

    # Check Balance: 1,000,000 - 300,000 = 700,000
    b1 = await finance_svc.get_balance_summary(test_user.id)
    assert b1.total_income == Decimal("1000000")
    assert b1.total_expense == Decimal("300000")
    assert b1.total_balance == Decimal("700000")
    assert b1.cash_balance == Decimal("700000")

    # 3. Update tx1 amount to 1,200,000
    updated_tx1 = await finance_svc.update_transaction(
        transaction_id=tx1.id,
        user_id=test_user.id,
        amount=Decimal("1200000"),
    )
    assert updated_tx1.amount == Decimal("1200000")

    # Check Balance: 1,200,000 - 300,000 = 900,000
    b2 = await finance_svc.get_balance_summary(test_user.id)
    assert b2.total_income == Decimal("1200000")
    assert b2.total_balance == Decimal("900000")

    # 4. Soft Delete tx2 (expense of 300,000)
    deleted = await finance_svc.delete_transaction(tx2.id, test_user.id)
    assert deleted is True

    # Check Balance: 1,200,000 - 0 = 1,200,000
    b3 = await finance_svc.get_balance_summary(test_user.id)
    assert b3.total_income == Decimal("1200000")
    assert b3.total_expense == Decimal("0")
    assert b3.total_balance == Decimal("1200000")

    # 5. Verify transaction history excludes deleted
    history = await finance_svc.get_recent_transactions(test_user.id)
    assert len(history) == 1
    assert history[0].id == tx1.id


@pytest.mark.asyncio
async def test_report_service_full_metrics(
    session: AsyncSession, test_user: User
):
    """Test full period report with margin, categories, and date filtering."""
    finance_svc = FinanceService(session)
    report_svc = ReportService(session)

    # Categories
    cat_savdo = TransactionCategory(
        user_id=test_user.id,
        name="Asosiy Savdo",
        type=CategoryType.INCOME,
        icon="🛍",
    )
    cat_reklama = TransactionCategory(
        user_id=test_user.id,
        name="Target Reklama",
        type=CategoryType.EXPENSE,
        icon="📢",
    )
    session.add_all([cat_savdo, cat_reklama])
    await session.flush()

    now = datetime.now()

    # Incomes
    await finance_svc.record_income(
        user_id=test_user.id,
        amount=Decimal("2000000"),
        category_id=cat_savdo.id,
        payment_method=PaymentMethod.CARD,
        description="Online buyurtmalar",
        transaction_date=now,
    )

    # Expenses
    await finance_svc.record_expense(
        user_id=test_user.id,
        amount=Decimal("500000"),
        category_id=cat_reklama.id,
        payment_method=PaymentMethod.CARD,
        description="Instagram target",
        transaction_date=now,
    )

    # Report
    start = now - timedelta(days=1)
    end = now + timedelta(days=1)
    rep = await report_svc.get_period_report(test_user.id, start, end)

    assert rep.total_income == Decimal("2000000")
    assert rep.total_expense == Decimal("500000")
    assert rep.net_profit == Decimal("1500000")
    # Margin = 1,500,000 / 2,000,000 * 100 = 75.0%
    assert rep.profit_margin_percent == 75.0

    assert len(rep.top_income_categories) == 1
    assert rep.top_income_categories[0].category_name == "Asosiy Savdo"
    assert rep.top_income_categories[0].total_amount == Decimal("2000000")

    assert len(rep.top_expense_categories) == 1
    assert rep.top_expense_categories[0].category_name == "Target Reklama"
    assert rep.top_expense_categories[0].total_amount == Decimal("500000")
