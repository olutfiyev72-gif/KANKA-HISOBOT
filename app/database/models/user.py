"""User model."""
import enum
from datetime import datetime
from typing import List, Optional

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class UserStatus(str, enum.Enum):
    PENDING = "pending"      # Tasdiqlash kutilmoqda
    ACTIVE = "active"        # Faol
    BLOCKED = "blocked"      # Bloklangan


class User(Base):
    """Telegram users."""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    full_name: Mapped[str] = mapped_column(String(500), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    timezone: Mapped[str] = mapped_column(String(50), default="Asia/Tashkent")
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus), default=UserStatus.PENDING, nullable=False
    )
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    language: Mapped[str] = mapped_column(String(5), default="uz")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    last_active_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    transactions: Mapped[List["Transaction"]] = relationship(  # noqa: F821
        back_populates="user", lazy="select"
    )
    products: Mapped[List["Product"]] = relationship(  # noqa: F821
        back_populates="user", lazy="select"
    )
    debts: Mapped[List["Debt"]] = relationship(  # noqa: F821
        back_populates="user", lazy="select"
    )
    custom_categories: Mapped[List["TransactionCategory"]] = relationship(  # noqa: F821
        back_populates="user", lazy="select"
    )
    customers: Mapped[List["Customer"]] = relationship(  # noqa: F821
        back_populates="user", lazy="select"
    )
    sales: Mapped[List["Sale"]] = relationship(  # noqa: F821
        back_populates="user", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} telegram_id={self.telegram_id} name={self.full_name}>"

    @property
    def is_active(self) -> bool:
        return self.status == UserStatus.ACTIVE

    @property
    def is_pending(self) -> bool:
        return self.status == UserStatus.PENDING
