"""Pydantic schemas for Customer / CRM module."""
from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class CustomerBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    telegram_username: Optional[str] = Field(None, max_length=255)
    telegram_user_id: Optional[int] = None
    notifications_enabled: bool = True


class CustomerCreate(CustomerBase):
    pass


class CustomerUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    telegram_username: Optional[str] = Field(None, max_length=255)
    telegram_user_id: Optional[int] = None
    notifications_enabled: Optional[bool] = None
    is_active: Optional[bool] = None


class CustomerRead(CustomerBase):
    id: int
    user_id: int
    total_purchases: Decimal
    total_paid: Decimal
    total_debt: Decimal
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CustomerSummary(BaseModel):
    total_customers: int = 0
    active_customers: int = 0
    total_debtors: int = 0
    total_customer_debt: Decimal = Decimal("0.00")
    total_customer_purchases: Decimal = Decimal("0.00")
