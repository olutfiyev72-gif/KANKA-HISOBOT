"""Expense entry handler with FSM wizard."""
from datetime import datetime
from decimal import Decimal

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.common_kb import (
    get_cancel_keyboard,
    get_confirm_inline,
    get_skip_keyboard,
)
from app.bot.keyboards.income_kb import (
    get_expense_category_keyboard,
    get_payment_method_keyboard,
)
from app.bot.keyboards.main_menu import get_main_menu
from app.bot.states.expense_states import ExpenseStates
from app.config.constants import PaymentMethod
from app.database.models.category import CategoryType
from app.database.models.user import User
from app.database.repositories.category_repo import CategoryRepository
from app.services.finance_service import FinanceService
from app.utils.formatters import format_date_short, format_money
from app.utils.validators import validate_amount

router = Router()

PAYMENT_METHOD_LABELS = {
    "cash": "💵 Naqd",
    "card": "💳 Karta",
    "bank": "🏦 Bank",
    "other": "🔄 Boshqa",
}


@router.message(F.text == "💸 Xarajat")
async def expense_start(message: Message, state: FSMContext, user: User):
    """Start expense entry flow."""
    await state.clear()
    await state.set_state(ExpenseStates.waiting_amount)
    await message.answer(
        "💸 <b>Xarajat kiritish</b>\n\n"
        "Summani kiriting (so'mda):\n"
        "<i>Masalan: 80000 yoki 80 000</i>",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML",
    )


@router.message(ExpenseStates.waiting_amount)
async def expense_amount(
    message: Message, state: FSMContext, session: AsyncSession, user: User
):
    """Process amount input and ask for category."""
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer(
            "❌ Amal bekor qilindi.",
            reply_markup=get_main_menu(is_admin=user.is_admin),
        )
        return

    is_valid, amount, error = validate_amount(message.text)
    if not is_valid:
        await message.answer(error)
        return

    await state.update_data(amount=str(amount))

    # Load expense categories
    cat_repo = CategoryRepository(session)
    categories = await cat_repo.get_categories(user.id, CategoryType.EXPENSE)

    await state.set_state(ExpenseStates.waiting_category)
    await message.answer(
        f"💸 Summa: <b>{format_money(amount)}</b>\n\n"
        "📁 Xarajat kategoriyasini tanlang:",
        reply_markup=get_expense_category_keyboard(categories),
        parse_mode="HTML",
    )


@router.callback_query(
    ExpenseStates.waiting_category, F.data.startswith("expense_cat:")
)
async def expense_category(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, user: User
):
    """Process category selection."""
    action = callback.data.split(":")[1]

    if action == "cancel":
        await state.clear()
        await callback.message.answer(
            "❌ Bekor qilindi.", reply_markup=get_main_menu(is_admin=user.is_admin)
        )
        await callback.answer()
        try:
            await callback.message.delete()
        except Exception:
            pass
        return

    if action == "new":
        await state.set_state(ExpenseStates.waiting_new_category)
        await callback.message.answer(
            "✏️ Yangi xarajat kategoriyasi nomini kiriting:",
            reply_markup=get_cancel_keyboard(),
        )
        await callback.answer()
        return

    category_id = int(action)
    cat_repo = CategoryRepository(session)
    category = await cat_repo.get_by_id(category_id)
    cat_name = f"{category.icon} {category.name}" if category else "Xarajat"

    await state.update_data(category_id=category_id, category_name=cat_name)
    await callback.answer()
    await _ask_payment_method(callback.message, state)


@router.message(ExpenseStates.waiting_new_category)
async def expense_new_category(
    message: Message, state: FSMContext, session: AsyncSession, user: User
):
    """Save new category and continue."""
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer(
            "❌ Amal bekor qilindi.",
            reply_markup=get_main_menu(is_admin=user.is_admin),
        )
        return

    name = message.text.strip()
    if len(name) < 2 or len(name) > 100:
        await message.answer("❌ Kategoriya nomi 2-100 ta belgi bo'lishi kerak")
        return

    cat_repo = CategoryRepository(session)
    new_cat = await cat_repo.create_custom_category(
        user_id=user.id,
        name=name,
        category_type=CategoryType.EXPENSE,
        icon="📁",
    )
    await state.update_data(
        category_id=new_cat.id, category_name=f"{new_cat.icon} {new_cat.name}"
    )
    await _ask_payment_method(message, state)


async def _ask_payment_method(message: Message, state: FSMContext):
    """Ask for payment method."""
    await state.set_state(ExpenseStates.waiting_payment_method)
    await message.answer(
        "💳 To'lov turini tanlang:",
        reply_markup=get_payment_method_keyboard(prefix="expense_pm"),
    )


@router.callback_query(
    ExpenseStates.waiting_payment_method, F.data.startswith("expense_pm:")
)
async def expense_payment_method(
    callback: CallbackQuery, state: FSMContext, user: User
):
    """Process payment method selection."""
    method = callback.data.split(":")[1]
    pm_label = PAYMENT_METHOD_LABELS.get(method, "💵 Naqd")
    await state.update_data(payment_method=method, payment_method_label=pm_label)
    await callback.answer()

    await state.set_state(ExpenseStates.waiting_description)
    await callback.message.answer(
        "📝 Izoh kiriting (ixtiyoriy):\n<i>O'tkazib yuborish uchun tugmani bosing</i>",
        reply_markup=get_skip_keyboard(),
        parse_mode="HTML",
    )


@router.message(ExpenseStates.waiting_description)
async def expense_description(
    message: Message, state: FSMContext, user: User
):
    """Process description input and show confirmation."""
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer(
            "❌ Amal bekor qilindi.",
            reply_markup=get_main_menu(is_admin=user.is_admin),
        )
        return

    text = message.text.strip()
    if text == "⏩ O'tkazib yuborish":
        description = None
    else:
        description = text[:500]

    await state.update_data(
        description=description,
        transaction_date=datetime.now().isoformat(),
    )

    data = await state.get_data()
    await _show_expense_confirmation(message, state, data, user)


async def _show_expense_confirmation(
    message: Message, state: FSMContext, data: dict, user: User
):
    """Show confirmation before saving."""
    amount = Decimal(data["amount"])
    pm = data.get("payment_method_label") or PAYMENT_METHOD_LABELS.get(
        data.get("payment_method", "cash"), "💵 Naqd"
    )
    cat_name = data.get("category_name", "Xarajat")
    description = data.get("description") or "—"
    date_display = format_date_short(datetime.now(), user.timezone)

    await state.set_state(ExpenseStates.confirming)
    await message.answer(
        "📋 <b>Xarajatni tasdiqlang:</b>\n\n"
        f"💸 Summa: <b>{format_money(amount)}</b>\n"
        f"📁 Kategoriya: <b>{cat_name}</b>\n"
        f"💳 To'lov: <b>{pm}</b>\n"
        f"📝 Izoh: <i>{description}</i>\n"
        f"📅 Sana: <b>{date_display}</b>",
        reply_markup=get_confirm_inline("expense_confirm"),
        parse_mode="HTML",
    )


@router.callback_query(
    ExpenseStates.confirming, F.data.startswith("expense_confirm:")
)
async def expense_confirm(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    user: User,
):
    """Save or cancel expense."""
    parts = callback.data.split(":")
    action = parts[1] if len(parts) > 1 else ""

    if action == "cancel":
        await state.clear()
        await callback.message.answer(
            "❌ Bekor qilindi.", reply_markup=get_main_menu(is_admin=user.is_admin)
        )
        await callback.answer("Bekor qilindi")
        try:
            await callback.message.delete()
        except Exception:
            pass
        return

    data = await state.get_data()
    try:
        finance_svc = FinanceService(session)
        amount = Decimal(data["amount"])
        pm_str = data.get("payment_method", "cash")
        pm_enum = PaymentMethod(pm_str) if pm_str in PaymentMethod._value2member_map_ else PaymentMethod.CASH
        category_id = data.get("category_id")
        description = data.get("description")
        dt = datetime.now()

        tx = await finance_svc.record_expense(
            user_id=user.id,
            amount=amount,
            category_id=category_id,
            payment_method=pm_enum,
            description=description,
            transaction_date=dt,
        )

        await state.clear()
        await callback.answer("✅ Saqlandi!")
        try:
            await callback.message.delete()
        except Exception:
            pass

        await callback.message.answer(
            f"✅ <b>Xarajat muvaffaqiyatli saqlandi!</b>\n\n"
            f"💸 Summa: <b>-{format_money(amount)}</b>\n"
            f"💳 To'lov: <b>{PAYMENT_METHOD_LABELS.get(pm_str, '💵 Naqd')}</b>\n"
            f"🆔 Tranzaksiya ID: <code>#{tx.id}</code>",
            reply_markup=get_main_menu(is_admin=user.is_admin),
            parse_mode="HTML",
        )
        logger.info(f"Expense saved: user={user.id} amount={amount} id={tx.id}")

    except Exception as e:
        logger.error(f"Failed to save expense for user {user.id}: {e}")
        await callback.answer("❌ Xatolik yuz berdi", show_alert=True)
        await state.clear()
        await callback.message.answer(
            "❌ Saqlashda xatolik yuz berdi. Iltimos qayta urinib ko'ring.",
            reply_markup=get_main_menu(is_admin=user.is_admin),
        )
