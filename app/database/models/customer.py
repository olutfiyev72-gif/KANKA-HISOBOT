"""Customer model for CRM."""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import (
    BigInteger, Boolean, DateTime, ForeignKey, Integer,
    Numeric, String, Text, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class Customer(Base):
    """Customer entity for CRM and debt management."""
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    telegram_username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    telegram_user_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, index=True)

    # Financial aggregations with exact Decimal precision
    total_purchases: Mapped[Decimal] = mapped_column(
        Numeric(20, 2), default=Decimal("0.00"), nullable=False
    )
    total_paid: Mapped[Decimal] = mapped_column(
        Numeric(20, 2), default=Decimal("0.00"), nullable=False
    )
    total_debt: Mapped[Decimal] = mapped_column(
        Numeric(20, 2), default=Decimal("0.00"), nullable=False
    )

    notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship(  # noqa: F821
        back_populates="customers", lazy="select"
    )
    transactions: Mapped[List["Transaction"]] = relationship(  # noqa: F821
        back_populates="customer", lazy="select"
    )
    debts: Mapped[List["Debt"]] = relationship(  # noqa: F821
        back_populates="customer", lazy="select"
    )
    sales: Mapped[List["Sale"]] = relationship(  # noqa: F821
        back_populates="customer", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<Customer id={self.id} name={self.name!r} debt={self.total_debt}>"
