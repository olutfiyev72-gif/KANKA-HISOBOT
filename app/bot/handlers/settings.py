"""Settings handler."""
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.user import User
from app.database.repositories.user_repo import UserRepository
from app.utils.formatters import format_datetime

router = Router()

TIMEZONES = [
    ("🇺🇿 Toshkent", "Asia/Tashkent"),
    ("🇷🇺 Moskva", "Europe/Moscow"),
    ("🇰🇿 Almaty", "Asia/Almaty"),
    ("🌐 UTC", "UTC"),
]


def get_settings_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🕐 Vaqt zonasi", callback_data="settings:timezone")
    builder.button(text="👤 Ma'lumotlarim", callback_data="settings:profile")
    builder.button(text="🔙 Yopish", callback_data="settings:close")
    builder.adjust(2, 1)
    return builder.as_markup()


def get_timezone_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for label, tz in TIMEZONES:
        builder.button(text=label, callback_data=f"tz:{tz}")
    builder.button(text="🔙 Orqaga", callback_data="settings:back")
    builder.adjust(2, 2, 1)
    return builder.as_markup()


@router.message(F.text == "⚙️ Sozlamalar")
async def settings_start(message: Message, user: User):
    """Show settings menu."""
    from datetime import datetime
    import pytz
    tz = pytz.timezone(user.timezone)
    now = datetime.now(tz).strftime("%H:%M")
    
    await message.answer(
        f"⚙️ <b>Sozlamalar</b>\n\n"
        f"👤 Ism: <b>{user.full_name}</b>\n"
        f"🆔 ID: <code>{user.telegram_id}</code>\n"
        f"🕐 Vaqt zonasi: <b>{user.timezone}</b>\n"
        f"🕐 Hozirgi vaqt: <b>{now}</b>",
        reply_markup=get_settings_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "settings:timezone")
async def settings_timezone(callback: CallbackQuery, user: User):
    """Show timezone selection."""
    await callback.answer()
    await callback.message.edit_text(
        "🕐 <b>Vaqt zonasini tanlang:</b>",
        reply_markup=get_timezone_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("tz:"))
async def settings_set_timezone(
    callback: CallbackQuery, session: AsyncSession, user: User
):
    """Set timezone."""
    tz = callback.data.split(":", 1)[1]
    user_repo = UserRepository(session)
    await user_repo.update_timezone(user, tz)
    await callback.answer(f"✅ Vaqt zonasi o'zgartirildi: {tz}")
    await callback.message.edit_text(
        f"✅ Vaqt zonasi o'zgartirildi!\n\n🕐 <b>{tz}</b>",
        parse_mode="HTML",
    )


@router.callback_query(F.data == "settings:profile")
async def settings_profile(callback: CallbackQuery, user: User):
    """Show user profile."""
    await callback.answer()
    status_emoji = {"active": "✅", "pending": "⏳", "blocked": "❌"}.get(
        user.status.value, "❓"
    )
    await callback.message.answer(
        f"👤 <b>Profilim</b>\n\n"
        f"Ism: <b>{user.full_name}</b>\n"
        f"Username: @{user.username or '—'}\n"
        f"Telegram ID: <code>{user.telegram_id}</code>\n"
        f"Status: {status_emoji} {user.status.value}\n"
        f"Vaqt zonasi: <b>{user.timezone}</b>\n"
        f"Admin: {'✅' if user.is_admin else '❌'}\n"
        f"Ro'yxatdan o'tgan: <b>{user.created_at.strftime('%d.%m.%Y')}</b>",
        parse_mode="HTML",
    )


@router.callback_query(F.data.in_(["settings:close", "settings:back"]))
async def settings_close(callback: CallbackQuery, user: User):
    await callback.answer()
    try:
        await callback.message.delete()
    except Exception:
        pass
