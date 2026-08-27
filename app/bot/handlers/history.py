"""Transaction history, details, edit and delete handler."""
from decimal import Decimal
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.common_kb import get_cancel_keyboard
from app.bot.keyboards.income_kb import get_payment_method_keyboard
from app.bot.keyboards.main_menu import get_main_menu
from app.bot.states.history_states import TransactionEditStates
from app.config.constants import PaymentMethod
from app.database.models.user import User
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


def get_tx_actions_keyboard(tx_id: int) -> InlineKeyboardMarkup:
    """Action buttons for a single transaction."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ Tahrirlash", callback_data=f"tx_edit:{tx_id}")
    builder.button(text="🗑 O'chirish", callback_data=f"tx_del_prompt:{tx_id}")
    builder.button(text="🔙 Yopish", callback_data="tx_list:back")
    builder.adjust(2, 1)
    return builder.as_markup()


def get_delete_confirm_keyboard(tx_id: int) -> InlineKeyboardMarkup:
    """Delete confirmation inline keyboard."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🗑 Ha, o'chirilsin", callback_data=f"tx_delete:{tx_id}")
    builder.button(text="❌ Bekor qilish", callback_data=f"tx_view:{tx_id}")
    builder.adjust(1)
    return builder.as_markup()


def get_edit_menu_keyboard(tx_id: int) -> InlineKeyboardMarkup:
    """Choose which field to edit."""
    builder = InlineKeyboardBuilder()
    builder.button(text="💰 Summani o'zgartirish", callback_data=f"tx_ed_field:amount:{tx_id}")
    builder.button(text="📝 Izohni o'zgartirish", callback_data=f"tx_ed_field:desc:{tx_id}")
    builder.button(text="💳 To'lov turini o'zgartirish", callback_data=f"tx_ed_field:pm:{tx_id}")
    builder.button(text="🔙 Orqaga", callback_data=f"tx_view:{tx_id}")
    builder.adjust(1)
    return builder.as_markup()


@router.callback_query(F.data == "tx_list:back")
async def tx_list_back(callback: CallbackQuery, state: FSMContext):
    """Close transaction details."""
    await state.clear()
    await callback.answer()
    try:
        await callback.message.delete()
    except Exception:
        pass


@router.callback_query(F.data.startswith("tx_view:"))
async def tx_view(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, user: User
):
    """View transaction details."""
    await state.clear()
    tx_id = int(callback.data.split(":")[1])
    finance_svc = FinanceService(session)
    tx = await finance_svc.get_transaction(tx_id, user.id)

    if not tx:
        await callback.answer("❌ Tranzaksiya topilmadi", show_alert=True)
        return

    type_emoji = "💰" if tx.type.value == "income" else "💸"
    type_name = "Daromad (Kirim)" if tx.type.value == "income" else "Xarajat (Chiqim)"
    sign = "+" if tx.type.value == "income" else "-"
    date_str = format_date_short(tx.transaction_date, user.timezone)
    cat_name = tx.category.name if tx.category else "Kategoriyasiz"
    pm = PAYMENT_METHOD_LABELS.get(tx.payment_method.value, "💵 Naqd")

    text = (
        f"{type_emoji} <b>TRANZAKSIYA #{tx.id}</b>\n"
        f"{'─' * 28}\n\n"
        f"Turi: <b>{type_name}</b>\n"
        f"Summa: <b>{sign}{format_money(tx.amount)}</b>\n"
        f"Kategoriya: <b>{cat_name}</b>\n"
        f"To'lov turi: <b>{pm}</b>\n"
        f"Sana: <b>{date_str}</b>\n"
        f"Izoh: <i>{tx.description or '—'}</i>\n"
    )

    await callback.answer()
    try:
        await callback.message.edit_text(
            text,
            reply_markup=get_tx_actions_keyboard(tx.id),
            parse_mode="HTML",
        )
    except Exception:
        await callback.message.answer(
            text,
            reply_markup=get_tx_actions_keyboard(tx.id),
            parse_mode="HTML",
        )


@router.callback_query(F.data.startswith("tx_del_prompt:"))
async def tx_del_prompt(callback: CallbackQuery):
    """Prompt user to confirm deletion."""
    tx_id = int(callback.data.split(":")[1])
    await callback.answer()
    await callback.message.edit_text(
        f"⚠️ <b>Haqiqatan ham #{tx_id} operatsiyani o'chirmoqchimisiz?</b>\n\n"
        "O'chirilgandan so'ng kassa balansi avtomatik qayta hisoblanadi.",
        reply_markup=get_delete_confirm_keyboard(tx_id),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("tx_delete:"))
async def tx_delete(callback: CallbackQuery, session: AsyncSession, user: User):
    """Soft delete transaction."""
    tx_id = int(callback.data.split(":")[1])
    finance_svc = FinanceService(session)
    deleted = await finance_svc.delete_transaction(tx_id, user.id)

    if deleted:
        await callback.answer("🗑 Muvaffaqiyatli o'chirildi!")
        await callback.message.edit_text(
            f"✅ <b>Tranzaksiya #{tx_id} o'chirildi.</b>\n"
            f"Kassa balansi yangilandi.",
            parse_mode="HTML",
        )
    else:
        await callback.answer("❌ Operatsiya topilmadi", show_alert=True)


# ============ EDIT TRANSACTION FLOW ============
@router.callback_query(F.data.startswith("tx_edit:"))
async def tx_edit_start(callback: CallbackQuery, state: FSMContext):
    """Open edit menu."""
    tx_id = int(callback.data.split(":")[1])
    await state.update_data(edit_tx_id=tx_id)
    await callback.answer()
    await callback.message.edit_text(
        f"✏️ <b>Tranzaksiya #{tx_id} ni tahrirlash:</b>\n\n"
        "Qaysi ma'lumotni o'zgartirmoqchisiz?",
        reply_markup=get_edit_menu_keyboard(tx_id),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("tx_ed_field:"))
async def tx_edit_field_selected(
    callback: CallbackQuery, state: FSMContext, user: User
):
    """Prompt for new value for chosen field."""
    parts = callback.data.split(":")
    field = parts[1]
    tx_id = int(parts[2])
    await state.update_data(edit_tx_id=tx_id, edit_field=field)
    await callback.answer()

    if field == "amount":
        await state.set_state(TransactionEditStates.waiting_amount)
        await callback.message.answer(
            f"💰 <b>Tranzaksiya #{tx_id} uchun yangi summani kiriting:</b>\n"
            "<i>Masalan: 350000</i>",
            reply_markup=get_cancel_keyboard(),
            parse_mode="HTML",
        )
    elif field == "desc":
        await state.set_state(TransactionEditStates.waiting_description)
        await callback.message.answer(
            f"📝 <b>Tranzaksiya #{tx_id} uchun yangi izoh kiriting:</b>",
            reply_markup=get_cancel_keyboard(),
            parse_mode="HTML",
        )
    elif field == "pm":
        await state.set_state(TransactionEditStates.waiting_payment_method)
        await callback.message.answer(
            f"💳 <b>Tranzaksiya #{tx_id} uchun yangi to'lov turini tanlang:</b>",
            reply_markup=get_payment_method_keyboard(prefix="tx_ed_pm"),
            parse_mode="HTML",
        )


@router.message(TransactionEditStates.waiting_amount)
async def tx_edit_save_amount(
    message: Message, state: FSMContext, session: AsyncSession, user: User
):
    """Save updated amount."""
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer(
            "❌ Tahrirlash bekor qilindi.",
            reply_markup=get_main_menu(is_admin=user.is_admin),
        )
        return

    is_valid, amount, error = validate_amount(message.text)
    if not is_valid:
        await message.answer(error)
        return

    data = await state.get_data()
    tx_id = data.get("edit_tx_id")

    finance_svc = FinanceService(session)
    updated = await finance_svc.update_transaction(
        transaction_id=tx_id,
        user_id=user.id,
        amount=amount,
    )

    await state.clear()
    if updated:
        await message.answer(
            f"✅ <b>Tranzaksiya #{tx_id} summasi yangilandi!</b>\n"
            f"💰 Yangi summa: <b>{format_money(amount)}</b>",
            reply_markup=get_main_menu(is_admin=user.is_admin),
            parse_mode="HTML",
        )
    else:
        await message.answer(
            "❌ Yangilashda xatolik yuz berdi.",
            reply_markup=get_main_menu(is_admin=user.is_admin),
        )


@router.message(TransactionEditStates.waiting_description)
async def tx_edit_save_desc(
    message: Message, state: FSMContext, session: AsyncSession, user: User
):
    """Save updated description."""
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer(
            "❌ Tahrirlash bekor qilindi.",
            reply_markup=get_main_menu(is_admin=user.is_admin),
        )
        return

    desc = message.text.strip()[:500]
    data = await state.get_data()
    tx_id = data.get("edit_tx_id")

    finance_svc = FinanceService(session)
    updated = await finance_svc.update_transaction(
        transaction_id=tx_id,
        user_id=user.id,
        description=desc,
    )

    await state.clear()
    if updated:
        await message.answer(
            f"✅ <b>Tranzaksiya #{tx_id} izohi yangilandi!</b>\n"
            f"📝 Yangi izoh: <i>{desc}</i>",
            reply_markup=get_main_menu(is_admin=user.is_admin),
            parse_mode="HTML",
        )
    else:
        await message.answer(
            "❌ Yangilashda xatolik yuz berdi.",
            reply_markup=get_main_menu(is_admin=user.is_admin),
        )


@router.callback_query(
    TransactionEditStates.waiting_payment_method, F.data.startswith("tx_ed_pm:")
)
async def tx_edit_save_pm(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, user: User
):
    """Save updated payment method."""
    method = callback.data.split(":")[1]
    pm_enum = PaymentMethod(method) if method in PaymentMethod._value2member_map_ else PaymentMethod.CASH
    pm_label = PAYMENT_METHOD_LABELS.get(method, "💵 Naqd")

    data = await state.get_data()
    tx_id = data.get("edit_tx_id")

    finance_svc = FinanceService(session)
    updated = await finance_svc.update_transaction(
        transaction_id=tx_id,
        user_id=user.id,
        payment_method=pm_enum,
    )

    await state.clear()
    await callback.answer("✅ Yangilandi!")
    try:
        await callback.message.delete()
    except Exception:
        pass

    if updated:
        await callback.message.answer(
            f"✅ <b>Tranzaksiya #{tx_id} to'lov turi yangilandi!</b>\n"
            f"💳 Yangi to'lov: <b>{pm_label}</b>",
            reply_markup=get_main_menu(is_admin=user.is_admin),
            parse_mode="HTML",
        )
    else:
        await callback.message.answer(
            "❌ Yangilashda xatolik yuz berdi.",
            reply_markup=get_main_menu(is_admin=user.is_admin),
        )
