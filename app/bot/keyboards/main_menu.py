"""Main menu keyboard."""
from aiogram.types import ReplyKeyboardMarkup
from aiogram.utils.keyboard import ReplyKeyboardBuilder


def get_main_menu(is_admin: bool = False) -> ReplyKeyboardMarkup:
    """Build the main menu keyboard."""
    builder = ReplyKeyboardBuilder()
    
    # Row 1: Core Finance
    builder.button(text="💰 Daromad")
    builder.button(text="💸 Xarajat")
    
    # Row 2: Sales & Cash
    builder.button(text="🛒 Sotuvlar")
    builder.button(text="💵 Kassa")
    
    # Row 3: Products & CRM
    builder.button(text="📦 Mahsulotlar")
    builder.button(text="👥 Mijozlar")
    
    # Row 4: Reports & Debts
    builder.button(text="📊 Hisobot")
    builder.button(text="👤 Qarzdorlik")
    
    # Row 5: Analytics & Settings
    builder.button(text="📈 Tahlil")
    builder.button(text="⚙️ Sozlamalar")
    
    # Admin button
    if is_admin:
        builder.button(text="🔐 Admin Panel")
    
    if is_admin:
        builder.adjust(2, 2, 2, 2, 2, 1)
    else:
        builder.adjust(2, 2, 2, 2, 2)
    
    return builder.as_markup(
        resize_keyboard=True,
        input_field_placeholder="Menyu bo'limini tanlang yoki + / - bilan tezkor yozing",
    )


# Main menu button texts (for message handler filtering)
MAIN_MENU_BUTTONS = {
    "💰 Daromad",
    "💸 Xarajat",
    "🛒 Sotuvlar",
    "💵 Kassa",
    "📦 Mahsulotlar",
    "👥 Mijozlar",
    "📊 Hisobot",
    "👤 Qarzdorlik",
    "📈 Tahlil",
    "⚙️ Sozlamalar",
    "🔐 Admin Panel",
}
