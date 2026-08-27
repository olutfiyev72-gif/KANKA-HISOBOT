"""Debt model."""
import enum
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import (
    Boolean, DateTime, Enum, ForeignKey, Integer,
    Numeric, String, Text, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class DebtType(str, enum.Enum):
    RECEIVABLE = "receivable"   # Mendan olishlari kerak (biz berishimiz kerak — NO!)
    # Actually: receivable = boshqa menga pul berishi kerak (men olishim kerak)
    # payable = men pul berishi kerakman
    PAYABLE = "payable"         # Men berishim kerak


class DebtStatus(str, enum.Enum):
    ACTIVE = "active"       # 🟡 Faol qarzdorlik
    PAID = "paid"           # 🟢 To'langan
    OVERDUE = "overdue"     # 🔴 Muddati o'tgan
    PARTIAL = "partial"     # 🟠 Qisman to'langan


class Debt(Base):
    """Debt tracking for receivables and payables."""
    __tablename__ = "debts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[DebtType] = mapped_column(Enum(DebtType), nullable=False, index=True)
    contact_name: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    customer_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("customers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    paid_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal("0"))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[DebtStatus] = mapped_column(
        Enum(DebtStatus), default=DebtStatus.ACTIVE, index=True
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship(  # noqa: F821
        back_populates="debts", lazy="select"
    )
    customer: Mapped[Optional["Customer"]] = relationship(  # noqa: F821
        back_populates="debts", lazy="select"
    )
    payments: Mapped[List["DebtPayment"]] = relationship(
        back_populates="debt", lazy="select", cascade="all, delete-orphan"
    )

    @property
    def remaining_amount(self) -> Decimal:
        return self.amount - self.paid_amount

    def __repr__(self) -> str:
        return (
            f"<Debt id={self.id} type={self.type} "
            f"contact={self.contact_name} amount={self.amount}>"
        )


class DebtPayment(Base):
    """Individual payments against a debt."""
    __tablename__ = "debt_payments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    debt_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("debts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    payment_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    debt: Mapped["Debt"] = relationship(back_populates="payments", lazy="select")

    def __repr__(self) -> str:
        return f"<DebtPayment id={self.id} debt_id={self.debt_id} amount={self.amount}>"
