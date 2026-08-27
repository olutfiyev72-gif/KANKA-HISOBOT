"""Sale and SaleItem database models."""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.constants import PaymentMethod
from app.database.base import Base


class Sale(Base):
    """Sale entity representing a complete sales order (supports multiple items)."""

    __tablename__ = "sales"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    customer_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("customers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    total_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    paid_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    debt_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal("0.00"), nullable=False)
    payment_method: Mapped[PaymentMethod] = mapped_column(
        Enum(PaymentMethod), default=PaymentMethod.CASH, nullable=False
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sale_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="sales", lazy="select")  # noqa: F821
    customer: Mapped[Optional["Customer"]] = relationship(back_populates="sales", lazy="select")  # noqa: F821
    items: Mapped[List["SaleItem"]] = relationship(
        back_populates="sale", lazy="selectin", cascade="all, delete-orphan"
    )


class SaleItem(Base):
    """Line item in a sale."""

    __tablename__ = "sale_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sale_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sales.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("products.id", ondelete="SET NULL"), nullable=True, index=True
    )
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), default="dona", nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    total_price: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    cost_price: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal("0.00"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    sale: Mapped["Sale"] = relationship(back_populates="items", lazy="select")
    product: Mapped[Optional["Product"]] = relationship(lazy="select")  # noqa: F821
