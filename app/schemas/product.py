"""Pydantic schemas for Product and Inventory."""
from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

from app.config.constants import InventoryAction


class ProductBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    sku: Optional[str] = Field(default=None, max_length=50)
    cost_price: Decimal = Field(..., ge=Decimal("0"), description="Cost price in Decimal")
    selling_price: Decimal = Field(..., ge=Decimal("0"), description="Selling price in Decimal")
    quantity: Decimal = Field(default=Decimal("0"), ge=Decimal("0"), description="Available stock")
    unit: str = Field(default="dona", max_length=20)
    category_id: Optional[int] = None
    min_stock_alert: Decimal = Field(default=Decimal("5"), ge=Decimal("0"))


class ProductCreate(ProductBase):
    user_id: int


class ProductUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    sku: Optional[str] = None
    cost_price: Optional[Decimal] = Field(default=None, ge=Decimal("0"))
    selling_price: Optional[Decimal] = Field(default=None, ge=Decimal("0"))
    quantity: Optional[Decimal] = Field(default=None, ge=Decimal("0"))
    unit: Optional[str] = None
    category_id: Optional[int] = None
    min_stock_alert: Optional[Decimal] = None
    is_active: Optional[bool] = None


class ProductRead(ProductBase):
    id: int
    user_id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InventoryLogCreate(BaseModel):
    product_id: int
    user_id: int
    action: InventoryAction
    quantity_change: Decimal
    previous_quantity: Decimal
    new_quantity: Decimal
    cost_price: Optional[Decimal] = None
    reason: Optional[str] = None


class InventoryLogRead(InventoryLogCreate):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
