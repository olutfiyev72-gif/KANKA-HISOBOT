"""Tests for expense, balance, profit calculations."""
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.transaction import PaymentMethod, TransactionType
from app.database.models.user import User
from app.database.repositories.transaction_repo import TransactionRepository


@pytest.mark.asyncio
async def test_add_expense(session: AsyncSession, test_user: User):
    """Test adding expense transaction."""
    repo = TransactionRepository(session)
    tx = await repo.create_transaction(
        user_id=test_user.id,
        type=TransactionType.EXPENSE,
        amount=Decimal("80000"),
        transaction_date=datetime.now(),
        payment_method=PaymentMethod.CARD,
        description="Reklama",
    )
    assert tx.id is not None
    assert tx.type == TransactionType.EXPENSE
    assert tx.amount == Decimal("80000")


@pytest.mark.asyncio
async def test_balance_calculation(session: AsyncSession, test_user: User):
    """Test profit = income - expense."""
    repo = TransactionRepository(session)
    now = datetime.now()

    await repo.create_transaction(
        user_id=test_user.id,
        type=TransactionType.INCOME,
        amount=Decimal("1000000"),
        transaction_date=now,
    )
    await repo.create_transaction(
        user_id=test_user.id,
        type=TransactionType.EXPENSE,
        amount=Decimal("300000"),
        transaction_date=now,
    )

    summary = await repo.get_summary(
        test_user.id,
        now - timedelta(hours=1),
        now + timedelta(hours=1),
    )

    assert summary["income"] == Decimal("1000000")
    assert summary["expense"] == Decimal("300000")
    assert summary["profit"] == Decimal("700000")


@pytest.mark.asyncio
async def test_profit_margin(session: AsyncSession, test_user: User):
    """Test profit margin calculation."""
    repo = TransactionRepository(session)
    now = datetime.now()

    await repo.create_transaction(
        user_id=test_user.id,
        type=TransactionType.INCOME,
        amount=Decimal("1000000"),
        transaction_date=now,
    )
    await repo.create_transaction(
        user_id=test_user.id,
        type=TransactionType.EXPENSE,
        amount=Decimal("442000"),
        transaction_date=now,
    )

    summary = await repo.get_summary(
        test_user.id,
        now - timedelta(hours=1),
        now + timedelta(hours=1),
    )
    # Margin = (558000 / 1000000) * 100 = 55.8%
    assert summary["margin"] == Decimal("55.80")


@pytest.mark.asyncio
async def test_cash_balance_by_method(session: AsyncSession, test_user: User):
    """Test cash balance grouped by payment method."""
    repo = TransactionRepository(session)
    now = datetime.now()

    # Add cash income
    await repo.create_transaction(
        user_id=test_user.id,
        type=TransactionType.INCOME,
        amount=Decimal("500000"),
        transaction_date=now,
        payment_method=PaymentMethod.CASH,
    )
    # Add card income
    await repo.create_transaction(
        user_id=test_user.id,
        type=TransactionType.INCOME,
        amount=Decimal("300000"),
        transaction_date=now,
        payment_method=PaymentMethod.CARD,
    )
    # Add cash expense
    await repo.create_transaction(
        user_id=test_user.id,
        type=TransactionType.EXPENSE,
        amount=Decimal("100000"),
        transaction_date=now,
        payment_method=PaymentMethod.CASH,
    )

    cash = await repo.get_cash_summary(test_user.id)
    assert cash["cash"] == Decimal("400000")   # 500k - 100k
    assert cash["card"] == Decimal("300000")
    assert cash["balance"] == Decimal("700000")  # Total net


@pytest.mark.asyncio
async def test_user_isolation(
    session: AsyncSession, test_user: User, test_user_2: User
):
    """Test that users cannot see each other's transactions."""
    repo = TransactionRepository(session)
    now = datetime.now()

    # User 1 income
    await repo.create_transaction(
        user_id=test_user.id,
        type=TransactionType.INCOME,
        amount=Decimal("999999"),
        transaction_date=now,
    )

    # User 2 should have empty data
    summary = await repo.get_summary(
        test_user_2.id,
        now - timedelta(hours=1),
        now + timedelta(hours=1),
    )
    assert summary["income"] == Decimal("0")
    assert summary["expense"] == Decimal("0")
