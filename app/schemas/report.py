"""Pydantic schemas for Reports and Analytics."""
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class PeriodFilter(BaseModel):
    start_date: datetime
    end_date: datetime
    category_id: Optional[int] = None
    user_id: int


class CategorySummary(BaseModel):
    category_name: str
    category_icon: Optional[str] = None
    total_amount: Decimal
    percentage: float
    transaction_count: int


class FinancialReport(BaseModel):
    total_income: Decimal = Decimal("0")
    total_expense: Decimal = Decimal("0")
    net_profit: Decimal = Decimal("0")
    profit_margin_percent: float = 0.0
    top_income_categories: List[CategorySummary] = []
    top_expense_categories: List[CategorySummary] = []
    start_date: datetime
    end_date: datetime


class AnalyticsTrendPoint(BaseModel):
    date_label: str
    income: Decimal = Decimal("0")
    expense: Decimal = Decimal("0")
    profit: Decimal = Decimal("0")


class AnalyticsOverview(BaseModel):
    trends: List[AnalyticsTrendPoint]
    daily_average_income: Decimal
    daily_average_expense: Decimal
    top_selling_products: List[Dict[str, object]] = []
