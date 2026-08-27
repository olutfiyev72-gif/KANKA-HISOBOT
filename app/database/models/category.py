"""Transaction category model."""
import enum
from datetime import datetime
from typing import List, Optional

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class CategoryType(str, enum.Enum):
    INCOME = "income"
    EXPENSE = "expense"


class TransactionCategory(Base):
    """Transaction categories - both system defaults and user-created."""
    __tablename__ = "transaction_categories"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # null = system/default category available to all users
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    type: Mapped[CategoryType] = mapped_column(Enum(CategoryType), nullable=False)
    icon: Mapped[str] = mapped_column(String(10), default="📁")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    user: Mapped[Optional["User"]] = relationship(  # noqa: F821
        back_populates="custom_categories", lazy="select"
    )
    transactions: Mapped[List["Transaction"]] = relationship(  # noqa: F821
        back_populates="category", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<Category id={self.id} name={self.name} type={self.type}>"
