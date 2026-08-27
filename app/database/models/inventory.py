"""Inventory transaction model."""
import enum
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    DateTime, Enum, ForeignKey, Integer,
    Numeric, String, Text, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class InventoryTransactionType(str, enum.Enum):
    PURCHASE = "purchase"        # Mahsulot xaridi
    SALE = "sale"                # Mahsulot sotish
    ADJUSTMENT = "adjustment"    # Qo'l bilan tuzatish
    RETURN = "return"            # Qaytarish


class InventoryTransaction(Base):
    """Inventory movement history."""
    __tablename__ = "inventory_transactions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[InventoryTransactionType] = mapped_column(
        Enum(InventoryTransactionType), nullable=False
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 3), nullable=False)
    price: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 2), nullable=True)
    # Reference to financial transaction if applicable
    transaction_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("transactions.id"), nullable=True
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    product: Mapped["Product"] = relationship(  # noqa: F821
        back_populates="inventory_transactions", lazy="select"
    )
    transaction: Mapped[Optional["Transaction"]] = relationship(  # noqa: F821
        back_populates="inventory_transaction", lazy="select"
    )

    def __repr__(self) -> str:
        return (
            f"<InventoryTransaction id={self.id} "
            f"type={self.type} qty={self.quantity}>"
        )
