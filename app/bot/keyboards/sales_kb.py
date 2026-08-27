"""Sales keyboards."""
from typing import List
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.database.models.sale import Sale
from app.utils.formatters import format_money


def get_sales_main_keyboard() -> InlineKeyboardMarkup:
    """Main menu for 🛒 Sotuvlar."""
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Yangi sotuv", callback_data="sales:new")
    builder.button(text="📋 Bugungi sotuvlar", callback_data="sales:today")
    builder.button(text="📅 Sotuvlar tarixi", callback_data="sales:history:0")
    builder.button(text="🔍 Qidirish", callback_data="sales:search")
    builder.adjust(2, 2)
    return builder.as_markup()


def get_basket_keyboard() -> InlineKeyboardMarkup:
    """Basket menu options."""
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Yana mahsulot qo'shish", callback_data="basket:add_more")
    builder.button(text="✅ To'lovga o'tish", callback_data="basket:checkout")
    builder.button(text="🗑 Savatni tozalash", callback_data="basket:clear")
    builder.button(text="❌ Bekor qilish", callback_data="basket:cancel")
    builder.adjust(2, 2)
    return builder.as_markup()


def get_sales_list_keyboard(
    sales: List[Sale], offset: int = 0, has_more: bool = False, prefix: str = "history"
) -> InlineKeyboardMarkup:
    """List of sales as clickable buttons."""
    builder = InlineKeyboardBuilder()
    for s in sales:
        cust_name = s.customer.name if s.customer else "Mijozsiz"
        debt_badge = f" (🔴 {format_money(s.debt_amount)})" if s.debt_amount > 0 else ""
        date_short = s.sale_date.strftime("%d.%m %H:%M")
        builder.button(
            text=f"🛒 #{s.id} | {format_money(s.total_amount)} | {cust_name}{debt_badge}",
            callback_data=f"sale_view:{s.id}",
        )
    builder.adjust(1)

    # Navigation buttons
    nav_buttons = []
    if offset > 0:
        nav_buttons.append(("⬅️ Oldingi", f"sales:{prefix}:{max(0, offset - 10)}"))
    if has_more:
        nav_buttons.append(("Keyingi ➡️", f"sales:{prefix}:{offset + 10}"))

    if nav_buttons:
        for text, cb in nav_buttons:
            builder.button(text=text, callback_data=cb)
        builder.adjust(1, len(nav_buttons))

    builder.button(text="🔙 Sotuvlar menyusi", callback_data="sales:menu")
    return builder.as_markup()


def get_sale_detail_keyboard(sale_id: int) -> InlineKeyboardMarkup:
    """Actions on a sale view."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Sotuvlar ro'yxati", callback_data="sales:history:0")
    builder.button(text="🔙 Bosh menyu", callback_data="sales:menu")
    builder.adjust(1, 1)
    return builder.as_markup()
