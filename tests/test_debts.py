"""Tests for debt operations."""
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.debt import DebtStatus, DebtType
from app.database.models.user import User
from app.database.repositories.debt_repo import DebtRepository


@pytest.mark.asyncio
async def test_add_debt(session: AsyncSession, test_user: User):
    """Test adding a new debt."""
    repo = DebtRepository(session)
    debt = await repo.create(
        user_id=test_user.id,
        type=DebtType.RECEIVABLE,
        contact_name="Ali Valiyev",
        contact_phone="+998901234567",
        amount=Decimal("500000"),
        created_date=datetime.now(),
    )
    assert debt.id is not None
    assert debt.contact_name == "Ali Valiyev"
    assert debt.amount == Decimal("500000")
    assert debt.paid_amount == Decimal("0")
    assert debt.status == DebtStatus.ACTIVE


@pytest.mark.asyncio
async def test_partial_payment(session: AsyncSession, test_user: User):
    """Test partial debt payment."""
    repo = DebtRepository(session)
    debt = await repo.create(
        user_id=test_user.id,
        type=DebtType.PAYABLE,
        contact_name="Sardor",
        amount=Decimal("1000000"),
        created_date=datetime.now(),
    )

    payment = await repo.add_payment(
        debt=debt,
        amount=Decimal("300000"),
        payment_date=datetime.now(),
    )

    assert payment.amount == Decimal("300000")
    assert debt.paid_amount == Decimal("300000")
    assert debt.remaining_amount == Decimal("700000")
    assert debt.status == DebtStatus.PARTIAL


@pytest.mark.asyncio
async def test_full_payment_closes_debt(session: AsyncSession, test_user: User):
    """Test that full payment marks debt as paid."""
    repo = DebtRepository(session)
    debt = await repo.create(
        user_id=test_user.id,
        type=DebtType.RECEIVABLE,
        contact_name="Bobur",
        amount=Decimal("200000"),
        created_date=datetime.now(),
    )

    await repo.add_payment(
        debt=debt,
        amount=Decimal("200000"),
        payment_date=datetime.now(),
    )

    assert debt.status == DebtStatus.PAID
    assert debt.remaining_amount == Decimal("0")


@pytest.mark.asyncio
async def test_overpayment_raises_error(session: AsyncSession, test_user: User):
    """Test that overpayment raises ValueError."""
    repo = DebtRepository(session)
    debt = await repo.create(
        user_id=test_user.id,
        type=DebtType.RECEIVABLE,
        contact_name="Test",
        amount=Decimal("100000"),
        created_date=datetime.now(),
    )

    with pytest.raises(ValueError, match="qoldiqdan"):
        await repo.add_payment(
            debt=debt,
            amount=Decimal("150000"),
            payment_date=datetime.now(),
        )


@pytest.mark.asyncio
async def test_overdue_detection(session: AsyncSession, test_user: User):
    """Test overdue debt detection."""
    repo = DebtRepository(session)
    past_due = datetime.now() - timedelta(days=5)

    debt = await repo.create(
        user_id=test_user.id,
        type=DebtType.RECEIVABLE,
        contact_name="Muddati O'tgan",
        amount=Decimal("300000"),
        created_date=datetime.now() - timedelta(days=30),
        due_date=past_due,
    )

    count = await repo.update_overdue_statuses(test_user.id)
    assert count >= 1

    updated_debt = await repo.get_by_id_and_user(debt.id, test_user.id)
    assert updated_debt.status == DebtStatus.OVERDUE


@pytest.mark.asyncio
async def test_debt_summary(session: AsyncSession, test_user: User):
    """Test debt summary calculation."""
    repo = DebtRepository(session)
    now = datetime.now()

    # Receivable
    await repo.create(
        user_id=test_user.id,
        type=DebtType.RECEIVABLE,
        contact_name="A",
        amount=Decimal("500000"),
        created_date=now,
    )
    # Payable
    await repo.create(
        user_id=test_user.id,
        type=DebtType.PAYABLE,
        contact_name="B",
        amount=Decimal("200000"),
        created_date=now,
    )

    summary = await repo.get_summary(test_user.id)
    assert summary["receivable_remaining"] == Decimal("500000")
    assert summary["payable_remaining"] == Decimal("200000")
