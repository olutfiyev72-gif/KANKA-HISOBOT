"""Pydantic schemas for Export tasks."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

from app.config.constants import ExportFormat


class ExportRequest(BaseModel):
    user_id: int
    format: ExportFormat = Field(default=ExportFormat.EXCEL)
    start_date: datetime
    end_date: datetime
    include_debts: bool = True
    include_products: bool = True
    include_transactions: bool = True


class ExportResult(BaseModel):
    file_bytes: bytes
    filename: str
    content_type: str
    size_bytes: int
