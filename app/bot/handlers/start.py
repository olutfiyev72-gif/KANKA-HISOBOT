"""Start/Help handler - user registration and main menu."""
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.main_menu import get_main_menu
from app.config import settings
from app.database.models.user import User, UserStatus
from app.database.repositories.user_repo import UserRepository

router = Router()


@router.message(Command("start"))
async def cmd_start(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    user: User,
    is_new_user: bool = False,
):
    """Handle /start command."""
    await state.clear()

    if is_new_user or user.status == UserStatus.PENDING:
        # Notify user
        await message.answer(
            f"👋 Salom, <b>{message.from_user.full_name}</b>!\n\n"
            f"🏪 <b>{settings.bot_name}</b> ga xush kelibsiz!\n\n"
            "⏳ Sizning so'rovingiz admin tomonidan ko'rib chiqilmoqda.\n"
            "Tez orada sizga xabar beriladi.",
            parse_mode="HTML",
        )
        
        # Notify admins about new user
        from aiogram import Bot
        bot: Bot = message.bot
        admin_ids = settings.get_admin_ids()
        for admin_id in admin_ids:
            try:
                await bot.send_message(
                    admin_id,
                    f"🆕 <b>Yangi foydalanuvchi</b>\n\n"
                    f"👤 Ism: {message.from_user.full_name}\n"
                    f"🔗 Username: @{message.from_user.username or 'yo\'q'}\n"
                    f"🆔 Telegram ID: <code>{message.from_user.id}</code>\n\n"
                    f"Tasdiqlash uchun: /admin",
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.error(f"Failed to notify admin {admin_id}: {e}")
        return

    if user.status == UserStatus.BLOCKED:
        await message.answer("❌ Sizning hisobingiz bloklangan.")
        return

    await message.answer(
        f"👋 Salom, <b>{user.full_name}</b>!\n\n"
        f"📊 <b>{settings.bot_name}</b>\n\n"
        "Quyidagi bo'limlardan birini tanlang:",
        reply_markup=get_main_menu(is_admin=user.is_admin),
        parse_mode="HTML",
    )


@router.message(Command("help"))
async def cmd_help(message: Message, user: User):
    """Help command."""
    help_text = """
📖 <b>Bot qo'llanmasi</b>

<b>Asosiy bo'limlar:</b>
💰 <b>Daromad</b> — Daromad kiritish
💸 <b>Xarajat</b> — Xarajat kiritish
📊 <b>Hisobot</b> — Moliyaviy hisobotlar
💵 <b>Kassa</b> — Joriy balans
📦 <b>Mahsulotlar</b> — Mahsulot boshqaruvi
👤 <b>Qarzdorlik</b> — Qarz hisobi
📈 <b>Tahlil</b> — Statistika va tahlil
⚙️ <b>Sozlamalar</b> — Bot sozlamalari

<b>Tezkor yozuv:</b>
<code>+250000 savdo</code> — 250 000 so'm daromad
<code>-80000 reklama</code> — 80 000 so'm xarajat

<b>Buyruqlar:</b>
/start — Asosiy menyu
/help — Yordam
/cancel — Joriy amalni bekor qilish
"""
    await message.answer(help_text, parse_mode="HTML")


@router.message(Command("cancel"))
@router.message(F.text == "❌ Bekor qilish")
async def cmd_cancel(message: Message, state: FSMContext, user: User):
    """Cancel current operation."""
    current_state = await state.get_state()
    if current_state:
        await state.clear()
        await message.answer(
            "❌ Amal bekor qilindi.",
            reply_markup=get_main_menu(is_admin=user.is_admin),
        )
    else:
        await message.answer(
            "📋 Asosiy menyu:",
            reply_markup=get_main_menu(is_admin=user.is_admin),
        )


@router.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext, user: User):
    """Show main menu."""
    await state.clear()
    await message.answer(
        "📋 Asosiy menyu:",
        reply_markup=get_main_menu(is_admin=user.is_admin),
    )
