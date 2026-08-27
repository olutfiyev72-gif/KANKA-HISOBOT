"""Tests for Pydantic schemas, domain services, and configuration validation."""
from datetime import datetime, timezone
from decimal import Decimal
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.constants import PaymentMethod, TransactionType, DebtType, DebtStatus
from app.config.settings import Settings
from app.database.models import User
from app.schemas.transaction import TransactionBase, BalanceSummary
from app.schemas.product import ProductBase
from app.services.finance_service import FinanceService
from app.services.report_service import ReportService
from app.services.debt_service import DebtService


def test_settings_url_validator():
    """Test database URL driver correction to asyncpg."""
    s1 = Settings(database_url="postgresql://user:pass@localhost:5432/db")
    assert s1.database_url == "postgresql+asyncpg://user:pass@localhost:5432/db"

    s2 = Settings(database_url="postgres://user:pass@localhost:5432/db")
    assert s2.database_url == "postgresql+asyncpg://user:pass@localhost:5432/db"

    s3 = Settings(admin_ids="12345, 67890")
    assert s3.get_admin_ids() == [12345, 67890]


def test_transaction_schema_decimal_coercion():
    """Test schema enforces Decimal precision and rejects negative/zero amounts."""
    tx = TransactionBase(
        amount=150000,
        type=TransactionType.INCOME,
        payment_method=PaymentMethod.CASH,
    )
    assert isinstance(tx.amount, Decimal)
    assert tx.amount == Decimal("150000")

    with pytest.raises(Exception):
        TransactionBase(
            amount=Decimal("-5000"),
            type=TransactionType.EXPENSE,
        )


def test_product_schema_precision():
    """Test product schema decimal fields."""
    prod = ProductBase(
        name="Futbolka",
        cost_price=Decimal("45000.50"),
        selling_price=Decimal("80000.00"),
        quantity=Decimal("15"),
    )
    assert prod.cost_price == Decimal("45000.50")
    assert prod.selling_price == Decimal("80000.00")
    assert prod.quantity == Decimal("15")


@pytest.mark.asyncio
async def test_finance_service(session: AsyncSession, test_user: User):
    """Test FinanceService income recording and balance computation."""
    svc = FinanceService(session)

    # Record income
    tx1 = await svc.record_income(
        user_id=test_user.id,
        amount=Decimal("500000"),
        payment_method=PaymentMethod.CASH,
        description="Kunlik savdo",
    )
    assert tx1.amount == Decimal("500000")

    # Record expense
    tx2 = await svc.record_expense(
        user_id=test_user.id,
        amount=Decimal("150000"),
        payment_method=PaymentMethod.CASH,
        description="Transport",
    )
    assert tx2.amount == Decimal("150000")

    summary = await svc.get_balance_summary(test_user.id)
    assert summary.total_income == Decimal("500000")
    assert summary.total_expense == Decimal("150000")
    assert summary.total_balance == Decimal("350000")
    assert summary.cash_balance == Decimal("350000")


@pytest.mark.asyncio
async def test_debt_service(session: AsyncSession, test_user: User):
    """Test DebtService creation and payments."""
    svc = DebtService(session)

    debt = await svc.create_debt(
        user_id=test_user.id,
        contact_name="Ali Valiyev",
        amount=Decimal("200000"),
        debt_type=DebtType.RECEIVABLE,
    )
    assert debt.amount == Decimal("200000")
    assert debt.paid_amount == Decimal("0")

    # Pay partial
    payment = await svc.record_payment(
        debt_id=debt.id,
        user_id=test_user.id,
        amount=Decimal("50000"),
        description="Qisman to'lov",
    )
    assert payment.amount == Decimal("50000")
    assert debt.paid_amount == Decimal("50000")
    assert debt.status == DebtStatus.PARTIAL

    summary = await svc.get_summary(test_user.id)
    assert summary.receivable_total == Decimal("200000")
    assert summary.receivable_remaining == Decimal("150000")
