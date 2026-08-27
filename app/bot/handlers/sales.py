"""Dedicated 🛒 Sotuvlar (Sales) handler with multi-product basket support, CRM integration, debts, and history."""
from datetime import datetime
from decimal import Decimal
from typing import List
import pytz
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
from app.bot.keyboards.income_kb import get_payment_method_keyboard
from app.bot.keyboards.main_menu import get_main_menu
from app.bot.keyboards.products_kb import (
    get_product_list_keyboard,
    get_sale_customer_choice_keyboard,
    get_sale_payment_choice_keyboard,
)
from app.bot.keyboards.sales_kb import (
    get_basket_keyboard,
    get_sale_detail_keyboard,
    get_sales_list_keyboard,
    get_sales_main_keyboard,
)
from app.bot.states.sale_states import SaleSearchStates, SaleWizardStates
from app.config.constants import PaymentMethod
from app.database.models.user import User
from app.database.repositories.product_repo import ProductRepository
from app.services.customer_service import CustomerService
from app.services.sale_service import SaleService
from app.utils.formatters import format_date_short, format_money
from app.utils.validators import validate_amount, validate_quantity

router = Router()
router.name = "Sotuvlar (Sales)"

PAYMENT_LABELS = {
    "cash": "💵 Naqd",
    "card": "💳 Karta",
    "bank": "🏦 Bank",
    "other": "🔄 Boshqa",
}


# ============ ENTRY POINT ============
@router.message(F.text == "🛒 Sotuvlar")
@router.message(Command("sales"))
async def sales_entry(message: Message, state: FSMContext, session: AsyncSession, user: User):
    """Show sales dashboard."""
    await state.clear()
    await show_sales_dashboard(message, session, user)


async def show_sales_dashboard(message: Message, session: AsyncSession, user: User):
    """Render sales dashboard with accurate metrics."""
    sale_svc = SaleService(session)
    tz = pytz.timezone(user.timezone or "Asia/Tashkent")
    now = datetime.now(tz)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=999999)

    today_summary = await sale_svc.get_sales_summary(user.id, date_from=start_of_day, date_to=end_of_day)

    text = (
        f"🛒 <b>SOTUVLAR BO'LIMI</b>\n"
        f"{'─' * 28}\n\n"
        f"📊 Bugungi sotuvlar soni: <b>{today_summary.total_sales_count} ta</b>\n"
        f"🛍 <b>Bugungi savdo (jami):</b> <b>{format_money(today_summary.total_sales_amount)}</b>\n"
        f"💵 <b>Haqiqiy tushum (to'langan):</b> <b>{format_money(today_summary.total_paid_amount)}</b>\n"
        f"🔴 <b>Yangi qarz (to'lanmagan):</b> <b>{format_money(today_summary.total_debt_amount)}</b>\n\n"
        f"<i>Quyidagi menyudan kerakli bo'limni tanlang:</i>"
    )

    await message.answer(
        text,
        reply_markup=get_sales_main_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "sales:menu")
async def sales_menu_callback(callback: CallbackQuery, state: FSMContext, session: AsyncSession, user: User):
    """Return to sales main menu."""
    await state.clear()
    await callback.answer()
    sale_svc = SaleService(session)
    tz = pytz.timezone(user.timezone or "Asia/Tashkent")
    now = datetime.now(tz)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=999999)

    today_summary = await sale_svc.get_sales_summary(user.id, date_from=start_of_day, date_to=end_of_day)

    text = (
        f"🛒 <b>SOTUVLAR BO'LIMI</b>\n"
        f"{'─' * 28}\n\n"
        f"📊 Bugungi sotuvlar soni: <b>{today_summary.total_sales_count} ta</b>\n"
        f"🛍 <b>Bugungi savdo (jami):</b> <b>{format_money(today_summary.total_sales_amount)}</b>\n"
        f"💵 <b>Haqiqiy tushum (to'langan):</b> <b>{format_money(today_summary.total_paid_amount)}</b>\n"
        f"🔴 <b>Yangi qarz (to'lanmagan):</b> <b>{format_money(today_summary.total_debt_amount)}</b>\n\n"
        f"<i>Quyidagi menyudan kerakli bo'limni tanlang:</i>"
    )

    try:
        await callback.message.edit_text(
            text,
            reply_markup=get_sales_main_keyboard(),
            parse_mode="HTML",
        )
    except Exception:
        await callback.message.answer(
            text,
            reply_markup=get_sales_main_keyboard(),
            parse_mode="HTML",
        )


# ============ MULTI-PRODUCT SALE FLOW ============
@router.callback_query(F.data == "sales:new")
async def sales_new_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession, user: User):
    """Start new multi-product sale wizard."""
    await state.clear()
    await state.update_data(basket=[])
    await callback.answer()

    cust_svc = CustomerService(session)
    customers = await cust_svc.get_user_customers(user.id, active_only=True, limit=10)

    if customers:
        await state.set_state(SaleWizardStates.selecting_customer)
        await callback.message.answer(
            "👤 <b>1-QADAM: Mijozni tanlang</b>\n<i>(yoki mijozsiz davom eting)</i>",
            reply_markup=get_sale_customer_choice_keyboard(customers),
            parse_mode="HTML",
        )
    else:
        await state.update_data(customer_id=None, customer_name="Mijozsiz")
        await _prompt_product_choice_for_sale(callback.message, state, session, user)


@router.callback_query(SaleWizardStates.selecting_customer, F.data.startswith("sell_cust:"))
async def sales_customer_selected(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, user: User
):
    action = callback.data.split(":")[1]
    if action == "cancel":
        await state.clear()
        await callback.answer("❌ Bekor qilindi")
        await callback.message.answer("❌ Sotuv bekor qilindi.", reply_markup=get_main_menu(is_admin=user.is_admin))
        return

    if action == "none":
        await state.update_data(customer_id=None, customer_name="Mijozsiz")
    else:
        customer_id = int(action)
        cust_svc = CustomerService(session)
        customer = await cust_svc.get_customer(customer_id, user.id)
        if customer:
            await state.update_data(customer_id=customer.id, customer_name=customer.name)

    await callback.answer()
    await _prompt_product_choice_for_sale(callback.message, state, session, user)


async def _prompt_product_choice_for_sale(
    message: Message, state: FSMContext, session: AsyncSession, user: User
):
    product_repo = ProductRepository(session)
    products = await product_repo.get_user_products(user.id)
    if not products:
        await state.clear()
        await message.answer(
            "📦 Omborda mahsulotlar mavjud emas.\nIltimos, avval mahsulot qo'shing.",
            reply_markup=get_main_menu(is_admin=user.is_admin),
        )
        return

    await state.set_state(SaleWizardStates.selecting_product)
    await message.answer(
        "📦 <b>Mahsulotni tanlang:</b>",
        reply_markup=get_product_list_keyboard(products, action="basket_choice"),
        parse_mode="HTML",
    )


@router.callback_query(SaleWizardStates.selecting_product, F.data.startswith("product_basket_choice:"))
async def sales_product_chosen(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, user: User
):
    action = callback.data.split(":")[1]
    if action == "cancel":
        await state.clear()
        await callback.answer("❌ Bekor qilindi")
        await callback.message.answer("❌ Sotuv bekor qilindi.", reply_markup=get_main_menu(is_admin=user.is_admin))
        return

    product_id = int(action)
    product_repo = ProductRepository(session)
    product = await product_repo.get_by_id_and_user(product_id, user.id)
    if not product:
        await callback.answer("❌ Mahsulot topilmadi", show_alert=True)
        return

    await state.update_data(
        current_product_id=product.id,
        current_product_name=product.name,
        current_selling_price=str(product.selling_price),
        current_unit=product.unit,
        current_max_qty=str(product.quantity),
    )
    await state.set_state(SaleWizardStates.waiting_quantity)
    await callback.answer()

    qty_str = (
        f"{int(product.quantity)}"
        if product.quantity == product.quantity.to_integral_value()
        else f"{product.quantity:.2f}"
    )
    await callback.message.answer(
        f"📦 <b>{product.name}</b>\n\n"
        f"💰 Narx: <b>{format_money(product.selling_price)}/{product.unit}</b>\n"
        f"📊 Omborda: <b>{qty_str} {product.unit}</b>\n\n"
        "Sotiladigan miqdorni kiriting:",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML",
    )


@router.message(SaleWizardStates.waiting_quantity)
async def sales_quantity_entered(
    message: Message, state: FSMContext, session: AsyncSession, user: User
):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("❌ Sotuv bekor qilindi.", reply_markup=get_main_menu(is_admin=user.is_admin))
        return

    is_valid, qty, error = validate_quantity(message.text)
    if not is_valid:
        await message.answer(error)
        return

    data = await state.get_data()
    product_repo = ProductRepository(session)
    product = await product_repo.get_by_id_and_user(data["current_product_id"], user.id)

    # Check already added quantity in basket + current quantity
    basket = data.get("basket", [])
    already_in_basket = sum(
        Decimal(str(it["quantity"])) for it in basket if it["product_id"] == product.id
    )

    if (qty + already_in_basket) > product.quantity:
        await message.answer(
            f"❌ Yetarli mahsulot yo'q!\n"
            f"Omborda mavjud: <b>{product.quantity} {product.unit}</b>\n"
            f"Savatdagi: <b>{already_in_basket} {product.unit}</b>",
            parse_mode="HTML",
        )
        return

    # Add to basket
    unit_price = product.selling_price
    line_total = qty * unit_price
    basket.append(
        {
            "product_id": product.id,
            "product_name": product.name,
            "unit": product.unit,
            "quantity": str(qty),
            "unit_price": str(unit_price),
            "total_price": str(line_total),
        }
    )
    await state.update_data(basket=basket)

    await show_basket_card(message, state)


async def show_basket_card(message: Message, state: FSMContext):
    """Render current basket contents and action buttons."""
    data = await state.get_data()
    basket = data.get("basket", [])
    cust_name = data.get("customer_name") or "Mijozsiz"

    total_amount = sum(Decimal(str(it["total_price"])) for it in basket)
    await state.update_data(total_amount=str(total_amount))

    lines = []
    for idx, item in enumerate(basket, 1):
        q = Decimal(str(item["quantity"]))
        up = Decimal(str(item["unit_price"]))
        tp = Decimal(str(item["total_price"]))
        lines.append(f"{idx}. <b>{item['product_name']}</b> — {q} {item['unit']} × {format_money(up)} = <b>{format_money(tp)}</b>")

    basket_text = "\n".join(lines)
    text = (
        f"🛒 <b>SAVAT ({len(basket)} ta mahsulot)</b>\n"
        f"👤 Mijoz: <b>{cust_name}</b>\n"
        f"{'─' * 28}\n"
        f"{basket_text}\n"
        f"{'─' * 28}\n"
        f"💰 <b>JAMI SUMMA: {format_money(total_amount)}</b>"
    )

    await state.set_state(SaleWizardStates.basket_menu)
    await message.answer(
        text,
        reply_markup=get_basket_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(SaleWizardStates.basket_menu, F.data == "basket:add_more")
async def basket_add_more(callback: CallbackQuery, state: FSMContext, session: AsyncSession, user: User):
    """Add another product to current basket."""
    await callback.answer()
    await _prompt_product_choice_for_sale(callback.message, state, session, user)


@router.callback_query(SaleWizardStates.basket_menu, F.data == "basket:clear")
async def basket_clear(callback: CallbackQuery, state: FSMContext, session: AsyncSession, user: User):
    """Clear basket."""
    await state.update_data(basket=[])
    await callback.answer("🗑 Savat tozalandi")
    await _prompt_product_choice_for_sale(callback.message, state, session, user)


@router.callback_query(SaleWizardStates.basket_menu, F.data == "basket:cancel")
async def basket_cancel(callback: CallbackQuery, state: FSMContext, user: User):
    """Cancel sale."""
    await state.clear()
    await callback.answer("❌ Bekor qilindi")
    await callback.message.answer("❌ Sotuv bekor qilindi.", reply_markup=get_main_menu(is_admin=user.is_admin))


@router.callback_query(SaleWizardStates.basket_menu, F.data == "basket:checkout")
async def basket_checkout(callback: CallbackQuery, state: FSMContext, user: User):
    """Proceed to payment step."""
    await callback.answer()
    data = await state.get_data()
    total = Decimal(str(data["total_amount"]))
    customer_id = data.get("customer_id")

    if customer_id:
        await state.set_state(SaleWizardStates.waiting_paid_amount)
        await callback.message.answer(
            f"💰 Jami to'lov: <b>{format_money(total)}</b>\n\n"
            "To'lov turini tanlang yoki to'langan summani kiriting:",
            reply_markup=get_sale_payment_choice_keyboard(total),
            parse_mode="HTML",
        )
    else:
        # Anonymous sale -> full payment
        await state.update_data(paid_amount=str(total))
        await _prompt_sales_payment_method(callback.message, state)


@router.callback_query(SaleWizardStates.waiting_paid_amount, F.data.startswith("sell_pay:"))
async def sales_payment_choice_cb(callback: CallbackQuery, state: FSMContext, user: User):
    action = callback.data.split(":")[1]
    if action == "cancel":
        await state.clear()
        await callback.answer("❌ Bekor qilindi")
        await callback.message.answer("❌ Sotuv bekor qilindi.", reply_markup=get_main_menu(is_admin=user.is_admin))
        return

    data = await state.get_data()
    total = Decimal(str(data["total_amount"]))

    if action == "full":
        await state.update_data(paid_amount=str(total))
        await callback.answer()
        await _prompt_sales_payment_method(callback.message, state)
    elif action == "partial":
        await callback.answer()
        await callback.message.answer(
            f"💵 <b>To'langan summani kiriting (so'mda):</b>\n"
            f"<i>Jami: {format_money(total)} (Masalan: 280000)</i>",
            reply_markup=get_cancel_keyboard(),
            parse_mode="HTML",
        )


@router.message(SaleWizardStates.waiting_paid_amount)
async def sales_paid_amount_text(message: Message, state: FSMContext, user: User):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("❌ Sotuv bekor qilindi.", reply_markup=get_main_menu(is_admin=user.is_admin))
        return

    is_valid, paid, error = validate_amount(message.text)
    if not is_valid:
        await message.answer(error)
        return

    data = await state.get_data()
    total = Decimal(str(data["total_amount"]))
    if paid > total:
        await message.answer(f"❌ To'langan summa jami summadan ({format_money(total)}) katta bo'lishi mumkin emas.")
        return

    await state.update_data(paid_amount=str(paid))
    await _prompt_sales_payment_method(message, state)


async def _prompt_sales_payment_method(message: Message, state: FSMContext):
    await state.set_state(SaleWizardStates.waiting_payment_method)
    await message.answer(
        "💳 <b>To'lov turini tanlang:</b>",
        reply_markup=get_payment_method_keyboard(prefix="sales_pm"),
        parse_mode="HTML",
    )


@router.callback_query(SaleWizardStates.waiting_payment_method, F.data.startswith("sales_pm:"))
async def sales_pm_selected(callback: CallbackQuery, state: FSMContext):
    method = callback.data.split(":")[1]
    await state.update_data(payment_method=method)
    await callback.answer()

    await state.set_state(SaleWizardStates.waiting_description)
    await callback.message.answer(
        "📝 Izoh kiriting (ixtiyoriy):\n<i>O'tkazib yuborish mumkin</i>",
        reply_markup=get_skip_keyboard(),
        parse_mode="HTML",
    )


@router.message(SaleWizardStates.waiting_description)
async def sales_description_entered(
    message: Message, state: FSMContext, session: AsyncSession, user: User
):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("❌ Sotuv bekor qilindi.", reply_markup=get_main_menu(is_admin=user.is_admin))
        return

    text = message.text.strip()
    desc = None if text == "⏩ O'tkazib yuborish" else text[:500]
    await state.update_data(description=desc)

    data = await state.get_data()
    basket = data.get("basket", [])
    total = Decimal(str(data["total_amount"]))
    paid = Decimal(str(data["paid_amount"]))
    new_debt = total - paid
    pm = PAYMENT_LABELS.get(data.get("payment_method", "cash"), "💵 Naqd")

    cust_name = data.get("customer_name") or "Mijozsiz"
    old_debt = Decimal("0.00")
    total_debt = Decimal("0.00")

    if data.get("customer_id"):
        cust_svc = CustomerService(session)
        customer = await cust_svc.get_customer(data["customer_id"], user.id)
        if customer:
            old_debt = customer.total_debt
            total_debt = old_debt + new_debt

    items_summary = "\n".join(
        [
            f"  • {it['product_name']} ({it['quantity']} {it['unit']}) = <b>{format_money(Decimal(str(it['total_price'])))}</b>"
            for it in basket
        ]
    )

    await state.set_state(SaleWizardStates.confirming)
    confirm_text = (
        f"📋 <b>SOTUVNI TASDIQLANG:</b>\n\n"
        f"👤 Mijoz: <b>{cust_name}</b>\n"
        f"📦 Mahsulotlar:\n{items_summary}\n\n"
        f"💰 Jami summa: <b>{format_money(total)}</b>\n"
        f"💵 To'langan: <b>{format_money(paid)}</b> ({pm})\n"
    )

    if new_debt > 0:
        confirm_text += (
            f"🔴 Bugungi qarz: <b>{format_money(new_debt)}</b>\n"
            f"🔴 Oldingi qarz: <b>{format_money(old_debt)}</b>\n"
            f"🔴 <b>Jami qarz: {format_money(total_debt)}</b>\n"
        )

    confirm_text += f"📝 Izoh: <i>{desc or '—'}</i>"

    await message.answer(
        confirm_text,
        reply_markup=get_confirm_inline("sales_basket_confirm"),
        parse_mode="HTML",
    )


@router.callback_query(SaleWizardStates.confirming, F.data.startswith("sales_basket_confirm:"))
async def sales_basket_confirmed_execute(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, user: User, bot: Bot
):
    action = callback.data.split(":")[1]
    if action == "cancel":
        await state.clear()
        await callback.answer("❌ Bekor qilindi")
        await callback.message.answer("❌ Sotuv bekor qilindi.", reply_markup=get_main_menu(is_admin=user.is_admin))
        return

    data = await state.get_data()
    try:
        sale_svc = SaleService(session)
        basket = data["basket"]
        paid = Decimal(str(data["paid_amount"]))
        pm_str = data.get("payment_method", "cash")
        pm_enum = PaymentMethod(pm_str) if pm_str in PaymentMethod._value2member_map_ else PaymentMethod.CASH
        desc = data.get("description")
        seller_name = user.full_name or "Do'kon"

        res = await sale_svc.process_basket_sale(
            user_id=user.id,
            items=basket,
            customer_id=data.get("customer_id"),
            paid_amount=paid,
            payment_method=pm_enum,
            description=desc,
            bot=bot,
            seller_name=seller_name,
        )

        await state.clear()
        await callback.answer("✅ Sotuv saqlandi!")

        notif_badge = "\n📲 <i>Mijozga Telegram xabarnoma yuborildi!</i>" if res["notification_sent"] else ""
        cust_line = f"👤 Mijoz: <b>{res['customer'].name}</b>\n" if res["customer"] else ""
        debt_line = f"🔴 Jami qarz: <b>{format_money(res['total_debt'])}\n</b>" if res["new_debt"] > 0 else ""

        await callback.message.answer(
            f"✅ <b>Sotuv muvaffaqiyatli saqlandi!</b>\n\n"
            f"🆔 Sotuv: <code>#{res['sale'].id}</code>\n"
            f"{cust_line}"
            f"📦 Mahsulotlar soni: <b>{len(basket)} ta</b>\n"
            f"💰 Jami summa: <b>{format_money(res['total_amount'])}</b>\n"
            f"💵 Qabul qilindi: <b>{format_money(paid)}</b>\n"
            f"{debt_line}"
            f"{notif_badge}",
            reply_markup=get_main_menu(is_admin=user.is_admin),
            parse_mode="HTML",
        )
        logger.info(f"Basket sale saved: user={user.id} sale_id={res['sale'].id} total={res['total_amount']}")

    except ValueError as e:
        await callback.answer(str(e), show_alert=True)
    except Exception as e:
        logger.error(f"Basket sale execution error for user {user.id}: {e}")
        await callback.answer("❌ Xatolik yuz berdi", show_alert=True)
        await state.clear()


# ============ TODAY'S SALES & HISTORY ============
@router.callback_query(F.data == "sales:today")
async def sales_today_list(callback: CallbackQuery, session: AsyncSession, user: User):
    """View list of today's sales."""
    await callback.answer()
    sale_svc = SaleService(session)
    sales = await sale_svc.get_today_sales(user.id)

    if not sales:
        await callback.message.answer(
            "📋 <b>Bugungi sotuvlar mavjud emas.</b>",
            reply_markup=get_sales_main_keyboard(),
            parse_mode="HTML",
        )
        return

    text = f"📋 <b>Bugungi sotuvlar ({len(sales)} ta):</b>\n<i>Tafsilotlar uchun sotuv ustiga bosing:</i>"
    await callback.message.answer(
        text,
        reply_markup=get_sales_list_keyboard(sales, prefix="today"),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("sales:history:"))
async def sales_history_list(callback: CallbackQuery, session: AsyncSession, user: User):
    """View paginated sales history."""
    offset = int(callback.data.split(":")[2])
    sale_svc = SaleService(session)
    sales = await sale_svc.get_sales_history(user.id, limit=11, offset=offset)

    has_more = len(sales) > 10
    display_list = sales[:10]

    await callback.answer()
    if not display_list:
        await callback.message.answer(
            "📅 <b>Sotuvlar tarixi bo'sh.</b>",
            reply_markup=get_sales_main_keyboard(),
            parse_mode="HTML",
        )
        return

    await callback.message.edit_text(
        "📅 <b>Sotuvlar tarixi:</b>\n<i>Sotuvni tanlang:</i>",
        reply_markup=get_sales_list_keyboard(display_list, offset=offset, has_more=has_more, prefix="history"),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("sale_view:"))
async def sale_view_detail(callback: CallbackQuery, session: AsyncSession, user: User):
    """View full details of a specific sale."""
    sale_id = int(callback.data.split(":")[1])
    sale_svc = SaleService(session)
    sale = await sale_svc.get_sale(sale_id, user.id)

    if not sale:
        await callback.answer("❌ Sotuv topilmadi", show_alert=True)
        return

    cust_name = sale.customer.name if sale.customer else "Mijozsiz"
    date_str = format_date_short(sale.sale_date, user.timezone)
    pm = PAYMENT_LABELS.get(sale.payment_method.value, "💵 Naqd")

    items_text = "\n".join(
        [
            f"  • {item.product_name}: {item.quantity} {item.unit} × {format_money(item.unit_price)} = <b>{format_money(item.total_price)}</b>"
            for item in sale.items
        ]
    )

    text = (
        f"🛒 <b>SOTUV #{sale.id}</b>\n"
        f"{'─' * 28}\n\n"
        f"📅 Sana: <b>{date_str}</b>\n"
        f"👤 Mijoz: <b>{cust_name}</b>\n"
        f"💳 To'lov turi: <b>{pm}</b>\n\n"
        f"📦 <b>Tarkibi:</b>\n{items_text}\n\n"
        f"{'─' * 28}\n"
        f"💰 Jami summa: <b>{format_money(sale.total_amount)}</b>\n"
        f"💵 To'langan: <b>{format_money(sale.paid_amount)}</b>\n"
        f"🔴 Qarz qolgan: <b>{format_money(sale.debt_amount)}</b>\n"
        f"📝 Izoh: <i>{sale.description or '—'}</i>"
    )

    await callback.answer()
    try:
        await callback.message.edit_text(
            text,
            reply_markup=get_sale_detail_keyboard(sale.id),
            parse_mode="HTML",
        )
    except Exception:
        await callback.message.answer(
            text,
            reply_markup=get_sale_detail_keyboard(sale.id),
            parse_mode="HTML",
        )


# ============ SEARCH SALES ============
@router.callback_query(F.data == "sales:search")
async def sales_search_start(callback: CallbackQuery, state: FSMContext):
    """Start sales search."""
    await state.set_state(SaleSearchStates.waiting_query)
    await callback.answer()
    await callback.message.answer(
        "🔍 <b>Sotuvlarni qidirish</b>\n\nMijoz ismi, mahsulot nomi yoki izohni kiriting:",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML",
    )


@router.message(SaleSearchStates.waiting_query)
async def sales_search_query_entered(
    message: Message, state: FSMContext, session: AsyncSession, user: User
):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("❌ Qidiruv bekor qilindi.", reply_markup=get_main_menu(is_admin=user.is_admin))
        return

    query = message.text.strip()
    sale_svc = SaleService(session)
    results = await sale_svc.search_sales(user.id, query)
    await state.clear()

    if not results:
        await message.answer(
            f"🔍 <i>'{query}'</i> bo'yicha hech qanday sotuv topilmadi.",
            reply_markup=get_sales_main_keyboard(),
            parse_mode="HTML",
        )
        return

    await message.answer(
        f"🔍 <b>Qidiruv natijalari ({len(results)} ta):</b>",
        reply_markup=get_sales_list_keyboard(results, prefix="search"),
        parse_mode="HTML",
    )
