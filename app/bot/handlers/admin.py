"""Admin panel handler."""
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.filters.admin_filter import AdminFilter
from app.bot.keyboards.main_menu import get_main_menu
from app.database.models.user import User, UserStatus
from app.database.repositories.transaction_repo import TransactionRepository
from app.database.repositories.user_repo import UserRepository

router = Router()
router.message.filter(AdminFilter())
router.callback_query.filter(AdminFilter())


def get_admin_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="👥 Foydalanuvchilar", callback_data="admin:users")
    builder.button(text="⏳ Kutayotganlar", callback_data="admin:pending")
    builder.button(text="📊 Statistika", callback_data="admin:stats")
    builder.button(text="🔙 Yopish", callback_data="admin:close")
    builder.adjust(2, 1, 1)
    return builder.as_markup()


def get_pending_user_keyboard(user_id: int, telegram_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Tasdiqlash", callback_data=f"admin_approve:{user_id}:{telegram_id}")
    builder.button(text="❌ Rad etish", callback_data=f"admin_reject:{user_id}:{telegram_id}")
    builder.adjust(2)
    return builder.as_markup()


@router.message(F.text == "🔐 Admin Panel")
@router.message(Command("admin"))
async def admin_panel(message: Message, user: User):
    """Show admin panel."""
    await message.answer(
        "🔐 <b>Admin Panel</b>\n\nNimani qilmoqchisiz?",
        reply_markup=get_admin_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "admin:stats")
async def admin_stats(callback: CallbackQuery, session: AsyncSession, user: User):
    """Show bot statistics."""
    await callback.answer()
    user_repo = UserRepository(session)
    tx_repo = TransactionRepository(session)

    user_stats = await user_repo.get_stats()
    tx_count = await tx_repo.count_all()

    text = (
        "📊 <b>Bot Statistikasi</b>\n"
        f"{'─' * 28}\n\n"
        f"👥 Jami foydalanuvchilar: <b>{user_stats['total']}</b>\n"
        f"✅ Faol: <b>{user_stats['active']}</b>\n"
        f"⏳ Kutayotgan: <b>{user_stats['pending']}</b>\n"
        f"📅 7 kunda faol: <b>{user_stats['recent_active']}</b>\n\n"
        f"💳 Jami operatsiyalar: <b>{tx_count}</b>"
    )
    await callback.message.answer(text, parse_mode="HTML")


@router.callback_query(F.data == "admin:pending")
async def admin_pending(callback: CallbackQuery, session: AsyncSession, user: User):
    """Show pending users."""
    await callback.answer()
    user_repo = UserRepository(session)
    pending = await user_repo.get_all_pending()

    if not pending:
        await callback.message.answer("✅ Tasdiqlanmagan foydalanuvchilar yo'q.")
        return

    for pending_user in pending:
        await callback.message.answer(
            f"⏳ <b>Yangi foydalanuvchi</b>\n\n"
            f"👤 Ism: {pending_user.full_name}\n"
            f"🔗 Username: @{pending_user.username or 'yo\'q'}\n"
            f"🆔 Telegram ID: <code>{pending_user.telegram_id}</code>\n"
            f"📅 Ro'yxat: {pending_user.created_at.strftime('%d.%m.%Y %H:%M')}",
            reply_markup=get_pending_user_keyboard(pending_user.id, pending_user.telegram_id),
            parse_mode="HTML",
        )


@router.callback_query(F.data == "admin:users")
async def admin_users(callback: CallbackQuery, session: AsyncSession, user: User):
    """Show active users list."""
    await callback.answer()
    user_repo = UserRepository(session)
    active = await user_repo.get_all_active()

    if not active:
        await callback.message.answer("Faol foydalanuvchilar yo'q.")
        return

    text = f"✅ <b>Faol foydalanuvchilar ({len(active)} ta):</b>\n\n"
    for u in active[:20]:  # Max 20
        text += (
            f"👤 {u.full_name}"
            f" | @{u.username or '—'}"
            f" | <code>{u.telegram_id}</code>\n"
        )
    
    await callback.message.answer(text, parse_mode="HTML")


@router.callback_query(F.data.startswith("admin_approve:"))
async def admin_approve_user(callback: CallbackQuery, session: AsyncSession, user: User):
    """Approve a pending user."""
    parts = callback.data.split(":")
    target_user_id = int(parts[1])
    target_telegram_id = int(parts[2])

    user_repo = UserRepository(session)
    target_user = await user_repo.get_by_id(target_user_id)

    if not target_user:
        await callback.answer("❌ Foydalanuvchi topilmadi", show_alert=True)
        return

    await user_repo.activate_user(target_user)
    await callback.answer("✅ Tasdiqlandi!")
    await callback.message.edit_text(
        f"✅ {target_user.full_name} tasdiqlandi!",
        parse_mode="HTML",
    )

    # Notify user
    try:
        from app.config import settings
        await callback.bot.send_message(
            target_telegram_id,
            "✅ Sizning so'rovingiz tasdiqlandi!\n\n"
            f"🏪 <b>{settings.bot_name}</b> dan foydalanishingiz mumkin.",
            reply_markup=get_main_menu(is_admin=False),
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"Failed to notify approved user {target_telegram_id}: {e}")


@router.callback_query(F.data.startswith("admin_reject:"))
async def admin_reject_user(callback: CallbackQuery, session: AsyncSession, user: User):
    """Reject/block a pending user."""
    parts = callback.data.split(":")
    target_user_id = int(parts[1])
    target_telegram_id = int(parts[2])

    user_repo = UserRepository(session)
    target_user = await user_repo.get_by_id(target_user_id)

    if not target_user:
        await callback.answer("❌ Foydalanuvchi topilmadi", show_alert=True)
        return

    await user_repo.block_user(target_user)
    await callback.answer("❌ Rad etildi!")
    await callback.message.edit_text(f"❌ {target_user.full_name} rad etildi.")

    try:
        await callback.bot.send_message(
            target_telegram_id,
            "❌ Afsuski, so'rovingiz rad etildi.\nQo'shimcha ma'lumot uchun admin bilan bog'laning.",
        )
    except Exception as e:
        logger.error(f"Failed to notify rejected user {target_telegram_id}: {e}")


@router.callback_query(F.data == "admin:close")
async def admin_close(callback: CallbackQuery, user: User):
    await callback.answer()
    try:
        await callback.message.delete()
    except Exception:
        pass
