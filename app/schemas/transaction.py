"""Pydantic schemas for Transaction entity (Income, Expense, Transfer)."""
from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.config.constants import PaymentMethod, TransactionType


class TransactionBase(BaseModel):
    amount: Decimal = Field(..., gt=Decimal("0"), description="Amount in financial Decimal format")
    type: TransactionType
    payment_method: PaymentMethod = Field(default=PaymentMethod.CASH)
    description: Optional[str] = Field(default=None, max_length=500)
    transaction_date: datetime = Field(default_factory=datetime.now)
    category_id: Optional[int] = None
    product_id: Optional[int] = None
    quantity: Optional[Decimal] = Field(default=None, gt=Decimal("0"))

    @field_validator("amount", mode="before")
    @classmethod
    def convert_amount_to_decimal(cls, v: object) -> Decimal:
        if isinstance(v, (int, str)):
            return Decimal(str(v))
        if isinstance(v, float):
            return Decimal(str(v))
        if isinstance(v, Decimal):
            return v
        raise ValueError("Invalid amount format")


class TransactionCreate(TransactionBase):
    user_id: int


class TransactionUpdate(BaseModel):
    amount: Optional[Decimal] = Field(default=None, gt=Decimal("0"))
    payment_method: Optional[PaymentMethod] = None
    description: Optional[str] = None
    category_id: Optional[int] = None
    transaction_date: Optional[datetime] = None


class TransactionRead(TransactionBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
    is_deleted: bool

    model_config = ConfigDict(from_attributes=True)


class BalanceSummary(BaseModel):
    """Cash balance summary."""
    total_balance: Decimal
    total_income: Decimal
    total_expense: Decimal
    cash_balance: Decimal
    card_balance: Decimal
    bank_balance: Decimal
    other_balance: Decimal
