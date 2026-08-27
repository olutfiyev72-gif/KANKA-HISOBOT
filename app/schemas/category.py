"""Pydantic schemas for Category entity."""
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

from app.config.constants import TransactionType


class CategoryBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    type: TransactionType
    icon: Optional[str] = Field(default=None, max_length=10)
    is_default: bool = False


class CategoryCreate(CategoryBase):
    user_id: Optional[int] = None


class CategoryUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    icon: Optional[str] = Field(default=None, max_length=10)


class CategoryRead(CategoryBase):
    id: int
    user_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)
