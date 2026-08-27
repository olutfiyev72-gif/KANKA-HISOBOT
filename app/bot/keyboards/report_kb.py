"""Report keyboards."""
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_report_period_keyboard() -> InlineKeyboardMarkup:
    """Report period selection keyboard."""
    builder = InlineKeyboardBuilder()
    periods = [
        ("📅 Bugun", "today"),
        ("📅 Kecha", "yesterday"),
        ("📆 7 kun", "week"),
        ("📆 30 kun", "month"),
        ("📆 Bu oy", "this_month"),
        ("📆 O'tgan oy", "last_month"),
        ("🗓 Boshqa sana", "custom"),
    ]
    for label, value in periods:
        builder.button(text=label, callback_data=f"report_period:{value}")
    builder.button(text="❌ Yopish", callback_data="report_period:close")
    builder.adjust(2, 2, 2, 1, 1)
    return builder.as_markup()


def get_report_actions_keyboard(period: str) -> InlineKeyboardMarkup:
    """Actions after showing report."""
    builder = InlineKeyboardBuilder()
    builder.button(text="📊 Excel", callback_data=f"export:excel:{period}")
    builder.button(text="📄 PDF", callback_data=f"export:pdf:{period}")
    builder.button(text="🔙 Orqaga", callback_data="report_period:back")
    builder.adjust(2, 1)
    return builder.as_markup()
