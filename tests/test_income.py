"""Tests for income operations."""
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.transaction import PaymentMethod, TransactionType
from app.database.models.user import User
from app.database.repositories.transaction_repo import TransactionRepository


@pytest.mark.asyncio
async def test_add_income(session: AsyncSession, test_user: User):
    """Test adding income transaction."""
    repo = TransactionRepository(session)
    tx = await repo.create_transaction(
        user_id=test_user.id,
        type=TransactionType.INCOME,
        amount=Decimal("250000"),
        transaction_date=datetime.now(),
        payment_method=PaymentMethod.CASH,
        description="Test daromad",
    )
    assert tx.id is not None
    assert tx.amount == Decimal("250000")
    assert tx.type == TransactionType.INCOME
    assert tx.user_id == test_user.id
    assert not tx.is_deleted


@pytest.mark.asyncio
async def test_income_no_float(session: AsyncSession, test_user: User):
    """Test that amounts are stored as NUMERIC, not float."""
    repo = TransactionRepository(session)
    tx = await repo.create_transaction(
        user_id=test_user.id,
        type=TransactionType.INCOME,
        amount=Decimal("123456.78"),
        transaction_date=datetime.now(),
    )
    assert isinstance(tx.amount, Decimal)
    assert tx.amount == Decimal("123456.78")


@pytest.mark.asyncio
async def test_income_summary(session: AsyncSession, test_user: User):
    """Test income summary calculation."""
    repo = TransactionRepository(session)
    now = datetime.now()

    await repo.create_transaction(
        user_id=test_user.id,
        type=TransactionType.INCOME,
        amount=Decimal("500000"),
        transaction_date=now,
    )
    await repo.create_transaction(
        user_id=test_user.id,
        type=TransactionType.INCOME,
        amount=Decimal("300000"),
        transaction_date=now,
    )

    start = now - timedelta(hours=1)
    end = now + timedelta(hours=1)
    summary = await repo.get_summary(test_user.id, start, end)

    assert summary["income"] == Decimal("800000")
    assert summary["income_count"] == 2


@pytest.mark.asyncio
async def test_soft_delete_income(session: AsyncSession, test_user: User):
    """Test soft delete doesn't affect other transactions."""
    repo = TransactionRepository(session)
    now = datetime.now()

    tx1 = await repo.create_transaction(
        user_id=test_user.id,
        type=TransactionType.INCOME,
        amount=Decimal("100000"),
        transaction_date=now,
    )
    tx2 = await repo.create_transaction(
        user_id=test_user.id,
        type=TransactionType.INCOME,
        amount=Decimal("200000"),
        transaction_date=now,
    )

    # Delete tx1
    deleted = await repo.soft_delete(tx1.id, test_user.id)
    assert deleted is True

    # tx2 should still be there
    summary = await repo.get_summary(
        test_user.id,
        now - timedelta(hours=1),
        now + timedelta(hours=1),
    )
    assert summary["income"] == Decimal("200000")
