"""Quick entry handler - parses +/-amount description."""
from decimal import Decimal
from datetime import datetime

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.common_kb import get_confirm_inline
from app.bot.keyboards.main_menu import get_main_menu
from app.config.constants import PaymentMethod, TransactionType
from app.database.models.user import User
from app.services.finance_service import FinanceService
from app.utils.formatters import format_money
from app.utils.quick_parser import is_quick_entry, parse_quick_entry

router = Router()


@router.message(F.func(lambda m: m.text and is_quick_entry(m.text)))
async def quick_entry_handler(message: Message, state: FSMContext, user: User):
    """Handle quick entry like '+250000 savdo' or '-80000 reklama'."""
    # Don't intercept if user is in an active FSM state
    current_state = await state.get_state()
    if current_state:
        return

    entry = parse_quick_entry(message.text)
    if not entry:
        return

    type_emoji = "💰" if entry.type == TransactionType.INCOME else "💸"
    type_label = "Daromad (Kirim)" if entry.type == TransactionType.INCOME else "Xarajat (Chiqim)"
    desc = entry.description or "—"

    # Store in state for confirmation
    await state.update_data(
        quick_amount=str(entry.amount),
        quick_type=entry.type.value,
        quick_description=entry.description,
    )

    await message.answer(
        f"⚡️ <b>Tezkor yozuv aniqlandi:</b>\n\n"
        f"Turi: <b>{type_emoji} {type_label}</b>\n"
        f"Summa: <b>{format_money(entry.amount)}</b>\n"
        f"Izoh: <i>{desc}</i>\n"
        f"To'lov turi: <b>💵 Naqd</b>\n\n"
        f"Ushbu operatsiyani saqlaysizmi?",
        reply_markup=get_confirm_inline("quick_entry"),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("quick_entry:"))
async def quick_entry_confirm(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    user: User,
):
    """Save or cancel quick entry."""
    parts = callback.data.split(":")
    action = parts[1] if len(parts) > 1 else ""

    if action == "cancel":
        await state.clear()
        await callback.answer("❌ Bekor qilindi")
        try:
            await callback.message.delete()
        except Exception:
            pass
        return

    data = await state.get_data()
    if not data.get("quick_amount"):
        await callback.answer("❌ Ma'lumot topilmadi", show_alert=True)
        await state.clear()
        return

    try:
        finance_svc = FinanceService(session)
        amount = Decimal(data["quick_amount"])
        tx_type_str = data["quick_type"]
        description = data.get("quick_description")
        dt = datetime.now()

        if tx_type_str == TransactionType.INCOME.value:
            tx = await finance_svc.record_income(
                user_id=user.id,
                amount=amount,
                payment_method=PaymentMethod.CASH,
                description=description,
                transaction_date=dt,
            )
            type_emoji = "💰"
            type_text = "Daromad"
            sign = "+"
        else:
            tx = await finance_svc.record_expense(
                user_id=user.id,
                amount=amount,
                payment_method=PaymentMethod.CASH,
                description=description,
                transaction_date=dt,
            )
            type_emoji = "💸"
            type_text = "Xarajat"
            sign = "-"

        await state.clear()
        await callback.answer("✅ Saqlandi!")
        try:
            await callback.message.delete()
        except Exception:
            pass

        await callback.message.answer(
            f"✅ <b>{type_text} saqlandi!</b>\n\n"
            f"{type_emoji} Summa: <b>{sign}{format_money(amount)}</b>\n"
            f"🆔 ID: <code>#{tx.id}</code>",
            reply_markup=get_main_menu(is_admin=user.is_admin),
            parse_mode="HTML",
        )
        logger.info(
            f"Quick entry saved: user={user.id} amount={amount} type={tx_type_str} id={tx.id}"
        )

    except Exception as e:
        logger.error(f"Quick entry error for user {user.id}: {e}")
        await callback.answer("❌ Xatolik yuz berdi", show_alert=True)
        await state.clear()
