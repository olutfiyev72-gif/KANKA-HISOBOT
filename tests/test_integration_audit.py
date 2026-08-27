"""Critical Integration Tests for System Audit.

Covers:
1. Cross-user isolation (Products, Debts, Transactions, Reports, Categories).
2. End-to-end Income + Expense -> Balance & Profit calculation.
3. End-to-end Inventory deduction on sale with InventoryLog tracking.
4. End-to-end Debt multi-step partial payments and status transitions.
5. End-to-end Period Financial Report matching transaction aggregates.
"""
from datetime import datetime, timedelta
from decimal import Decimal
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.constants import PaymentMethod, TransactionType, DebtType, DebtStatus
from app.database.models import User, TransactionCategory, CategoryType
from app.database.repositories.transaction_repo import TransactionRepository
from app.database.repositories.product_repo import ProductRepository
from app.database.repositories.debt_repo import DebtRepository
from app.database.repositories.inventory_repo import InventoryRepository
from app.services.finance_service import FinanceService
from app.services.product_service import ProductService
from app.services.debt_service import DebtService
from app.services.report_service import ReportService


# ============================================================================
# 1. CROSS-USER DATA ISOLATION INTEGRATION
# ============================================================================
@pytest.mark.asyncio
async def test_cross_user_data_isolation(
    session: AsyncSession, test_user: User, test_user_2: User
):
    """Verify User A cannot access, modify, or view User B's entities."""
    tx_repo = TransactionRepository(session)
    prod_repo = ProductRepository(session)
    debt_repo = DebtRepository(session)
    report_svc = ReportService(session)

    # 1. User A creates a transaction
    tx_a = await tx_repo.create_transaction(
        user_id=test_user.id,
        type=TransactionType.INCOME,
        amount=Decimal("1500000.00"),
        transaction_date=datetime.now(),
        description="User A Secret Income",
    )

    # User B cannot fetch or delete User A's transaction
    tx_b_view = await tx_repo.get_user_transaction(tx_a.id, test_user_2.id)
    assert tx_b_view is None

    deleted_by_b = await tx_repo.soft_delete(tx_a.id, test_user_2.id)
    assert deleted_by_b is False

    # 2. User A creates a product
    prod_a = await prod_repo.create(
        user_id=test_user.id,
        name="User A iPhone",
        cost_price=Decimal("8000000"),
        selling_price=Decimal("10000000"),
        quantity=Decimal("5"),
    )

    # User B cannot fetch User A's product
    prod_b_view = await prod_repo.get_by_id_and_user(prod_a.id, test_user_2.id)
    assert prod_b_view is None

    user_b_products = await prod_repo.get_user_products(test_user_2.id)
    assert len(user_b_products) == 0

    # 3. User A creates a debt
    debt_a = await debt_repo.create(
        user_id=test_user.id,
        contact_name="Karim Qarz",
        amount=Decimal("3000000"),
        created_date=datetime.now(),
        type=DebtType.RECEIVABLE,
    )

    # User B cannot fetch User A's debt
    debt_b_view = await debt_repo.get_by_id_and_user(debt_a.id, test_user_2.id)
    assert debt_b_view is None

    user_b_debts = await debt_repo.get_user_debts(test_user_2.id)
    assert len(user_b_debts) == 0

    # 4. User B's report remains empty despite User A's activity
    now = datetime.now()
    report_b = await report_svc.get_period_report(
        user_id=test_user_2.id,
        start_date=now - timedelta(days=1),
        end_date=now + timedelta(days=1),
    )
    assert report_b.total_income == Decimal("0")
    assert report_b.total_expense == Decimal("0")
    assert report_b.net_profit == Decimal("0")


# ============================================================================
# 2. INCOME + EXPENSE = CORRECT BALANCE & PROFIT INTEGRATION
# ============================================================================
@pytest.mark.asyncio
async def test_income_expense_balance_and_profit(
    session: AsyncSession, test_user: User
):
    """Verify multi-channel income/expenses compute exact balance and profit margin."""
    finance_svc = FinanceService(session)

    # Income entries
    await finance_svc.record_income(
        user_id=test_user.id,
        amount=Decimal("5000000.50"),
        payment_method=PaymentMethod.CASH,
        description="Cash sales",
    )
    await finance_svc.record_income(
        user_id=test_user.id,
        amount=Decimal("3000000.25"),
        payment_method=PaymentMethod.CARD,
        description="Card sales",
    )
    await finance_svc.record_income(
        user_id=test_user.id,
        amount=Decimal("2000000.00"),
        payment_method=PaymentMethod.BANK,
        description="Bank transfer",
    )

    # Expense entries
    await finance_svc.record_expense(
        user_id=test_user.id,
        amount=Decimal("1500000.25"),
        payment_method=PaymentMethod.CASH,
        description="Rent",
    )
    await finance_svc.record_expense(
        user_id=test_user.id,
        amount=Decimal("500000.50"),
        payment_method=PaymentMethod.CARD,
        description="Marketing",
    )

    # Total Income: 5,000,000.50 + 3,000,000.25 + 2,000,000.00 = 10,000,000.75
    # Total Expense: 1,500,000.25 + 500,000.50 = 2,000,000.75
    # Net Profit: 8,000,000.00
    # Cash Balance: 5,000,000.50 - 1,500,000.25 = 3,500,000.25
    # Card Balance: 3,000,000.25 - 500,000.50 = 2,499,999.75
    # Bank Balance: 2,000,000.00

    summary = await finance_svc.get_balance_summary(test_user.id)

    assert summary.total_income == Decimal("10000000.75")
    assert summary.total_expense == Decimal("2000000.75")
    assert summary.total_balance == Decimal("8000000.00")
    assert summary.cash_balance == Decimal("3500000.25")
    assert summary.card_balance == Decimal("2499999.75")
    assert summary.bank_balance == Decimal("2000000.00")


# ============================================================================
# 3. INVENTORY SALE & STOCK DECREASE INTEGRATION
# ============================================================================
@pytest.mark.asyncio
async def test_inventory_decreases_after_sale_with_logs(
    session: AsyncSession, test_user: User
):
    """Verify selling stock decreases product quantity and creates inventory transactions."""
    prod_svc = ProductService(session)
    inv_repo = InventoryRepository(session)

    # 1. Create product with initial quantity of 20
    product = await prod_svc.create_product(
        user_id=test_user.id,
        name="Nike Air Max",
        cost_price=Decimal("600000"),
        selling_price=Decimal("950000"),
        quantity=Decimal("20"),
        unit="juft",
    )
    assert product.quantity == Decimal("20")

    # 2. Sell 7 items
    updated_prod = await prod_svc.sell_stock(
        product_id=product.id,
        user_id=test_user.id,
        quantity=Decimal("7"),
    )
    assert updated_prod.quantity == Decimal("13")

    # 3. Verify inventory transaction log
    history = await inv_repo.get_product_history(product.id, test_user.id)
    assert len(history) == 1
    assert history[0].quantity == Decimal("7")
    assert history[0].price == Decimal("950000")

    # 4. Sell remaining 13 items
    updated_prod = await prod_svc.sell_stock(
        product_id=product.id,
        user_id=test_user.id,
        quantity=Decimal("13"),
    )
    assert updated_prod.quantity == Decimal("0")

    # 5. Oversell attempt must raise ValueError
    with pytest.raises(ValueError, match="Yetarli mahsulot yo'q"):
        await prod_svc.sell_stock(
            product_id=product.id,
            user_id=test_user.id,
            quantity=Decimal("1"),
        )


# ============================================================================
# 4. DEBT MULTI-STEP PARTIAL PAYMENTS INTEGRATION
# ============================================================================
@pytest.mark.asyncio
async def test_debt_partial_payments_lifecycle(
    session: AsyncSession, test_user: User
):
    """Verify multi-step debt payments give correct remaining balances and status transitions."""
    debt_svc = DebtService(session)

    # 1. Create Debt of 1,000,000 UZS
    debt = await debt_svc.create_debt(
        user_id=test_user.id,
        contact_name="Jasur Akromov",
        contact_phone="+998901112233",
        amount=Decimal("1000000"),
        debt_type=DebtType.RECEIVABLE,
        due_date=datetime.now() + timedelta(days=15),
    )
    assert debt.status == DebtStatus.ACTIVE
    assert debt.remaining_amount == Decimal("1000000")

    # 2. First payment of 300,000 UZS
    p1 = await debt_svc.record_payment(
        debt_id=debt.id,
        user_id=test_user.id,
        amount=Decimal("300000"),
        description="1-qism to'lov",
    )
    assert p1.amount == Decimal("300000")
    assert debt.paid_amount == Decimal("300000")
    assert debt.remaining_amount == Decimal("700000")
    assert debt.status == DebtStatus.PARTIAL

    # 3. Second payment of 400,000 UZS
    p2 = await debt_svc.record_payment(
        debt_id=debt.id,
        user_id=test_user.id,
        amount=Decimal("400000"),
        description="2-qism to'lov",
    )
    assert p2.amount == Decimal("400000")
    assert debt.paid_amount == Decimal("700000")
    assert debt.remaining_amount == Decimal("300000")
    assert debt.status == DebtStatus.PARTIAL

    # 4. Final settlement of 300,000 UZS
    p3 = await debt_svc.record_payment(
        debt_id=debt.id,
        user_id=test_user.id,
        amount=Decimal("300000"),
        description="Yakuniy to'lov",
    )
    assert p3.amount == Decimal("300000")
    assert debt.paid_amount == Decimal("1000000")
    assert debt.remaining_amount == Decimal("0")
    assert debt.status == DebtStatus.PAID

    # 5. Overpayment attempt must fail
    with pytest.raises(ValueError, match="To'lov summasi qoldiqdan"):
        await debt_svc.record_payment(
            debt_id=debt.id,
            user_id=test_user.id,
            amount=Decimal("10000"),
        )


# ============================================================================
# 5. REPORT ACCURACY MATCHING TRANSACTIONS INTEGRATION
# ============================================================================
@pytest.mark.asyncio
async def test_financial_report_matches_transactions(
    session: AsyncSession, test_user: User
):
    """Verify period financial report matches exact transaction sums and category breakdowns."""
    tx_repo = TransactionRepository(session)
    report_svc = ReportService(session)

    # Create test categories
    cat_sales = TransactionCategory(
        user_id=test_user.id,
        name="Chakana savdo",
        type=CategoryType.INCOME,
        icon="🛍",
    )
    cat_wholesale = TransactionCategory(
        user_id=test_user.id,
        name="Ulgurji savdo",
        type=CategoryType.INCOME,
        icon="📦",
    )
    cat_rent = TransactionCategory(
        user_id=test_user.id,
        name="Ijara",
        type=CategoryType.EXPENSE,
        icon="🏢",
    )
    session.add_all([cat_sales, cat_wholesale, cat_rent])
    await session.flush()

    now = datetime.now()

    # Incomes within period
    await tx_repo.create_transaction(
        user_id=test_user.id,
        type=TransactionType.INCOME,
        amount=Decimal("4000000"),
        category_id=cat_sales.id,
        transaction_date=now - timedelta(days=2),
    )
    await tx_repo.create_transaction(
        user_id=test_user.id,
        type=TransactionType.INCOME,
        amount=Decimal("6000000"),
        category_id=cat_wholesale.id,
        transaction_date=now - timedelta(days=1),
    )

    # Expenses within period
    await tx_repo.create_transaction(
        user_id=test_user.id,
        type=TransactionType.EXPENSE,
        amount=Decimal("2500000"),
        category_id=cat_rent.id,
        transaction_date=now - timedelta(hours=12),
    )

    # Out-of-period transaction (must NOT be in report)
    await tx_repo.create_transaction(
        user_id=test_user.id,
        type=TransactionType.INCOME,
        amount=Decimal("9999999"),
        transaction_date=now - timedelta(days=30),
    )

    # Generate 7-day report
    start = now - timedelta(days=7)
    end = now + timedelta(hours=1)
    report = await report_svc.get_period_report(test_user.id, start, end)

    assert report.total_income == Decimal("10000000")
    assert report.total_expense == Decimal("2500000")
    assert report.net_profit == Decimal("7500000")
    # Profit margin = (7,500,000 / 10,000,000) * 100 = 75.0%
    assert report.profit_margin_percent == 75.0

    # Verify category breakdown
    assert len(report.top_income_categories) == 2
    assert len(report.top_expense_categories) == 1

    top_cat = report.top_income_categories[0]
    assert top_cat.category_name == "Ulgurji savdo"
    assert top_cat.total_amount == Decimal("6000000")
    assert top_cat.percentage == 60.0

    second_cat = report.top_income_categories[1]
    assert second_cat.category_name == "Chakana savdo"
    assert second_cat.total_amount == Decimal("4000000")
    assert second_cat.percentage == 40.0
