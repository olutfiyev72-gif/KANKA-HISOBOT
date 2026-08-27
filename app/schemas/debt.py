"""Pydantic schemas for Debts and Debt Payments."""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.config.constants import DebtStatus, DebtType


class DebtPaymentBase(BaseModel):
    amount: Decimal = Field(..., gt=Decimal("0"), description="Payment amount")
    payment_date: datetime = Field(default_factory=datetime.now)
    description: Optional[str] = Field(default=None, max_length=500)


class DebtPaymentCreate(DebtPaymentBase):
    debt_id: int


class DebtPaymentRead(DebtPaymentBase):
    id: int
    debt_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DebtBase(BaseModel):
    contact_name: str = Field(..., min_length=1, max_length=200)
    contact_phone: Optional[str] = Field(default=None, max_length=50)
    amount: Decimal = Field(..., gt=Decimal("0"))
    type: DebtType
    status: DebtStatus = Field(default=DebtStatus.ACTIVE)
    due_date: Optional[datetime] = None
    description: Optional[str] = Field(default=None, max_length=500)
    created_date: datetime = Field(default_factory=datetime.now)


class DebtCreate(DebtBase):
    user_id: int


class DebtUpdate(BaseModel):
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    due_date: Optional[datetime] = None
    description: Optional[str] = None
    status: Optional[DebtStatus] = None


class DebtRead(DebtBase):
    id: int
    user_id: int
    paid_amount: Decimal
    remaining_amount: Decimal
    is_deleted: bool
    created_at: datetime
    updated_at: datetime
    payments: List[DebtPaymentRead] = []

    model_config = ConfigDict(from_attributes=True)


class DebtSummary(BaseModel):
    receivable_total: Decimal
    receivable_remaining: Decimal
    receivable_count: int
    payable_total: Decimal
    payable_remaining: Decimal
    payable_count: int
