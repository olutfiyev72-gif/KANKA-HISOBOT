"""Products keyboards."""
from decimal import Decimal
from typing import List
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.database.models.customer import Customer
from app.database.models.product import Product
from app.utils.formatters import format_money


def get_products_menu_keyboard() -> InlineKeyboardMarkup:
    """Product section main menu."""
    builder = InlineKeyboardBuilder()
    builder.button(text="📋 Ro'yxat", callback_data="products:list")
    builder.button(text="➕ Qo'shish", callback_data="products:add")
    builder.button(text="💰 Sotish", callback_data="products:sell")
    builder.button(text="📦 Kirim", callback_data="products:purchase")
    builder.button(text="📊 Statistika", callback_data="products:stats")
    builder.adjust(2, 2, 1)
    return builder.as_markup()


def get_product_list_keyboard(products: List[Product], action: str = "view") -> InlineKeyboardMarkup:
    """List of products as inline buttons."""
    builder = InlineKeyboardBuilder()
    for product in products:
        qty_str = (
            f"{product.quantity:.0f}"
            if product.quantity == product.quantity.to_integral_value()
            else f"{product.quantity:.2f}"
        )
        builder.button(
            text=f"📦 {product.name} ({qty_str} {product.unit} | {format_money(product.selling_price)})",
            callback_data=f"product_{action}:{product.id}",
        )
    builder.button(text="❌ Bekor qilish", callback_data=f"product_{action}:cancel")
    builder.adjust(1)
    return builder.as_markup()


def get_product_actions_keyboard(product_id: int) -> InlineKeyboardMarkup:
    """Actions for a specific product."""
    builder = InlineKeyboardBuilder()
    builder.button(text="💰 Sotish", callback_data=f"product_sell:{product_id}")
    builder.button(text="📦 Kirim", callback_data=f"product_purchase:{product_id}")
    builder.button(text="✏️ Tahrirlash", callback_data=f"product_edit:{product_id}")
    builder.button(text="🗑 O'chirish", callback_data=f"product_delete:{product_id}")
    builder.button(text="🔙 Orqaga", callback_data="products:list")
    builder.adjust(2, 2, 1)
    return builder.as_markup()


def get_sale_customer_choice_keyboard(customers: List[Customer]) -> InlineKeyboardMarkup:
    """Customer selection keyboard for sales."""
    builder = InlineKeyboardBuilder()
    for c in customers[:8]:
        debt_badge = f" (🔴 {format_money(c.total_debt)})" if c.total_debt > 0 else ""
        builder.button(
            text=f"👤 {c.name}{debt_badge}",
            callback_data=f"sell_cust:{c.id}",
        )
    builder.adjust(1)
    builder.button(text="⏩ Mijozsiz davom etish", callback_data="sell_cust:none")
    builder.button(text="❌ Bekor qilish", callback_data="sell_cust:cancel")
    return builder.as_markup()


def get_sale_payment_choice_keyboard(total_amount: Decimal) -> InlineKeyboardMarkup:
    """Quick payment selection for sale."""
    builder = InlineKeyboardBuilder()
    builder.button(
        text=f"✅ To'liq to'landi ({format_money(total_amount)})",
        callback_data="sell_pay:full",
    )
    builder.button(
        text="🔴 Qisman to'lov / Qarzga",
        callback_data="sell_pay:partial",
    )
    builder.button(text="❌ Bekor qilish", callback_data="sell_pay:cancel")
    builder.adjust(1)
    return builder.as_markup()
