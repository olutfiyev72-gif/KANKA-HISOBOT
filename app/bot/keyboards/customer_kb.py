"""Customer CRM keyboards."""
from typing import List
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.database.models.customer import Customer
from app.utils.formatters import format_money


def get_customer_main_keyboard() -> InlineKeyboardMarkup:
    """Main CRM menu."""
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Yangi mijoz", callback_data="cust:add")
    builder.button(text="🔍 Qidirish", callback_data="cust:search")
    builder.button(text="📋 Barcha mijozlar", callback_data="cust:list:0")
    builder.button(text="📊 CRM Tahlil", callback_data="cust:summary")
    builder.adjust(2, 2)
    return builder.as_markup()


def get_customer_list_keyboard(
    customers: List[Customer], action: str = "view", offset: int = 0, has_more: bool = False
) -> InlineKeyboardMarkup:
    """List of customer buttons."""
    builder = InlineKeyboardBuilder()
    for c in customers:
        debt_badge = f" (🔴 {format_money(c.total_debt)})" if c.total_debt > 0 else ""
        builder.button(
            text=f"👤 {c.name}{debt_badge}",
            callback_data=f"cust_{action}:{c.id}",
        )
    builder.adjust(1)

    # Navigation buttons
    nav_buttons = []
    if offset > 0:
        nav_buttons.append(("⬅️ Oldingi", f"cust:list:{max(0, offset - 10)}"))
    if has_more:
        nav_buttons.append(("Keyingi ➡️", f"cust:list:{offset + 10}"))

    if nav_buttons:
        for text, cb in nav_buttons:
            builder.button(text=text, callback_data=cb)
        builder.adjust(1, len(nav_buttons))

    builder.button(text="🔙 CRM Bosh sahifa", callback_data="cust:menu")
    return builder.as_markup()


def get_customer_detail_keyboard(
    customer_id: int,
    has_debt: bool = False,
    notifications_enabled: bool = True,
    is_active: bool = True,
) -> InlineKeyboardMarkup:
    """Actions on a specific customer profile."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🛍 Xarid yozish", callback_data=f"cust_sale:{customer_id}")
    if has_debt:
        builder.button(text="💵 Qarz to'lovi", callback_data=f"cust_pay:{customer_id}")

    builder.button(text="📜 Xaridlar", callback_data=f"cust_hist_tx:{customer_id}")
    builder.button(text="📑 Qarzlar", callback_data=f"cust_hist_debt:{customer_id}")

    builder.button(text="✏️ Tahrirlash", callback_data=f"cust_edit:{customer_id}")
    
    notif_text = "🔔 Xabar: Yoqilgan" if notifications_enabled else "🔕 Xabar: O'chirilgan"
    builder.button(text=notif_text, callback_data=f"cust_toggle_notif:{customer_id}")

    status_text = "🚫 Noo'rin qilish" if is_active else "✅ Faollashtirish"
    builder.button(text=status_text, callback_data=f"cust_toggle_active:{customer_id}")

    builder.button(text="🔙 Mijozlar ro'yxati", callback_data="cust:list:0")
    builder.adjust(2, 2, 2, 1, 1)
    return builder.as_markup()


def get_customer_edit_keyboard(customer_id: int) -> InlineKeyboardMarkup:
    """Fields that can be edited."""
    builder = InlineKeyboardBuilder()
    builder.button(text="👤 Ism", callback_data=f"cust_ed_f:name:{customer_id}")
    builder.button(text="📞 Telefon", callback_data=f"cust_ed_f:phone:{customer_id}")
    builder.button(text="🔗 Username", callback_data=f"cust_ed_f:username:{customer_id}")
    builder.button(text="🆔 Telegram ID", callback_data=f"cust_ed_f:tg_id:{customer_id}")
    builder.button(text="🔙 Orqaga", callback_data=f"cust_view:{customer_id}")
    builder.adjust(2, 2, 1)
    return builder.as_markup()
