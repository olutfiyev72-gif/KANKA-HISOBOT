"""Product model."""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Integer,
    Numeric, String, Text, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class Product(Base):
    """Products/goods catalog."""
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sku: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cost_price: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    selling_price: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 3), default=Decimal("0"))
    unit: Mapped[str] = mapped_column(String(20), default="dona")  # dona, kg, litr, etc.
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship(  # noqa: F821
        back_populates="products", lazy="select"
    )
    inventory_transactions: Mapped[List["InventoryTransaction"]] = relationship(  # noqa: F821
        back_populates="product", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<Product id={self.id} name={self.name} qty={self.quantity}>"

    @property
    def profit_per_unit(self) -> Decimal:
        """Birlik foydasi."""
        return self.selling_price - self.cost_price

    @property
    def profit_margin(self) -> Decimal:
        """Foyda foizi."""
        if self.selling_price == 0:
            return Decimal("0")
        return (self.profit_per_unit / self.selling_price * 100).quantize(Decimal("0.01"))
