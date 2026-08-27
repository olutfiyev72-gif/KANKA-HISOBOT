"""Tests for product operations."""
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.user import User
from app.database.repositories.product_repo import ProductRepository
from app.database.repositories.inventory_repo import InventoryRepository
from app.database.models.inventory import InventoryTransactionType


@pytest.mark.asyncio
async def test_add_product(session: AsyncSession, test_user: User):
    """Test adding a new product."""
    repo = ProductRepository(session)
    product = await repo.create(
        user_id=test_user.id,
        name="Mayiz",
        cost_price=Decimal("45000"),
        selling_price=Decimal("65000"),
        quantity=Decimal("35"),
        unit="kg",
    )
    assert product.id is not None
    assert product.name == "Mayiz"
    assert product.cost_price == Decimal("45000")
    assert product.selling_price == Decimal("65000")


@pytest.mark.asyncio
async def test_product_profit_calculation(session: AsyncSession, test_user: User):
    """Test profit per unit and margin calculation."""
    repo = ProductRepository(session)
    product = await repo.create(
        user_id=test_user.id,
        name="Test Mahsulot",
        cost_price=Decimal("45000"),
        selling_price=Decimal("65000"),
        quantity=Decimal("10"),
        unit="kg",
    )
    assert product.profit_per_unit == Decimal("20000")
    expected_margin = (Decimal("20000") / Decimal("65000") * 100).quantize(Decimal("0.01"))
    assert product.profit_margin == expected_margin


@pytest.mark.asyncio
async def test_sell_product_updates_quantity(session: AsyncSession, test_user: User):
    """Test that selling a product decreases inventory."""
    repo = ProductRepository(session)
    inv_repo = InventoryRepository(session)
    
    product = await repo.create(
        user_id=test_user.id,
        name="Savdo mahsulot",
        cost_price=Decimal("10000"),
        selling_price=Decimal("15000"),
        quantity=Decimal("20"),
        unit="dona",
    )
    
    # Sell 5 units
    await repo.update_quantity(product, Decimal("-5"))
    await inv_repo.add_inventory_transaction(
        product_id=product.id,
        user_id=test_user.id,
        type=InventoryTransactionType.SALE,
        quantity=Decimal("5"),
        price=Decimal("15000"),
    )
    
    assert product.quantity == Decimal("15")


@pytest.mark.asyncio
async def test_oversell_raises_error(session: AsyncSession, test_user: User):
    """Test that selling more than available raises ValueError."""
    repo = ProductRepository(session)
    product = await repo.create(
        user_id=test_user.id,
        name="Oz mahsulot",
        cost_price=Decimal("10000"),
        selling_price=Decimal("15000"),
        quantity=Decimal("5"),
        unit="dona",
    )
    
    with pytest.raises(ValueError, match="Yetarli mahsulot yo'q"):
        await repo.update_quantity(product, Decimal("-10"))


@pytest.mark.asyncio
async def test_product_user_isolation(
    session: AsyncSession, test_user: User, test_user_2: User
):
    """Test that users cannot access each other's products."""
    repo = ProductRepository(session)
    
    product = await repo.create(
        user_id=test_user.id,
        name="Faqat Men Uchun",
        cost_price=Decimal("10000"),
        selling_price=Decimal("15000"),
        quantity=Decimal("10"),
        unit="dona",
    )
    
    # User 2 cannot access user 1's product
    found = await repo.get_by_id_and_user(product.id, test_user_2.id)
    assert found is None
    
    # User 1 can access their own product
    found = await repo.get_by_id_and_user(product.id, test_user.id)
    assert found is not None
    assert found.name == "Faqat Men Uchun"
