"""Debts handler - receivables and payables management."""
from datetime import datetime
from decimal import Decimal

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.common_kb import (
    get_cancel_keyboard, get_confirm_inline, get_skip_keyboard,
    get_today_keyboard,
)
from app.bot.keyboards.debts_kb import (
    get_debt_actions_keyboard, get_debt_list_keyboard,
    get_debt_menu_keyboard, get_debt_type_keyboard,
)
from app.bot.keyboards.main_menu import get_main_menu
from app.bot.states.debt_states import DebtAddStates, DebtPaymentStates
from app.database.models.debt import DebtStatus, DebtType
from app.database.models.user import User
from app.database.repositories.debt_repo import DebtRepository
from app.utils.formatters import format_date_short, format_money, parse_date_input
from app.utils.validators import validate_amount, validate_phone, validate_text

router = Router()

DEBT_TYPE_LABELS = {
    DebtType.RECEIVABLE: "💚 Menga berishi kerak",
    DebtType.PAYABLE: "❤️ Men berishi kerakman",
}

STATUS_EMOJI = {
    DebtStatus.ACTIVE: "🟡",
    DebtStatus.PAID: "🟢",
    DebtStatus.OVERDUE: "🔴",
    DebtStatus.PARTIAL: "🟠",
}


@router.message(F.text == "👤 Qarzdorlik")
async def debts_start(message: Message, state: FSMContext, user: User):
    """Show debt menu."""
    await state.clear()
    await message.answer(
        "👤 <b>Qarzdorlik</b>\n\nQaysi bo'limni ko'rmoqchisiz?",
        reply_markup=get_debt_menu_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "debts:menu")
async def debts_menu(callback: CallbackQuery, state: FSMContext, user: User):
    """Return to debt menu."""
    await callback.answer()
    await callback.message.answer(
        "👤 <b>Qarzdorlik</b>\n\nQaysi bo'limni ko'rmoqchisiz?",
        reply_markup=get_debt_menu_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "debts:summary")
async def debts_summary(callback: CallbackQuery, session: AsyncSession, user: User):
    """Show debt summary."""
    await callback.answer()
    debt_repo = DebtRepository(session)
    # Update overdue statuses first
    await debt_repo.update_overdue_statuses(user.id)
    summary = await debt_repo.get_summary(user.id)

    text = (
        "👤 <b>QARZDORLIK XULOSASI</b>\n"
        f"{'─' * 28}\n\n"
        f"💚 <b>Menga berishlari kerak:</b>\n"
        f"   Jami: {format_money(summary['receivable_total'])}\n"
        f"   Qoldiq: {format_money(summary['receivable_remaining'])}\n"
        f"   Soni: {summary['receivable_count']} ta\n\n"
        f"❤️ <b>Men berishim kerak:</b>\n"
        f"   Jami: {format_money(summary['payable_total'])}\n"
        f"   Qoldiq: {format_money(summary['payable_remaining'])}\n"
        f"   Soni: {summary['payable_count']} ta\n\n"
        f"{'─' * 28}\n"
        f"📊 Sof pozitsiya: "
    )
    net = summary["receivable_remaining"] - summary["payable_remaining"]
    if net > 0:
        text += f"<b>+{format_money(net)}</b> (sizga qarzdorlar)"
    elif net < 0:
        text += f"<b>{format_money(net)}</b> (siz qarzdorsiz)"
    else:
        text += "<b>Nol</b>"

    await callback.message.answer(text, parse_mode="HTML")


@router.callback_query(F.data.in_(["debts:receivable", "debts:payable"]))
async def debts_list(callback: CallbackQuery, session: AsyncSession, user: User):
    """Show debt list by type."""
    debt_type = DebtType.RECEIVABLE if callback.data == "debts:receivable" else DebtType.PAYABLE
    await callback.answer()

    debt_repo = DebtRepository(session)
    await debt_repo.update_overdue_statuses(user.id)
    debts = await debt_repo.get_user_debts(user.id, debt_type=debt_type)

    type_label = "Menga berishlari kerak" if debt_type == DebtType.RECEIVABLE else "Men berishim kerak"

    if not debts:
        await callback.message.answer(
            f"👤 <b>{type_label}</b>\n\n"
            "Hech qanday qarz topilmadi.",
            parse_mode="HTML",
        )
        return

    text = f"👤 <b>{type_label}:</b>\n\n"
    for debt in debts:
        emoji = STATUS_EMOJI.get(debt.status, "⚪")
        remaining = debt.amount - debt.paid_amount
        date_str = format_date_short(debt.created_date, user.timezone)
        text += (
            f"{emoji} <b>{debt.contact_name}</b>\n"
            f"   💰 {format_money(remaining)} qoldi\n"
            f"   📅 {date_str}\n\n"
        )

    await callback.message.answer(
        text,
        reply_markup=get_debt_list_keyboard(debts),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("debt_view:"))
async def debt_view(callback: CallbackQuery, session: AsyncSession, user: User):
    """View single debt details."""
    debt_id = int(callback.data.split(":")[1])
    await callback.answer()

    debt_repo = DebtRepository(session)
    debt = await debt_repo.get_by_id_and_user(debt_id, user.id)
    if not debt:
        await callback.message.answer("❌ Qarz topilmadi.")
        return

    remaining = debt.amount - debt.paid_amount
    emoji = STATUS_EMOJI.get(debt.status, "⚪")
    type_label = DEBT_TYPE_LABELS.get(debt.type, "")
    date_str = format_date_short(debt.created_date, user.timezone)
    due_str = format_date_short(debt.due_date, user.timezone) if debt.due_date else "—"

    text = (
        f"👤 <b>{debt.contact_name}</b>\n"
        f"{'─' * 28}\n\n"
        f"Tur: {type_label}\n"
        f"Status: {emoji} {debt.status.value.capitalize()}\n"
        f"📞 Tel: {debt.contact_phone or '—'}\n\n"
        f"💰 Jami summa: <b>{format_money(debt.amount)}</b>\n"
        f"✅ To'langan: <b>{format_money(debt.paid_amount)}</b>\n"
        f"⏳ Qoldi: <b>{format_money(remaining)}</b>\n\n"
        f"📅 Sana: {date_str}\n"
        f"⏰ Muddat: {due_str}\n"
        f"📝 Izoh: {debt.description or '—'}"
    )

    await callback.message.answer(
        text,
        reply_markup=get_debt_actions_keyboard(debt.id, debt.status),
        parse_mode="HTML",
    )


# ============ ADD DEBT ============
@router.callback_query(F.data == "debts:add")
async def debt_add_start(callback: CallbackQuery, state: FSMContext, user: User):
    """Start adding a new debt."""
    await callback.answer()
    await state.set_state(DebtAddStates.waiting_type)
    await callback.message.answer(
        "➕ <b>Yangi qarz kiritish</b>\n\nQarz turi:",
        reply_markup=get_debt_type_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(DebtAddStates.waiting_type, F.data.startswith("debt_type:"))
async def debt_add_type(callback: CallbackQuery, state: FSMContext, user: User):
    debt_type_str = callback.data.split(":")[1]
    if debt_type_str == "cancel":
        await state.clear()
        await callback.answer()
        return
    await state.update_data(debt_type=debt_type_str)
    await state.set_state(DebtAddStates.waiting_contact_name)
    await callback.answer()
    await callback.message.answer(
        "👤 Ismi va familiyasini kiriting:", reply_markup=get_cancel_keyboard()
    )


@router.message(DebtAddStates.waiting_contact_name)
async def debt_add_name(message: Message, state: FSMContext, user: User):
    is_valid, error = validate_text(message.text, max_length=255)
    if not is_valid:
        await message.answer(error)
        return
    await state.update_data(contact_name=message.text.strip())
    await state.set_state(DebtAddStates.waiting_phone)
    await message.answer(
        "📞 Telefon raqami (ixtiyoriy):", reply_markup=get_skip_keyboard()
    )


@router.message(DebtAddStates.waiting_phone)
async def debt_add_phone(message: Message, state: FSMContext, user: User):
    text = message.text.strip()
    if text == "⏩ O'tkazib yuborish":
        await state.update_data(phone=None)
    else:
        is_valid, phone, error = validate_phone(text)
        if not is_valid:
            await message.answer(error)
            return
        await state.update_data(phone=phone)

    await state.set_state(DebtAddStates.waiting_amount)
    await message.answer("💰 Summani kiriting:", reply_markup=get_cancel_keyboard())


@router.message(DebtAddStates.waiting_amount)
async def debt_add_amount(message: Message, state: FSMContext, user: User):
    is_valid, amount, error = validate_amount(message.text)
    if not is_valid:
        await message.answer(error)
        return
    await state.update_data(amount=str(amount))
    await state.set_state(DebtAddStates.waiting_description)
    await message.answer("📝 Izoh (ixtiyoriy):", reply_markup=get_skip_keyboard())


@router.message(DebtAddStates.waiting_description)
async def debt_add_desc(message: Message, state: FSMContext, user: User):
    text = message.text.strip()
    await state.update_data(
        description=None if text == "⏩ O'tkazib yuborish" else text[:500]
    )
    await state.set_state(DebtAddStates.waiting_due_date)
    await message.answer(
        "⏰ To'lov muddati (ixtiyoriy):\n<i>Masalan: 15.09.2024</i>",
        reply_markup=get_skip_keyboard(),
        parse_mode="HTML",
    )


@router.message(DebtAddStates.waiting_due_date)
async def debt_add_due_date(message: Message, state: FSMContext, user: User):
    text = message.text.strip()
    if text == "⏩ O'tkazib yuborish":
        await state.update_data(due_date=None)
    else:
        date = parse_date_input(text, user.timezone)
        if not date:
            await message.answer("❌ Noto'g'ri sana. Masalan: <code>15.09.2024</code>", parse_mode="HTML")
            return
        await state.update_data(due_date=date.isoformat())

    await state.set_state(DebtAddStates.confirming)
    data = await state.get_data()
    amount = Decimal(data["amount"])
    debt_type = DebtType(data["debt_type"])
    type_label = DEBT_TYPE_LABELS.get(debt_type, "")
    due_str = "—"
    if data.get("due_date"):
        try:
            due_str = format_date_short(datetime.fromisoformat(data["due_date"]), user.timezone)
        except Exception:
            pass

    await message.answer(
        "✅ <b>Qarzni tasdiqlang:</b>\n\n"
        f"Tur: {type_label}\n"
        f"👤 Ism: <b>{data['contact_name']}</b>\n"
        f"📞 Tel: <b>{data.get('phone') or '—'}</b>\n"
        f"💰 Summa: <b>{format_money(amount)}</b>\n"
        f"📝 Izoh: <b>{data.get('description') or '—'}</b>\n"
        f"⏰ Muddat: <b>{due_str}</b>",
        reply_markup=get_confirm_inline("debt_add_confirm"),
        parse_mode="HTML",
    )


@router.callback_query(DebtAddStates.confirming, F.data.startswith("debt_add_confirm:"))
async def debt_add_confirm(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, user: User
):
    action = callback.data.split(":")[1]
    if action == "cancel":
        await state.clear()
        await callback.message.answer("❌ Bekor qilindi.", reply_markup=get_main_menu(is_admin=user.is_admin))
        await callback.answer()
        return

    data = await state.get_data()
    try:
        debt_repo = DebtRepository(session)
        due_date = None
        if data.get("due_date"):
            due_date = datetime.fromisoformat(data["due_date"])

        debt = await debt_repo.create(
            user_id=user.id,
            type=DebtType(data["debt_type"]),
            contact_name=data["contact_name"],
            contact_phone=data.get("phone"),
            amount=Decimal(data["amount"]),
            description=data.get("description"),
            created_date=datetime.now(),
            due_date=due_date,
        )
        await state.clear()
        await callback.answer("✅ Saqlandi!")
        await callback.message.answer(
            f"✅ Qarz saqlandi!\n👤 {debt.contact_name}\n💰 {format_money(debt.amount)}",
            reply_markup=get_main_menu(is_admin=user.is_admin),
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"Debt add error for user {user.id}: {e}")
        await callback.answer("❌ Xatolik", show_alert=True)
        await state.clear()


# ============ DEBT PAYMENT ============
@router.callback_query(F.data.startswith("debt_pay:"))
async def debt_pay_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession, user: User):
    """Start recording a debt payment."""
    debt_id = int(callback.data.split(":")[1])
    await callback.answer()

    debt_repo = DebtRepository(session)
    debt = await debt_repo.get_by_id_and_user(debt_id, user.id)
    if not debt:
        await callback.message.answer("❌ Qarz topilmadi.")
        return

    remaining = debt.amount - debt.paid_amount
    await state.update_data(debt_id=debt_id)
    await state.set_state(DebtPaymentStates.waiting_amount)
    await callback.message.answer(
        f"💰 To'lov kiritish\n\n"
        f"👤 {debt.contact_name}\n"
        f"⏳ Qoldiq: <b>{format_money(remaining)}</b>\n\n"
        "To'lov summasini kiriting:",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML",
    )


@router.message(DebtPaymentStates.waiting_amount)
async def debt_pay_amount(message: Message, state: FSMContext, user: User):
    is_valid, amount, error = validate_amount(message.text)
    if not is_valid:
        await message.answer(error)
        return
    await state.update_data(pay_amount=str(amount))
    await state.set_state(DebtPaymentStates.confirming)
    await message.answer(
        f"✅ <b>To'lovni tasdiqlang:</b>\n💰 {format_money(amount)}",
        reply_markup=get_confirm_inline("debt_pay_confirm"),
        parse_mode="HTML",
    )


@router.callback_query(DebtPaymentStates.confirming, F.data.startswith("debt_pay_confirm:"))
async def debt_pay_confirm(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, user: User
):
    action = callback.data.split(":")[1]
    if action == "cancel":
        await state.clear()
        await callback.message.answer("❌ Bekor qilindi.", reply_markup=get_main_menu(is_admin=user.is_admin))
        await callback.answer()
        return

    data = await state.get_data()
    try:
        debt_repo = DebtRepository(session)
        debt = await debt_repo.get_by_id_and_user(data["debt_id"], user.id)
        amount = Decimal(data["pay_amount"])

        await debt_repo.add_payment(
            debt=debt,
            amount=amount,
            payment_date=datetime.now(),
        )

        await state.clear()
        await callback.answer("✅ Saqlandi!")
        remaining = debt.remaining_amount
        status_text = "✅ To'liq to'landi!" if debt.status.value == "paid" else f"⏳ Qoldi: {format_money(remaining)}"
        await callback.message.answer(
            f"💰 To'lov saqlandi: {format_money(amount)}\n{status_text}",
            reply_markup=get_main_menu(is_admin=user.is_admin),
            parse_mode="HTML",
        )
    except ValueError as e:
        await callback.answer(str(e), show_alert=True)
    except Exception as e:
        logger.error(f"Debt payment error for user {user.id}: {e}")
        await callback.answer("❌ Xatolik", show_alert=True)
        await state.clear()


@router.callback_query(F.data.startswith("debt_delete:"))
async def debt_delete(callback: CallbackQuery, session: AsyncSession, user: User):
    """Delete a debt."""
    debt_id = int(callback.data.split(":")[1])
    debt_repo = DebtRepository(session)
    deleted = await debt_repo.soft_delete(debt_id, user.id)
    if deleted:
        await callback.answer("🗑 O'chirildi!")
        await callback.message.answer("🗑 Qarz o'chirildi.")
    else:
        await callback.answer("❌ Topilmadi", show_alert=True)
