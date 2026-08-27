"""Cash balance handler."""
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.common_kb import get_cancel_keyboard
from app.bot.states.income_states import IncomeStates
from app.bot.states.expense_states import ExpenseStates
from app.database.models.user import User
from app.services.finance_service import FinanceService
from app.utils.formatters import format_date_short, format_money, format_profit_indicator

router = Router()


def get_cash_keyboard() -> InlineKeyboardMarkup:
    """Cash dashboard inline keyboard."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 Yangilash", callback_data="cash:refresh")
    builder.button(text="📋 So'nggi amallar", callback_data="cash:history")
    builder.button(text="💰 Daromad", callback_data="cash:add_income")
    builder.button(text="💸 Xarajat", callback_data="cash:add_expense")
    builder.adjust(2, 2)
    return builder.as_markup()


@router.message(F.text == "💵 Kassa")
async def cash_start(message: Message, session: AsyncSession, user: User):
    """Show cash balance."""
    await show_cash(message, session, user)


async def show_cash(message: Message, session: AsyncSession, user: User):
    """Generate and display cash balance."""
    try:
        finance_svc = FinanceService(session)
        summary = await finance_svc.get_balance_summary(user.id)

        balance = summary.total_balance
        profit_emoji = format_profit_indicator(balance)

        text = (
            f"💵 <b>KASSA VA BALANS</b>\n"
            f"{'─' * 28}\n\n"
            f"{profit_emoji} <b>Umumiy balans:</b> <code>{format_money(balance)}</code>\n\n"
            f"<b>💳 To'lov turlari bo'yicha qoldiq:</b>\n"
            f"💵 Naqd pul:  <b>{format_money(summary.cash_balance)}</b>\n"
            f"💳 Plastik karta: <b>{format_money(summary.card_balance)}</b>\n"
            f"🏦 Bank hisobi:  <b>{format_money(summary.bank_balance)}</b>\n"
            f"🔄 Boshqa: <b>{format_money(summary.other_balance)}</b>\n\n"
            f"{'─' * 28}\n"
            f"📈 Jami daromad: <b>+{format_money(summary.total_income)}</b>\n"
            f"📉 Jami xarajat: <b>-{format_money(summary.total_expense)}</b>"
        )

        await message.answer(
            text,
            reply_markup=get_cash_keyboard(),
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"Cash display error for user {user.id}: {e}")
        await message.answer("❌ Kassani yuklashda xatolik yuz berdi.")


@router.callback_query(F.data == "cash:refresh")
async def cash_refresh(callback: CallbackQuery, session: AsyncSession, user: User):
    """Refresh cash balance."""
    await callback.answer("🔄 Yangilanmoqda...")
    finance_svc = FinanceService(session)
    summary = await finance_svc.get_balance_summary(user.id)

    balance = summary.total_balance
    profit_emoji = format_profit_indicator(balance)

    text = (
        f"💵 <b>KASSA VA BALANS</b>\n"
        f"{'─' * 28}\n\n"
        f"{profit_emoji} <b>Umumiy balans:</b> <code>{format_money(balance)}</code>\n\n"
        f"<b>💳 To'lov turlari bo'yicha qoldiq:</b>\n"
        f"💵 Naqd pul:  <b>{format_money(summary.cash_balance)}</b>\n"
        f"💳 Plastik karta: <b>{format_money(summary.card_balance)}</b>\n"
        f"🏦 Bank hisobi:  <b>{format_money(summary.bank_balance)}</b>\n"
        f"🔄 Boshqa: <b>{format_money(summary.other_balance)}</b>\n\n"
        f"{'─' * 28}\n"
        f"📈 Jami daromad: <b>+{format_money(summary.total_income)}</b>\n"
        f"📉 Jami xarajat: <b>-{format_money(summary.total_expense)}</b>"
    )

    try:
        await callback.message.edit_text(
            text,
            reply_markup=get_cash_keyboard(),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.callback_query(F.data == "cash:history")
async def cash_history(callback: CallbackQuery, session: AsyncSession, user: User):
    """Show recent transactions with action buttons."""
    await callback.answer()
    finance_svc = FinanceService(session)
    transactions = await finance_svc.get_recent_transactions(user.id, limit=10)

    if not transactions:
        await callback.message.answer("📋 Hech qanday operatsiya topilmadi.")
        return

    text = "📋 <b>So'nggi operatsiyalar:</b>\n<i>Batafsil ko'rish va boshqarish uchun tanlang:</i>\n\n"
    builder = InlineKeyboardBuilder()

    for tx in transactions:
        emoji = "💰" if tx.type.value == "income" else "💸"
        sign = "+" if tx.type.value == "income" else "-"
        date_str = format_date_short(tx.transaction_date, user.timezone)
        cat_name = tx.category.name if tx.category else "Asosiy"
        text += (
            f"{emoji} <b>{sign}{format_money(tx.amount)}</b> | 📁 {cat_name}\n"
            f"   📅 {date_str} | 🆔 <code>#{tx.id}</code>\n\n"
        )
        builder.button(
            text=f"{emoji} #{tx.id} ({sign}{format_money(tx.amount)})",
            callback_data=f"tx_view:{tx.id}",
        )

    builder.button(text="🔙 Yopish", callback_data="tx_list:back")
    builder.adjust(1)

    await callback.message.answer(
        text,
        reply_markup=builder.as_markup(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "cash:add_income")
async def cash_add_income(callback: CallbackQuery, state: FSMContext, user: User):
    """Trigger income flow from cash menu."""
    await callback.answer()
    await state.clear()
    await state.set_state(IncomeStates.waiting_amount)
    await callback.message.answer(
        "💰 <b>Daromad kiritish</b>\n\n"
        "Summani kiriting (so'mda):\n"
        "<i>Masalan: 250000 yoki 250 000</i>",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "cash:add_expense")
async def cash_add_expense(callback: CallbackQuery, state: FSMContext, user: User):
    """Trigger expense flow from cash menu."""
    await callback.answer()
    await state.clear()
    await state.set_state(ExpenseStates.waiting_amount)
    await callback.message.answer(
        "💸 <b>Xarajat kiritish</b>\n\n"
        "Summani kiriting (so'mda):\n"
        "<i>Masalan: 80000 yoki 80 000</i>",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML",
    )
