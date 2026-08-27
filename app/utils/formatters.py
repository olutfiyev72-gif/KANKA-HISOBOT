"""Formatting utilities for monetary values, dates, etc."""
from datetime import datetime
from decimal import Decimal
from typing import Optional

import pytz

from app.config import settings


def format_money(amount: Decimal, currency: str = "so'm") -> str:
    """Format decimal amount as money string.
    
    Example: 1250000 -> "1 250 000 so'm"
    """
    if amount is None:
        amount = Decimal("0")
    # Format with thousands separator
    formatted = f"{amount:,.0f}".replace(",", " ")
    return f"{formatted} {currency}"


def format_money_short(amount: Decimal) -> str:
    """Short format for money (no currency label).
    
    Example: 1250000 -> "1 250 000"
    """
    if amount is None:
        amount = Decimal("0")
    return f"{amount:,.0f}".replace(",", " ")


def format_percentage(value: Decimal) -> str:
    """Format percentage value.
    
    Example: 44.23 -> "44.2%"
    """
    if value is None:
        value = Decimal("0")
    return f"{value:.1f}%"


def format_quantity(value: Decimal, unit: str = "dona") -> str:
    """Format quantity with unit.
    
    Example: 35.5, "kg" -> "35.5 kg"
    """
    if value == value.to_integral_value():
        return f"{int(value)} {unit}"
    return f"{value:.3f}".rstrip("0") + f" {unit}"


def format_date(dt: datetime, timezone: str = None) -> str:
    """Format datetime to local date string.
    
    Example: 2024-08-15 -> "15-Avgust 2024"
    """
    if timezone is None:
        timezone = settings.default_timezone
    
    tz = pytz.timezone(timezone)
    if dt.tzinfo is None:
        dt = pytz.utc.localize(dt)
    local_dt = dt.astimezone(tz)
    
    months_uz = [
        "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
        "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr"
    ]
    month_name = months_uz[local_dt.month - 1]
    return f"{local_dt.day}-{month_name} {local_dt.year}"


def format_datetime(dt: datetime, timezone: str = None) -> str:
    """Format datetime to local datetime string."""
    if timezone is None:
        timezone = settings.default_timezone
    
    tz = pytz.timezone(timezone)
    if dt.tzinfo is None:
        dt = pytz.utc.localize(dt)
    local_dt = dt.astimezone(tz)
    return local_dt.strftime("%d.%m.%Y %H:%M")


def format_date_short(dt: datetime, timezone: str = None) -> str:
    """Short date format: 15.08.2024"""
    if timezone is None:
        timezone = settings.default_timezone
    
    tz = pytz.timezone(timezone)
    if dt.tzinfo is None:
        dt = pytz.utc.localize(dt)
    local_dt = dt.astimezone(tz)
    return local_dt.strftime("%d.%m.%Y")


def get_month_name(month: int) -> str:
    """Get Uzbek month name."""
    months_uz = [
        "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
        "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr"
    ]
    return months_uz[month - 1]


def format_profit_indicator(profit: Decimal) -> str:
    """Return emoji indicator for profit/loss."""
    if profit > 0:
        return "🟢"
    elif profit < 0:
        return "🔴"
    return "⚪"


def parse_date_input(date_str: str, user_timezone: str = None) -> Optional[datetime]:
    """Parse user-inputted date string to datetime.
    
    Accepts formats: "15.08.2024", "15/08/2024", "15-08-2024", "bugun", "kecha"
    """
    if user_timezone is None:
        user_timezone = settings.default_timezone
    
    tz = pytz.timezone(user_timezone)
    now = datetime.now(tz)
    
    lower = date_str.lower().strip()
    if lower in ("bugun", "today", "b"):
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if lower in ("kecha", "yesterday", "k"):
        from datetime import timedelta
        yesterday = now - timedelta(days=1)
        return yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Try different date formats
    formats = ["%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"]
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str.strip(), fmt)
            return tz.localize(dt)
        except ValueError:
            continue
    
    return None
