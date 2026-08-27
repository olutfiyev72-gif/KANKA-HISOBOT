"""Customer CRM handlers - manage customers, sales with debt, and notifications."""
from decimal import Decimal
from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.common_kb import (
    get_cancel_keyboard,
    get_confirm_inline,
    get_skip_keyboard,
)
from app.bot.keyboards.customer_kb import (
    get_customer_detail_keyboard,
    get_customer_edit_keyboard,
    get_customer_list_keyboard,
    get_customer_main_keyboard,
)
from app.bot.keyboards.income_kb import get_payment_method_keyboard
from app.bot.keyboards.main_menu import get_main_menu
from app.bot.states.customer_states import (
    CustomerAddStates,
    CustomerDebtPaymentStates,
    CustomerEditStates,
    CustomerSaleStates,
    CustomerSearchStates,
)
from app.config.constants import PaymentMethod
from app.database.models.user import User
from app.services.customer_service import CustomerService
from app.utils.formatters import format_date_short, format_money
from app.utils.validators import validate_amount, validate_phone, validate_text

router = Router()
router.name = "Mijozlar (CRM)"

PAYMENT_LABELS = {
    "cash": "💵 Naqd",
    "card": "💳 Karta",
    "bank": "🏦 Bank",
    "other": "🔄 Boshqa",
}


# ============ ENTRY POINT ============
@router.message(F.text == "👥 Mijozlar")
@router.message(Command("customers"))
async def customers_entry(message: Message, state: FSMContext, session: AsyncSession, user: User):
    """Show CRM dashboard."""
    await state.clear()
    await show_crm_dashboard(message, session, user)


async def show_crm_dashboard(message: Message, session: AsyncSession, user: User):
    """Render CRM dashboard text and options."""
    cust_svc = CustomerService(session)
    summary = await cust_svc.get_crm_summary(user.id)

    text = (
        f"👥 <b>MIJOZLAR (CRM)</b>\n"
        f"{'─' * 28}\n\n"
        f"👤 Jami mijozlar: <b>{summary.total_customers} ta</b>\n"
        f"✅ Faol mijozlar: <b>{summary.active_customers} ta</b>\n"
        f"🔴 Qarzdor mijozlar: <b>{summary.total_debtors} ta</b>\n\n"
        f"💰 Jami mijozlar qarzi: <b>{format_money(summary.total_customer_debt)}</b>\n"
        f"🛍 Jami mijozlar savdosi: <b>{format_money(summary.total_customer_purchases)}</b>"
    )

    await message.answer(
        text,
        reply_markup=get_customer_main_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "cust:menu")
async def cust_menu_callback(callback: CallbackQuery, state: FSMContext, session: AsyncSession, user: User):
    """Return to CRM menu."""
    await state.clear()
    await callback.answer()
    cust_svc = CustomerService(session)
    summary = await cust_svc.get_crm_summary(user.id)

    text = (
        f"👥 <b>MIJOZLAR (CRM)</b>\n"
        f"{'─' * 28}\n\n"
        f"👤 Jami mijozlar: <b>{summary.total_customers} ta</b>\n"
        f"✅ Faol mijozlar: <b>{summary.active_customers} ta</b>\n"
        f"🔴 Qarzdor mijozlar: <b>{summary.total_debtors} ta</b>\n\n"
        f"💰 Jami mijozlar qarzi: <b>{format_money(summary.total_customer_debt)}</b>\n"
        f"🛍 Jami mijozlar savdosi: <b>{format_money(summary.total_customer_purchases)}</b>"
    )

    try:
        await callback.message.edit_text(
            text,
            reply_markup=get_customer_main_keyboard(),
            parse_mode="HTML",
        )
    except Exception:
        await callback.message.answer(
            text,
            reply_markup=get_customer_main_keyboard(),
            parse_mode="HTML",
        )


# ============ ADD CUSTOMER ============
@router.callback_query(F.data == "cust:add")
async def cust_add_start(callback: CallbackQuery, state: FSMContext):
    """Start customer creation wizard."""
    await state.clear()
    await state.set_state(CustomerAddStates.waiting_name)
    await callback.answer()
    await callback.message.answer(
        "👤 <b>Yangi mijoz qo'shish</b>\n\n"
        "Mijozning ismini kiriting:\n<i>Masalan: Rustam Karimov</i>",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML",
    )


@router.message(CustomerAddStates.waiting_name)
async def cust_add_name(message: Message, state: FSMContext, user: User):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("❌ Amal bekor qilindi.", reply_markup=get_main_menu(is_admin=user.is_admin))
        return

    is_valid, error = validate_text(message.text, max_length=255)
    if not is_valid:
        await message.answer(error)
        return

    await state.update_data(name=message.text.strip())
    await state.set_state(CustomerAddStates.waiting_phone)
    await message.answer(
        "📞 Telefon raqamini kiriting:\n<i>Masalan: +998901234567 yoki O'tkazib yuboring</i>",
        reply_markup=get_skip_keyboard(),
        parse_mode="HTML",
    )


@router.message(CustomerAddStates.waiting_phone)
async def cust_add_phone(message: Message, state: FSMContext, user: User):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("❌ Amal bekor qilindi.", reply_markup=get_main_menu(is_admin=user.is_admin))
        return

    text = message.text.strip()
    if text == "⏩ O'tkazib yuborish":
        phone = None
    else:
        is_valid, phone_val, error = validate_phone(text)
        if not is_valid:
            await message.answer(error)
            return
        phone = phone_val

    await state.update_data(phone=phone)
    await state.set_state(CustomerAddStates.waiting_tg_username)
    await message.answer(
        "🔗 Telegram username kiriting (ixtiyoriy):\n<i>Masalan: @username yoki O'tkazib yuboring</i>",
        reply_markup=get_skip_keyboard(),
        parse_mode="HTML",
    )


@router.message(CustomerAddStates.waiting_tg_username)
async def cust_add_tg_username(message: Message, state: FSMContext, user: User):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("❌ Amal bekor qilindi.", reply_markup=get_main_menu(is_admin=user.is_admin))
        return

    text = message.text.strip()
    if text == "⏩ O'tkazib yuborish":
        tg_user = None
    else:
        tg_user = text.lstrip("@")[:255]

    await state.update_data(telegram_username=tg_user)
    await state.set_state(CustomerAddStates.waiting_tg_user_id)
    await message.answer(
        "🆔 Telegram User ID kiriting (xabarnoma jo'natish uchun):\n<i>Masalan: 123456789 yoki O'tkazib yuboring</i>",
        reply_markup=get_skip_keyboard(),
        parse_mode="HTML",
    )


@router.message(CustomerAddStates.waiting_tg_user_id)
async def cust_add_tg_id(message: Message, state: FSMContext, user: User):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("❌ Amal bekor qilindi.", reply_markup=get_main_menu(is_admin=user.is_admin))
        return

    text = message.text.strip()
    tg_id = None
    if text != "⏩ O'tkazib yuborish":
        if text.isdigit():
            tg_id = int(text)
        else:
            await message.answer("❌ Telegram ID faqat sonlardan iborat bo'lishi kerak.")
            return

    await state.update_data(telegram_user_id=tg_id)
    data = await state.get_data()

    await state.set_state(CustomerAddStates.confirming)
    await message.answer(
        "📋 <b>Mijoz ma'lumotlarini tasdiqlang:</b>\n\n"
        f"👤 Ism: <b>{data['name']}</b>\n"
        f"📞 Telefon: <b>{data.get('phone') or '—'}</b>\n"
        f"🔗 Username: <b>@{data.get('telegram_username') or '—'}</b>\n"
        f"🆔 Telegram ID: <b>{data.get('telegram_user_id') or '—'}</b>\n"
        f"🔔 Xabarnomalar: <b>Yoqilgan</b>",
        reply_markup=get_confirm_inline("cust_add_confirm"),
        parse_mode="HTML",
    )


@router.callback_query(CustomerAddStates.confirming, F.data.startswith("cust_add_confirm:"))
async def cust_add_confirm(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, user: User
):
    action = callback.data.split(":")[1]
    if action == "cancel":
        await state.clear()
        await callback.answer("❌ Bekor qilindi")
        await callback.message.answer("❌ Bekor qilindi.", reply_markup=get_main_menu(is_admin=user.is_admin))
        return

    data = await state.get_data()
    cust_svc = CustomerService(session)
    customer = await cust_svc.create_customer(
        user_id=user.id,
        name=data["name"],
        phone=data.get("phone"),
        telegram_username=data.get("telegram_username"),
        telegram_user_id=data.get("telegram_user_id"),
        notifications_enabled=True,
    )

    await state.clear()
    await callback.answer("✅ Mijoz saqlandi!")
    await callback.message.answer(
        f"✅ <b>{customer.name}</b> CRM bazasiga qo'shildi!\n🆔 ID: <code>#{customer.id}</code>",
        reply_markup=get_main_menu(is_admin=user.is_admin),
        parse_mode="HTML",
    )


# ============ LIST & SEARCH ============
@router.callback_query(F.data.startswith("cust:list:"))
async def cust_list(callback: CallbackQuery, session: AsyncSession, user: User):
    """Show paginated customers."""
    offset = int(callback.data.split(":")[2])
    cust_svc = CustomerService(session)
    customers = await cust_svc.get_user_customers(user.id, limit=11, offset=offset)

    has_more = len(customers) > 10
    display_list = customers[:10]

    await callback.answer()
    if not display_list:
        await callback.message.answer("👥 Hozircha mijozlar mavjud emas.")
        return

    await callback.message.edit_text(
        "👥 <b>Mijozlar ro'yxati:</b>\n<i>Mijozni tanlang:</i>",
        reply_markup=get_customer_list_keyboard(display_list, action="view", offset=offset, has_more=has_more),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "cust:search")
async def cust_search_start(callback: CallbackQuery, state: FSMContext):
    """Start search prompt."""
    await state.set_state(CustomerSearchStates.waiting_query)
    await callback.answer()
    await callback.message.answer(
        "🔍 <b>Mijozni qidirish</b>\n\nIsm yoki telefon raqamini kiriting:",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML",
    )


@router.message(CustomerSearchStates.waiting_query)
async def cust_search_query(message: Message, state: FSMContext, session: AsyncSession, user: User):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("❌ Qidiruv bekor qilindi.", reply_markup=get_main_menu(is_admin=user.is_admin))
        return

    query = message.text.strip()
    cust_svc = CustomerService(session)
    results = await cust_svc.search_customers(user.id, query)
    await state.clear()

    if not results:
        await message.answer(
            f"🔍 <i>'{query}'</i> bo'yicha hech qanday mijoz topilmadi.",
            reply_markup=get_customer_main_keyboard(),
            parse_mode="HTML",
        )
        return

    await message.answer(
        f"🔍 <b>Qidiruv natijalari ({len(results)} ta):</b>",
        reply_markup=get_customer_list_keyboard(results, action="view"),
        parse_mode="HTML",
    )


# ============ CUSTOMER PROFILE DETAILS ============
@router.callback_query(F.data.startswith("cust_view:"))
async def cust_view(callback: CallbackQuery, session: AsyncSession, user: User):
    """Display detailed profile card for a customer."""
    customer_id = int(callback.data.split(":")[1])
    cust_svc = CustomerService(session)
    customer = await cust_svc.get_customer(customer_id, user.id)

    if not customer:
        await callback.answer("❌ Mijoz topilmadi", show_alert=True)
        return

    status_str = "🟢 Faol" if customer.is_active else "🔴 Nofaol"
    notif_str = "🔔 Yoqilgan" if customer.notifications_enabled else "🔕 O'chirilgan"

    text = (
        f"👤 <b>MIJOZ: {customer.name}</b>\n"
        f"{'─' * 28}\n\n"
        f"📞 Telefon: <b>{customer.phone or '—'}</b>\n"
        f"🔗 Username: <b>@{customer.telegram_username or '—'}</b>\n"
        f"🆔 Telegram ID: <code>{customer.telegram_user_id or '—'}</code>\n"
        f"📊 Holat: <b>{status_str}</b> | Xabar: <b>{notif_str}</b>\n\n"
        f"{'─' * 28}\n"
        f"🛍 Jami xaridlar: <b>{format_money(customer.total_purchases)}</b>\n"
        f"💵 Jami to'langan: <b>{format_money(customer.total_paid)}</b>\n"
        f"🔴 <b>Joriy qarz: {format_money(customer.total_debt)}</b>"
    )

    await callback.answer()
    try:
        await callback.message.edit_text(
            text,
            reply_markup=get_customer_detail_keyboard(
                customer_id=customer.id,
                has_debt=customer.total_debt > 0,
                notifications_enabled=customer.notifications_enabled,
                is_active=customer.is_active,
            ),
            parse_mode="HTML",
        )
    except Exception:
        await callback.message.answer(
            text,
            reply_markup=get_customer_detail_keyboard(
                customer_id=customer.id,
                has_debt=customer.total_debt > 0,
                notifications_enabled=customer.notifications_enabled,
                is_active=customer.is_active,
            ),
            parse_mode="HTML",
        )


# ============ CUSTOMER SALE WITH DEBT ACCUMULATION ============
@router.callback_query(F.data.startswith("cust_sale:"))
async def cust_sale_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession, user: User):
    """Start recording a sale for customer."""
    customer_id = int(callback.data.split(":")[1])
    cust_svc = CustomerService(session)
    customer = await cust_svc.get_customer(customer_id, user.id)
    if not customer:
        await callback.answer("❌ Mijoz topilmadi", show_alert=True)
        return

    await state.update_data(customer_id=customer_id, customer_name=customer.name)
    await state.set_state(CustomerSaleStates.waiting_total_amount)
    await callback.answer()
    await callback.message.answer(
        f"🛍 <b>{customer.name} ga sotuv yozish</b>\n\n"
        "Umumiy xarid summasini kiriting (so'mda):\n<i>Masalan: 400000 yoki 400 000</i>",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML",
    )


@router.message(CustomerSaleStates.waiting_total_amount)
async def cust_sale_total(message: Message, state: FSMContext, user: User):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=get_main_menu(is_admin=user.is_admin))
        return

    is_valid, amount, error = validate_amount(message.text)
    if not is_valid:
        await message.answer(error)
        return

    await state.update_data(total_amount=str(amount))
    await state.set_state(CustomerSaleStates.waiting_paid_amount)
    await message.answer(
        f"💰 Umumiy xarid: <b>{format_money(amount)}</b>\n\n"
        "To'langan summani kiriting (so'mda):\n"
        "<i>To'liq to'langan bo'lsa xarid summasini, qisman to'langan bo'lsa to'langan summani kiriting (masalan: 280000)</i>",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML",
    )


@router.message(CustomerSaleStates.waiting_paid_amount)
async def cust_sale_paid(message: Message, state: FSMContext, user: User):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=get_main_menu(is_admin=user.is_admin))
        return

    is_valid, paid, error = validate_amount(message.text)
    if not is_valid:
        await message.answer(error)
        return

    data = await state.get_data()
    total = Decimal(data["total_amount"])
    if paid > total:
        await message.answer(f"❌ To'langan summa umumiy xarid ({format_money(total)}) dan katta bo'lishi mumkin emas.")
        return

    await state.update_data(paid_amount=str(paid))
    await state.set_state(CustomerSaleStates.waiting_payment_method)
    await message.answer(
        "💳 To'langan summa uchun to'lov turini tanlang:",
        reply_markup=get_payment_method_keyboard(prefix="cust_sale_pm"),
    )


@router.callback_query(CustomerSaleStates.waiting_payment_method, F.data.startswith("cust_sale_pm:"))
async def cust_sale_pm(callback: CallbackQuery, state: FSMContext, user: User):
    method = callback.data.split(":")[1]
    await state.update_data(payment_method=method)
    await callback.answer()

    await state.set_state(CustomerSaleStates.waiting_description)
    await callback.message.answer(
        "📝 Izoh kiriting (ixtiyoriy):\n<i>O'tkazib yuborish mumkin</i>",
        reply_markup=get_skip_keyboard(),
        parse_mode="HTML",
    )


@router.message(CustomerSaleStates.waiting_description)
async def cust_sale_desc(message: Message, state: FSMContext, session: AsyncSession, user: User):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=get_main_menu(is_admin=user.is_admin))
        return

    text = message.text.strip()
    desc = None if text == "⏩ O'tkazib yuborish" else text[:500]
    await state.update_data(description=desc)

    data = await state.get_data()
    cust_svc = CustomerService(session)
    customer = await cust_svc.get_customer(data["customer_id"], user.id)

    total = Decimal(data["total_amount"])
    paid = Decimal(data["paid_amount"])
    new_debt = total - paid
    old_debt = customer.total_debt
    total_debt = old_debt + new_debt
    pm = PAYMENT_LABELS.get(data.get("payment_method", "cash"), "💵 Naqd")

    await state.set_state(CustomerSaleStates.confirming)
    await message.answer(
        f"📋 <b>Sotuvni tasdiqlang:</b>\n\n"
        f"👤 Mijoz: <b>{customer.name}</b>\n"
        f"🛍 Xarid: <b>{format_money(total)}</b>\n"
        f"💵 To'langan: <b>{format_money(paid)}</b> ({pm})\n"
        f"🔴 Bugungi qarz: <b>{format_money(new_debt)}</b>\n"
        f"🔴 Oldingi qarz: <b>{format_money(old_debt)}</b>\n\n"
        f"🔴 <b>Jami qarz: {format_money(total_debt)}</b>\n"
        f"📝 Izoh: <i>{desc or '—'}</i>",
        reply_markup=get_confirm_inline("cust_sale_confirm"),
        parse_mode="HTML",
    )


@router.callback_query(CustomerSaleStates.confirming, F.data.startswith("cust_sale_confirm:"))
async def cust_sale_confirm(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, user: User, bot: Bot
):
    action = callback.data.split(":")[1]
    if action == "cancel":
        await state.clear()
        await callback.answer("❌ Bekor qilindi")
        await callback.message.answer("❌ Bekor qilindi.", reply_markup=get_main_menu(is_admin=user.is_admin))
        return

    data = await state.get_data()
    try:
        cust_svc = CustomerService(session)
        total = Decimal(data["total_amount"])
        paid = Decimal(data["paid_amount"])
        pm_str = data.get("payment_method", "cash")
        pm_enum = PaymentMethod(pm_str) if pm_str in PaymentMethod._value2member_map_ else PaymentMethod.CASH
        desc = data.get("description")

        seller_name = user.full_name or "Do'kon"
        res = await cust_svc.record_customer_sale(
            user_id=user.id,
            customer_id=data["customer_id"],
            total_amount=total,
            paid_amount=paid,
            payment_method=pm_enum,
            description=desc,
            bot=callback.bot or bot,
            seller_name=seller_name,
        )

        await state.clear()
        await callback.answer("✅ Sotuv saqlandi!")

        notif_badge = "\n📲 <i>Mijozga Telegram xabarnoma yuborildi!</i>" if res["notification_sent"] else ""
        await callback.message.answer(
            f"✅ <b>Sotuv muvaffaqiyatli saqlandi!</b>\n\n"
            f"👤 Mijoz: <b>{res['customer'].name}</b>\n"
            f"🛍 Xarid: <b>{format_money(total)}</b>\n"
            f"💵 To'landi: <b>{format_money(paid)}</b>\n"
            f"🔴 Jami qarz: <b>{format_money(res['total_debt'])}</b>"
            f"{notif_badge}",
            reply_markup=get_main_menu(is_admin=user.is_admin),
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"Customer sale error for user {user.id}: {e}")
        await callback.answer("❌ Xatolik yuz berdi", show_alert=True)
        await state.clear()


# ============ CUSTOMER DEBT REPAYMENT ============
@router.callback_query(F.data.startswith("cust_pay:"))
async def cust_pay_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession, user: User):
    """Start debt repayment flow for a customer."""
    customer_id = int(callback.data.split(":")[1])
    cust_svc = CustomerService(session)
    customer = await cust_svc.get_customer(customer_id, user.id)
    if not customer:
        await callback.answer("❌ Mijoz topilmadi", show_alert=True)
        return

    await state.update_data(customer_id=customer_id, customer_name=customer.name)
    await state.set_state(CustomerDebtPaymentStates.waiting_amount)
    await callback.answer()
    await callback.message.answer(
        f"💵 <b>{customer.name} dan qarz to'lovi qabul qilish</b>\n\n"
        f"🔴 Joriy qarz: <b>{format_money(customer.total_debt)}</b>\n\n"
        "To'lov summasini kiriting (so'mda):",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML",
    )


@router.message(CustomerDebtPaymentStates.waiting_amount)
async def cust_pay_amount(message: Message, state: FSMContext, user: User):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=get_main_menu(is_admin=user.is_admin))
        return

    is_valid, amount, error = validate_amount(message.text)
    if not is_valid:
        await message.answer(error)
        return

    await state.update_data(payment_amount=str(amount))
    await state.set_state(CustomerDebtPaymentStates.waiting_payment_method)
    await message.answer(
        "💳 To'lov turini tanlang:",
        reply_markup=get_payment_method_keyboard(prefix="cust_pay_pm"),
    )


@router.callback_query(CustomerDebtPaymentStates.waiting_payment_method, F.data.startswith("cust_pay_pm:"))
async def cust_pay_pm(callback: CallbackQuery, state: FSMContext, user: User):
    method = callback.data.split(":")[1]
    await state.update_data(payment_method=method)
    await callback.answer()

    await state.set_state(CustomerDebtPaymentStates.waiting_description)
    await callback.message.answer(
        "📝 Izoh kiriting (ixtiyoriy):\n<i>O'tkazib yuborish mumkin</i>",
        reply_markup=get_skip_keyboard(),
        parse_mode="HTML",
    )


@router.message(CustomerDebtPaymentStates.waiting_description)
async def cust_pay_desc(message: Message, state: FSMContext, session: AsyncSession, user: User):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("❌ Bekor qilindi.", reply_markup=get_main_menu(is_admin=user.is_admin))
        return

    text = message.text.strip()
    desc = None if text == "⏩ O'tkazib yuborish" else text[:500]
    await state.update_data(description=desc)

    data = await state.get_data()
    cust_svc = CustomerService(session)
    customer = await cust_svc.get_customer(data["customer_id"], user.id)

    amount = Decimal(data["payment_amount"])
    old_debt = customer.total_debt
    rem_debt = max(Decimal("0.00"), old_debt - amount)
    pm = PAYMENT_LABELS.get(data.get("payment_method", "cash"), "💵 Naqd")

    await state.set_state(CustomerDebtPaymentStates.confirming)
    await message.answer(
        f"📋 <b>Qarz to'lovini tasdiqlang:</b>\n\n"
        f"👤 Mijoz: <b>{customer.name}</b>\n"
        f"💵 To'lov summasi: <b>{format_money(amount)}</b> ({pm})\n"
        f"🔴 Oldingi qarz: <b>{format_money(old_debt)}</b>\n"
        f"🟡 Qolgan qarz: <b>{format_money(rem_debt)}</b>\n"
        f"📝 Izoh: <i>{desc or '—'}</i>",
        reply_markup=get_confirm_inline("cust_pay_confirm"),
        parse_mode="HTML",
    )


@router.callback_query(CustomerDebtPaymentStates.confirming, F.data.startswith("cust_pay_confirm:"))
async def cust_pay_confirm(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, user: User, bot: Bot
):
    action = callback.data.split(":")[1]
    if action == "cancel":
        await state.clear()
        await callback.answer("❌ Bekor qilindi")
        await callback.message.answer("❌ Bekor qilindi.", reply_markup=get_main_menu(is_admin=user.is_admin))
        return

    data = await state.get_data()
    try:
        cust_svc = CustomerService(session)
        amount = Decimal(data["payment_amount"])
        pm_str = data.get("payment_method", "cash")
        pm_enum = PaymentMethod(pm_str) if pm_str in PaymentMethod._value2member_map_ else PaymentMethod.CASH
        desc = data.get("description")

        seller_name = user.full_name or "Do'kon"
        res = await cust_svc.record_customer_debt_payment(
            user_id=user.id,
            customer_id=data["customer_id"],
            payment_amount=amount,
            payment_method=pm_enum,
            description=desc,
            bot=callback.bot or bot,
            seller_name=seller_name,
        )

        await state.clear()
        await callback.answer("✅ To'lov qabul qilindi!")

        notif_badge = "\n📲 <i>Mijozga Telegram xabarnoma yuborildi!</i>" if res["notification_sent"] else ""
        await callback.message.answer(
            f"✅ <b>Qarz to'lovi qabul qilindi!</b>\n\n"
            f"👤 Mijoz: <b>{res['customer'].name}</b>\n"
            f"💵 To'langan: <b>{format_money(amount)}</b>\n"
            f"🟡 Qolgan qarz: <b>{format_money(res['remaining_debt'])}</b>"
            f"{notif_badge}",
            reply_markup=get_main_menu(is_admin=user.is_admin),
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"Debt payment error for user {user.id}: {e}")
        await callback.answer("❌ Xatolik yuz berdi", show_alert=True)
        await state.clear()


# ============ CUSTOMER HISTORY & TOGGLES ============
@router.callback_query(F.data.startswith("cust_hist_tx:"))
async def cust_hist_tx(callback: CallbackQuery, session: AsyncSession, user: User):
    """View customer transaction history."""
    customer_id = int(callback.data.split(":")[1])
    cust_svc = CustomerService(session)
    hist = await cust_svc.get_customer_history(customer_id, user.id)

    transactions = hist["transactions"]
    customer = hist["customer"]

    await callback.answer()
    if not transactions:
        await callback.message.answer(f"📜 {customer.name} uchun xaridlar tarixi bo'sh.")
        return

    text = f"📜 <b>{customer.name} — Xaridlar tarixi:</b>\n\n"
    for tx in transactions:
        sign = "+" if tx.type.value == "income" else "-"
        date_str = format_date_short(tx.transaction_date, user.timezone)
        text += (
            f"💰 <b>{sign}{format_money(tx.amount)}</b> | 📅 {date_str}\n"
            f"   📝 {tx.description or '—'} | 🆔 <code>#{tx.id}</code>\n\n"
        )

    await callback.message.answer(text, parse_mode="HTML")


@router.callback_query(F.data.startswith("cust_hist_debt:"))
async def cust_hist_debt(callback: CallbackQuery, session: AsyncSession, user: User):
    """View customer debt history."""
    customer_id = int(callback.data.split(":")[1])
    cust_svc = CustomerService(session)
    hist = await cust_svc.get_customer_history(customer_id, user.id)

    debts = hist["debts"]
    customer = hist["customer"]

    await callback.answer()
    if not debts:
        await callback.message.answer(f"📑 {customer.name} uchun qarz yozuvlari topilmadi.")
        return

    text = f"📑 <b>{customer.name} — Qarzlar tarixi:</b>\n\n"
    for d in debts:
        date_str = format_date_short(d.created_date, user.timezone)
        status_icon = "🟢 To'langan" if d.status.value == "paid" else "🔴 Faol qarz"
        text += (
            f"🔴 <b>{format_money(d.amount)}</b> ({status_icon})\n"
            f"   To'landi: {format_money(d.paid_amount)} | Qoldi: {format_money(d.remaining_amount)}\n"
            f"   📅 {date_str} | 🆔 <code>#{d.id}</code>\n\n"
        )

    await callback.message.answer(text, parse_mode="HTML")


@router.callback_query(F.data.startswith("cust_toggle_notif:"))
async def cust_toggle_notif(callback: CallbackQuery, session: AsyncSession, user: User):
    """Toggle customer notification preference."""
    customer_id = int(callback.data.split(":")[1])
    cust_svc = CustomerService(session)
    customer = await cust_svc.toggle_notifications(customer_id, user.id)

    if customer:
        status_text = "yoqildi" if customer.notifications_enabled else "o'chirildi"
        await callback.answer(f"🔔 Xabarnoma {status_text}")
        await cust_view(callback, session, user)


@router.callback_query(F.data.startswith("cust_toggle_active:"))
async def cust_toggle_active(callback: CallbackQuery, session: AsyncSession, user: User):
    """Toggle customer active status."""
    customer_id = int(callback.data.split(":")[1])
    cust_svc = CustomerService(session)
    customer = await cust_svc.toggle_active(customer_id, user.id)

    if customer:
        status_text = "faollashtirildi" if customer.is_active else "nofaol qilindi"
        await callback.answer(f"Holat {status_text}")
        await cust_view(callback, session, user)


# ============ EDIT CUSTOMER ============
@router.callback_query(F.data.startswith("cust_edit:"))
async def cust_edit_menu(callback: CallbackQuery, session: AsyncSession, user: User):
    """Show edit field options."""
    customer_id = int(callback.data.split(":")[1])
    cust_svc = CustomerService(session)
    customer = await cust_svc.get_customer(customer_id, user.id)
    if not customer:
        await callback.answer("❌ Mijoz topilmadi", show_alert=True)
        return

    await callback.answer()
    await callback.message.edit_text(
        f"✏️ <b>{customer.name} ma'lumotlarini tahrirlash:</b>\n\n"
        "Qaysi ma'lumotni o'zgartirmoqchisiz?",
        reply_markup=get_customer_edit_keyboard(customer.id),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("cust_ed_f:"))
async def cust_edit_field_select(callback: CallbackQuery, state: FSMContext, user: User):
    parts = callback.data.split(":")
    field = parts[1]
    customer_id = int(parts[2])
    await state.update_data(edit_customer_id=customer_id)
    await callback.answer()

    if field == "name":
        await state.set_state(CustomerEditStates.waiting_name)
        await callback.message.answer("👤 Yangi ismni kiriting:", reply_markup=get_cancel_keyboard())
    elif field == "phone":
        await state.set_state(CustomerEditStates.waiting_phone)
        await callback.message.answer("📞 Yangi telefon raqamini kiriting:", reply_markup=get_cancel_keyboard())
    elif field == "username":
        await state.set_state(CustomerEditStates.waiting_tg_username)
        await callback.message.answer("🔗 Yangi Telegram usernameni kiriting:", reply_markup=get_cancel_keyboard())
    elif field == "tg_id":
        await state.set_state(CustomerEditStates.waiting_tg_user_id)
        await callback.message.answer("🆔 Yangi Telegram ID ni kiriting:", reply_markup=get_cancel_keyboard())


@router.message(CustomerEditStates.waiting_name)
async def cust_edit_save_name(message: Message, state: FSMContext, session: AsyncSession, user: User):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("❌ Tahrirlash bekor qilindi.", reply_markup=get_main_menu(is_admin=user.is_admin))
        return

    data = await state.get_data()
    cust_svc = CustomerService(session)
    await cust_svc.update_customer(customer_id=data["edit_customer_id"], user_id=user.id, name=message.text.strip())
    await state.clear()
    await message.answer("✅ Mijoz ismi yangilandi!", reply_markup=get_main_menu(is_admin=user.is_admin))


@router.message(CustomerEditStates.waiting_phone)
async def cust_edit_save_phone(message: Message, state: FSMContext, session: AsyncSession, user: User):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("❌ Tahrirlash bekor qilindi.", reply_markup=get_main_menu(is_admin=user.is_admin))
        return

    is_valid, phone_val, error = validate_phone(message.text.strip())
    if not is_valid:
        await message.answer(error)
        return

    data = await state.get_data()
    cust_svc = CustomerService(session)
    await cust_svc.update_customer(customer_id=data["edit_customer_id"], user_id=user.id, phone=phone_val)
    await state.clear()
    await message.answer("✅ Mijoz telefoni yangilandi!", reply_markup=get_main_menu(is_admin=user.is_admin))


@router.message(CustomerEditStates.waiting_tg_username)
async def cust_edit_save_username(message: Message, state: FSMContext, session: AsyncSession, user: User):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("❌ Tahrirlash bekor qilindi.", reply_markup=get_main_menu(is_admin=user.is_admin))
        return

    data = await state.get_data()
    cust_svc = CustomerService(session)
    await cust_svc.update_customer(
        customer_id=data["edit_customer_id"], user_id=user.id, telegram_username=message.text.strip().lstrip("@")
    )
    await state.clear()
    await message.answer("✅ Mijoz username yangilandi!", reply_markup=get_main_menu(is_admin=user.is_admin))


@router.message(CustomerEditStates.waiting_tg_user_id)
async def cust_edit_save_tg_id(message: Message, state: FSMContext, session: AsyncSession, user: User):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("❌ Tahrirlash bekor qilindi.", reply_markup=get_main_menu(is_admin=user.is_admin))
        return

    text = message.text.strip()
    if not text.isdigit():
        await message.answer("❌ Telegram ID faqat sonlardan iborat bo'lishi kerak.")
        return

    data = await state.get_data()
    cust_svc = CustomerService(session)
    await cust_svc.update_customer(
        customer_id=data["edit_customer_id"], user_id=user.id, telegram_user_id=int(text)
    )
    await state.clear()
    await message.answer("✅ Mijoz Telegram ID yangilandi!", reply_markup=get_main_menu(is_admin=user.is_admin))
