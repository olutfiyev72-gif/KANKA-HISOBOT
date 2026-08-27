"""Pydantic schemas for Sales orders and line items."""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.config.constants import PaymentMethod


class SaleItemCreate(BaseModel):
    product_id: int
    quantity: Decimal = Field(..., gt=Decimal("0"))
    unit_price: Optional[Decimal] = None


class SaleItemRead(BaseModel):
    id: int
    sale_id: int
    product_id: Optional[int] = None
    product_name: str
    unit: str
    quantity: Decimal
    unit_price: Decimal
    total_price: Decimal
    cost_price: Decimal
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SaleCreate(BaseModel):
    customer_id: Optional[int] = None
    items: List[SaleItemCreate] = Field(..., min_length=1)
    paid_amount: Optional[Decimal] = None
    payment_method: PaymentMethod = PaymentMethod.CASH
    description: Optional[str] = None


class SaleRead(BaseModel):
    id: int
    user_id: int
    customer_id: Optional[int] = None
    total_amount: Decimal
    paid_amount: Decimal
    debt_amount: Decimal
    payment_method: PaymentMethod
    description: Optional[str] = None
    sale_date: datetime
    is_deleted: bool
    created_at: datetime
    items: List[SaleItemRead] = []

    model_config = ConfigDict(from_attributes=True)


class SaleSummary(BaseModel):
    total_sales_count: int = 0
    total_sales_amount: Decimal = Decimal("0.00")
    total_paid_amount: Decimal = Decimal("0.00")
    total_debt_amount: Decimal = Decimal("0.00")
