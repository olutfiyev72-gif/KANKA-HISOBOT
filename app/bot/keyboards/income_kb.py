"""Income keyboards."""
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup

from app.database.models.category import TransactionCategory
from app.database.models.transaction import PaymentMethod


def get_income_type_keyboard(categories: list[TransactionCategory]) -> InlineKeyboardMarkup:
    """Income category selection."""
    builder = InlineKeyboardBuilder()
    for cat in categories:
        builder.button(
            text=f"{cat.icon} {cat.name}",
            callback_data=f"income_cat:{cat.id}"
        )
    builder.button(text="➕ Yangi tur qo'shish", callback_data="income_cat:new")
    builder.button(text="❌ Bekor qilish", callback_data="income_cat:cancel")
    builder.adjust(2)
    return builder.as_markup()


def get_payment_method_keyboard(prefix: str = "pm") -> InlineKeyboardMarkup:
    """Payment method selection."""
    builder = InlineKeyboardBuilder()
    methods = [
        ("💵 Naqd", "cash"),
        ("💳 Karta", "card"),
        ("🏦 Bank", "bank"),
        ("🔄 Boshqa", "other"),
    ]
    for label, value in methods:
        builder.button(text=label, callback_data=f"{prefix}:{value}")
    builder.adjust(2)
    return builder.as_markup()


def get_expense_category_keyboard(categories: list[TransactionCategory]) -> InlineKeyboardMarkup:
    """Expense category selection."""
    builder = InlineKeyboardBuilder()
    for cat in categories:
        builder.button(
            text=f"{cat.icon} {cat.name}",
            callback_data=f"expense_cat:{cat.id}"
        )
    builder.button(text="➕ Yangi kategoriya", callback_data="expense_cat:new")
    builder.button(text="❌ Bekor qilish", callback_data="expense_cat:cancel")
    builder.adjust(2)
    return builder.as_markup()
