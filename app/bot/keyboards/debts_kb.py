"""Debts keyboards."""
from typing import List
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.database.models.debt import Debt, DebtStatus, DebtType


def get_debt_menu_keyboard() -> InlineKeyboardMarkup:
    """Debt section main menu."""
    builder = InlineKeyboardBuilder()
    builder.button(text="💚 Menga berishlari kerak", callback_data="debts:receivable")
    builder.button(text="❤️ Men berishim kerak", callback_data="debts:payable")
    builder.button(text="➕ Yangi qarz", callback_data="debts:add")
    builder.button(text="📊 Xulosa", callback_data="debts:summary")
    builder.adjust(1, 1, 2)
    return builder.as_markup()


def get_debt_list_keyboard(debts: List[Debt]) -> InlineKeyboardMarkup:
    """List of debts as inline buttons."""
    builder = InlineKeyboardBuilder()
    status_emoji = {
        DebtStatus.ACTIVE: "🟡",
        DebtStatus.PAID: "🟢",
        DebtStatus.OVERDUE: "🔴",
        DebtStatus.PARTIAL: "🟠",
    }
    for debt in debts:
        emoji = status_emoji.get(debt.status, "⚪")
        remaining = debt.amount - debt.paid_amount
        builder.button(
            text=f"{emoji} {debt.contact_name} — {remaining:,.0f}".replace(",", " "),
            callback_data=f"debt_view:{debt.id}"
        )
    builder.button(text="🔙 Orqaga", callback_data="debts:menu")
    builder.adjust(1)
    return builder.as_markup()


def get_debt_actions_keyboard(debt_id: int, status: DebtStatus) -> InlineKeyboardMarkup:
    """Actions for a specific debt."""
    builder = InlineKeyboardBuilder()
    if status != DebtStatus.PAID:
        builder.button(text="💰 To'lov qo'shish", callback_data=f"debt_pay:{debt_id}")
    builder.button(text="✏️ Tahrirlash", callback_data=f"debt_edit:{debt_id}")
    builder.button(text="🗑 O'chirish", callback_data=f"debt_delete:{debt_id}")
    builder.button(text="🔙 Orqaga", callback_data="debts:menu")
    if status != DebtStatus.PAID:
        builder.adjust(1, 2, 1)
    else:
        builder.adjust(2, 1)
    return builder.as_markup()


def get_debt_type_keyboard() -> InlineKeyboardMarkup:
    """Select debt type when adding."""
    builder = InlineKeyboardBuilder()
    builder.button(text="💚 Menga berishi kerak", callback_data="debt_type:receivable")
    builder.button(text="❤️ Men berishi kerakman", callback_data="debt_type:payable")
    builder.button(text="❌ Bekor qilish", callback_data="debt_type:cancel")
    builder.adjust(1)
    return builder.as_markup()
