"""Transaction model."""
import enum
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean, DateTime, Enum, ForeignKey, Integer,
    Numeric, String, Text, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class TransactionType(str, enum.Enum):
    INCOME = "income"
    EXPENSE = "expense"


class PaymentMethod(str, enum.Enum):
    CASH = "cash"          # Naqd
    CARD = "card"          # Karta
    BANK = "bank"          # Bank
    OTHER = "other"        # Boshqa


class Transaction(Base):
    """Financial transactions (income and expense)."""
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[TransactionType] = mapped_column(
        Enum(TransactionType), nullable=False, index=True
    )
    category_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("transaction_categories.id"), nullable=True
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(20, 2), nullable=False
    )
    payment_method: Mapped[PaymentMethod] = mapped_column(
        Enum(PaymentMethod), default=PaymentMethod.CASH
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Product reference (if this is a product sale)
    product_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("products.id"), nullable=True
    )
    product_quantity: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(20, 3), nullable=True
    )
    # Customer reference (if linked to a CRM customer)
    customer_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("customers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # The actual date of the transaction (user-specified)
    transaction_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    # Soft delete
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship(  # noqa: F821
        back_populates="transactions", lazy="select"
    )
    category: Mapped[Optional["TransactionCategory"]] = relationship(  # noqa: F821
        back_populates="transactions", lazy="select"
    )
    customer: Mapped[Optional["Customer"]] = relationship(  # noqa: F821
        back_populates="transactions", lazy="select"
    )
    product: Mapped[Optional["Product"]] = relationship(  # noqa: F821
        lazy="select"
    )
    inventory_transaction: Mapped[Optional["InventoryTransaction"]] = relationship(  # noqa: F821
        back_populates="transaction", lazy="select"
    )

    def __repr__(self) -> str:
        return (
            f"<Transaction id={self.id} type={self.type} "
            f"amount={self.amount} user_id={self.user_id}>"
        )
