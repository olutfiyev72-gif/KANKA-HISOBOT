"""Pydantic schemas for User entity."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

from app.config.constants import UserRole


class UserBase(BaseModel):
    telegram_id: int
    username: Optional[str] = None
    first_name: str
    last_name: Optional[str] = None
    business_name: Optional[str] = None
    language: str = Field(default="uz", max_length=10)
    role: UserRole = Field(default=UserRole.OWNER)
    is_active: bool = True


class UserCreate(UserBase):
    pass


class UserUpdate(BaseModel):
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    business_name: Optional[str] = None
    language: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None


class UserRead(UserBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
