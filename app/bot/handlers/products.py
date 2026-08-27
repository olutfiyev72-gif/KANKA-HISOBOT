"""Products handler with full CRUD, inventory management, and integrated CRM sales flow."""
from decimal import Decimal
from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.common_kb import (
    get_cancel_keyboard,
    get_confirm_inline,
    get_skip_keyboard,
)
from app.bot.keyboards.customer_kb import get_customer_list_keyboard
from app.bot.keyboards.income_kb import get_payment_method_keyboard
from app.bot.keyboards.main_menu import get_main_menu
from app.bot.keyboards.products_kb import (
    get_product_actions_keyboard,
    get_product_list_keyboard,
    get_products_menu_keyboard,
    get_sale_customer_choice_keyboard,
    get_sale_payment_choice_keyboard,
)
from app.bot.states.product_states import (
    ProductAddStates,
    ProductEditStates,
    ProductPurchaseStates,
    ProductSellStates,
)
from app.config.constants import PaymentMethod
from app.database.models.user import User
from app.database.repositories.product_repo import ProductRepository
from app.services.customer_service import CustomerService
from app.services.finance_service import FinanceService
from app.services.product_service import ProductService
from app.utils.formatters import format_money, format_percentage
from app.utils.validators import (
    validate_amount,
    validate_quantity,
    validate_sku,
    validate_text,
)

router = Router()
router.name = "Mahsulotlar (Products)"

PAYMENT_LABELS = {
    "cash": "💵 Naqd",
    "card": "💳 Karta",
    "bank": "🏦 Bank",
    "other": "🔄 Boshqa",
}


@router.message(F.text == "📦 Mahsulotlar")
async def products_start(message: Message, state: FSMContext, user: User):
    """Show products menu."""
    await state.clear()
    await message.answer(
        "📦 <b>Mahsulotlar va Ombor</b>\n\nNimani qilmoqchisiz?",
        reply_markup=get_products_menu_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "products:list")
async def products_list(callback: CallbackQuery, session: AsyncSession, user: User):
    """Show all products."""
    await callback.answer()
    product_repo = ProductRepository(session)
    products = await product_repo.get_user_products(user.id)

    if not products:
        await callback.message.answer(
            "📦 Mahsulotlar ro'yxati bo'sh.\n\n"
            "➕ Mahsulot qo'shish uchun <b>Qo'shish</b> tugmasini bosing.",
            reply_markup=get_products_menu_keyboard(),
            parse_mode="HTML",
        )
        return

    text = "📦 <b>Mahsulotlar ro'yxati:</b>\n\n"
    for p in products:
        profit = p.profit_per_unit
        qty_str = (
            f"{int(p.quantity)}"
            if p.quantity == p.quantity.to_integral_value()
            else f"{p.quantity:.2f}"
        )
        text += (
            f"📌 <b>{p.name}</b>\n"
            f"   💰 Sotuv: {format_money(p.selling_price)}/{p.unit}\n"
            f"   📦 Ombor: <b>{qty_str} {p.unit}</b>\n"
            f"   💚 Foyda: {format_money(profit)}/{p.unit} ({format_percentage(p.profit_margin)})\n\n"
        )

    await callback.message.answer(
        text,
        reply_markup=get_product_list_keyboard(products, action="view"),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("product_view:"))
async def product_view(callback: CallbackQuery, session: AsyncSession, user: User):
    """View single product details."""
    product_id = callback.data.split(":")[1]
    if product_id == "cancel":
        await callback.answer()
        return

    product_repo = ProductRepository(session)
    product = await product_repo.get_by_id_and_user(int(product_id), user.id)

    if not product:
        await callback.answer("❌ Mahsulot topilmadi", show_alert=True)
        return

    qty_str = (
        f"{int(product.quantity)}"
        if product.quantity == product.quantity.to_integral_value()
        else f"{product.quantity:.2f}"
    )
    text = (
        f"📦 <b>{product.name}</b>\n"
        f"{'─' * 28}\n\n"
        f"🔑 SKU: <code>{product.sku or '—'}</code>\n"
        f"💵 Tannarx: <b>{format_money(product.cost_price)}/{product.unit}</b>\n"
        f"💰 Sotuv narxi: <b>{format_money(product.selling_price)}/{product.unit}</b>\n"
        f"💚 Birlik foydasi: <b>{format_money(product.profit_per_unit)}</b>\n"
        f"📊 Foyda foizi: <b>{format_percentage(product.profit_margin)}</b>\n"
        f"📦 Omborda: <b>{qty_str} {product.unit}</b>\n"
        f"💰 Ombor qiymati: <b>{format_money(product.quantity * product.selling_price)}</b>"
    )

    await callback.answer()
    await callback.message.answer(
        text,
        reply_markup=get_product_actions_keyboard(product.id),
        parse_mode="HTML",
    )


# ============ ADD PRODUCT ============
@router.callback_query(F.data == "products:add")
async def product_add_start(callback: CallbackQuery, state: FSMContext, user: User):
    """Start adding a new product."""
    await callback.answer()
    await state.clear()
    await state.set_state(ProductAddStates.waiting_name)
    await callback.message.answer(
        "➕ <b>Yangi mahsulot qo'shish</b>\n\nMahsulot nomini kiriting:\n<i>Masalan: Futbolka Zara</i>",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML",
    )


@router.message(ProductAddStates.waiting_name)
async def product_add_name(message: Message, state: FSMContext, user: User):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("❌ Amal bekor qilindi.", reply_markup=get_main_menu(is_admin=user.is_admin))
        return

    is_valid, error = validate_text(message.text, max_length=255)
    if not is_valid:
        await message.answer(error)
        return
    await state.update_data(name=message.text.strip())
    await state.set_state(ProductAddStates.waiting_sku)
    await message.answer(
        "🔑 SKU (artikul) kiriting:\n<i>O'tkazib yuborish mumkin</i>",
        reply_markup=get_skip_keyboard(),
        parse_mode="HTML",
    )


@router.message(ProductAddStates.waiting_sku)
async def product_add_sku(message: Message, state: FSMContext, user: User):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("❌ Amal bekor qilindi.", reply_markup=get_main_menu(is_admin=user.is_admin))
        return

    text = message.text.strip()
    if text == "⏩ O'tkazib yuborish":
        await state.update_data(sku=None)
    else:
        is_valid, sku, error = validate_sku(text)
        if not is_valid:
            await message.answer(error)
            return
        await state.update_data(sku=sku)

    await state.set_state(ProductAddStates.waiting_cost_price)
    await message.answer("💵 Tannarxni kiriting (so'mda):\n<i>Masalan: 70000</i>", reply_markup=get_cancel_keyboard())


@router.message(ProductAddStates.waiting_cost_price)
async def product_add_cost(message: Message, state: FSMContext, user: User):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("❌ Amal bekor qilindi.", reply_markup=get_main_menu(is_admin=user.is_admin))
        return

    is_valid, cost, error = validate_amount(message.text)
    if not is_valid:
        await message.answer(error)
        return
    await state.update_data(cost_price=str(cost))
    await state.set_state(ProductAddStates.waiting_selling_price)
    await message.answer("💰 Sotuv narxini kiriting (so'mda):\n<i>Masalan: 120000</i>", reply_markup=get_cancel_keyboard())


@router.message(ProductAddStates.waiting_selling_price)
async def product_add_sell_price(message: Message, state: FSMContext, user: User):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("❌ Amal bekor qilindi.", reply_markup=get_main_menu(is_admin=user.is_admin))
        return

    is_valid, sell_price, error = validate_amount(message.text)
    if not is_valid:
        await message.answer(error)
        return

    data = await state.get_data()
    cost = Decimal(data["cost_price"])
    if sell_price < cost:
        await message.answer("⚠️ Diqqat: Sotuv narxi tannarxdan past kiritilmoqda.")

    await state.update_data(selling_price=str(sell_price))
    await state.set_state(ProductAddStates.waiting_quantity)
    await message.answer("📦 Boshlang'ich miqdorni kiriting:\n<i>Masalan: 50 yoki 10</i>", reply_markup=get_cancel_keyboard())


@router.message(ProductAddStates.waiting_quantity)
async def product_add_qty(message: Message, state: FSMContext, user: User):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("❌ Amal bekor qilindi.", reply_markup=get_main_menu(is_admin=user.is_admin))
        return

    is_valid, qty, error = validate_quantity(message.text)
    if not is_valid:
        await message.answer(error)
        return
    await state.update_data(quantity=str(qty))
    await state.set_state(ProductAddStates.waiting_unit)
    await message.answer(
        "📏 O'lchov birligini kiriting:\n<i>Masalan: dona, kg, metr, quti (standart: dona)</i>",
        reply_markup=get_skip_keyboard(),
        parse_mode="HTML",
    )


@router.message(ProductAddStates.waiting_unit)
async def product_add_unit(message: Message, state: FSMContext, user: User):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("❌ Amal bekor qilindi.", reply_markup=get_main_menu(is_admin=user.is_admin))
        return

    text = message.text.strip()
    unit = "dona" if text == "⏩ O'tkazib yuborish" else text[:20]
    await state.update_data(unit=unit)

    data = await state.get_data()
    cost = Decimal(data["cost_price"])
    sell = Decimal(data["selling_price"])
    qty = Decimal(data["quantity"])
    profit = sell - cost

    await state.set_state(ProductAddStates.confirming)
    await message.answer(
        f"📋 <b>Mahsulotni tasdiqlang:</b>\n\n"
        f"📦 Nomi: <b>{data['name']}</b>\n"
        f"🔑 SKU: <code>{data.get('sku') or '—'}</code>\n"
        f"💵 Tannarx: <b>{format_money(cost)}</b>\n"
        f"💰 Sotuv narxi: <b>{format_money(sell)}</b>\n"
        f"💚 Birlik foydasi: <b>{format_money(profit)}</b>\n"
        f"📦 Miqdor: <b>{qty} {unit}</b>",
        reply_markup=get_confirm_inline("product_add_confirm"),
        parse_mode="HTML",
    )


@router.callback_query(ProductAddStates.confirming, F.data.startswith("product_add_confirm:"))
async def product_add_confirm(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, user: User
):
    action = callback.data.split(":")[1]
    if action == "cancel":
        await state.clear()
        await callback.answer("❌ Bekor qilindi")
        await callback.message.answer("❌ Bekor qilindi.", reply_markup=get_main_menu(is_admin=user.is_admin))
        return

    data = await state.get_data()
    try:
        product_repo = ProductRepository(session)
        product = await product_repo.create(
            user_id=user.id,
            name=data["name"],
            sku=data.get("sku"),
            cost_price=Decimal(data["cost_price"]),
            selling_price=Decimal(data["selling_price"]),
            quantity=Decimal(data["quantity"]),
            unit=data["unit"],
        )
        await state.clear()
        await callback.answer("✅ Saqlandi!")
        await callback.message.answer(
            f"✅ <b>{product.name}</b> mahsulot qo'shildi!\n🆔 ID: <code>#{product.id}</code>",
            reply_markup=get_main_menu(is_admin=user.is_admin),
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"Product add error for user {user.id}: {e}")
        await callback.answer("❌ Xatolik", show_alert=True)
        await state.clear()


# ============ COMPLETE INTEGRATED SALES FLOW ============
@router.callback_query(F.data.startswith("product_sell:"))
@router.callback_query(F.data == "products:sell")
async def product_sell_start(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, user: User
):
    """Start unified sales flow: Customer -> Product -> Quantity -> Paid -> Debt -> Notification."""
    await callback.answer()
    await state.clear()

    # Pre-selected product if triggered from product view
    if ":" in callback.data and callback.data != "products:sell":
        product_id = int(callback.data.split(":")[1])
        await state.update_data(product_id=product_id)

    # 1. Ask for customer
    cust_svc = CustomerService(session)
    customers = await cust_svc.get_user_customers(user.id, active_only=True, limit=10)

    if customers:
        await state.set_state(ProductSellStates.selecting_customer)
        await callback.message.answer(
            "👤 <b>Mijozni tanlang:</b>\n<i>(yoki to'g'ridan-to'g'ri davom eting)</i>",
            reply_markup=get_sale_customer_choice_keyboard(customers),
            parse_mode="HTML",
        )
    else:
        # No customers yet, continue without customer
        await state.update_data(customer_id=None)
        await _prompt_product_selection(callback.message, state, session, user)


@router.callback_query(ProductSellStates.selecting_customer, F.data.startswith("sell_cust:"))
async def product_sell_customer_selected(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, user: User
):
    """Handle customer selection."""
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
    data = await state.get_data()
    if data.get("product_id"):
        await _prompt_quantity(callback.message, state, session, user, data["product_id"])
    else:
        await _prompt_product_selection(callback.message, state, session, user)


async def _prompt_product_selection(
    message: Message, state: FSMContext, session: AsyncSession, user: User
):
    """Prompt user to select a product to sell."""
    product_repo = ProductRepository(session)
    products = await product_repo.get_user_products(user.id)
    if not products:
        await state.clear()
        await message.answer(
            "📦 Omborda mahsulotlar mavjud emas.\nIltimos avval mahsulot qo'shing.",
            reply_markup=get_main_menu(is_admin=user.is_admin),
        )
        return

    await state.set_state(ProductSellStates.selecting_product)
    await message.answer(
        "📦 <b>Qaysi mahsulotni sotmoqchisiz?</b>",
        reply_markup=get_product_list_keyboard(products, action="sell_choice"),
        parse_mode="HTML",
    )


@router.callback_query(ProductSellStates.selecting_product, F.data.startswith("product_sell_choice:"))
async def product_sell_product_chosen(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, user: User
):
    action = callback.data.split(":")[1]
    if action == "cancel":
        await state.clear()
        await callback.answer("❌ Bekor qilindi")
        await callback.message.answer("❌ Sotuv bekor qilindi.", reply_markup=get_main_menu(is_admin=user.is_admin))
        return

    product_id = int(action)
    await state.update_data(product_id=product_id)
    await callback.answer()
    await _prompt_quantity(callback.message, state, session, user, product_id)


async def _prompt_quantity(
    message: Message, state: FSMContext, session: AsyncSession, user: User, product_id: int
):
    product_repo = ProductRepository(session)
    product = await product_repo.get_by_id_and_user(product_id, user.id)
    if not product:
        await state.clear()
        await message.answer("❌ Mahsulot topilmadi.")
        return

    await state.update_data(product_name=product.name, selling_price=str(product.selling_price), unit=product.unit)
    await state.set_state(ProductSellStates.waiting_quantity)

    qty_str = f"{int(product.quantity)}" if product.quantity == product.quantity.to_integral_value() else f"{product.quantity:.2f}"
    await message.answer(
        f"💰 <b>{product.name} sotish</b>\n\n"
        f"📦 Omborda mavjud: <b>{qty_str} {product.unit}</b>\n"
        f"💰 Narx: <b>{format_money(product.selling_price)}/{product.unit}</b>\n\n"
        "Sotiladigan miqdorni kiriting:",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML",
    )


@router.message(ProductSellStates.waiting_quantity)
async def product_sell_qty(
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
    product = await product_repo.get_by_id_and_user(data["product_id"], user.id)

    if qty > product.quantity:
        await message.answer(
            f"❌ Yetarli mahsulot yo'q!\n"
            f"Omborda mavjud: <b>{product.quantity} {product.unit}</b>",
            parse_mode="HTML",
        )
        return

    total = qty * product.selling_price
    await state.update_data(quantity=str(qty), total_amount=str(total))

    customer_id = data.get("customer_id")
    if customer_id:
        # Ask if full payment or partial debt
        await state.set_state(ProductSellStates.waiting_paid_amount)
        await message.answer(
            f"💰 Jami xarid summasi: <b>{format_money(total)}</b>\n\n"
            "To'lov turini tanlang yoki to'langan summani kiriting:",
            reply_markup=get_sale_payment_choice_keyboard(total),
            parse_mode="HTML",
        )
    else:
        # Anonymous sale -> full payment default
        await state.update_data(paid_amount=str(total))
        await _prompt_payment_method(message, state)


@router.callback_query(ProductSellStates.waiting_paid_amount, F.data.startswith("sell_pay:"))
async def product_sell_payment_choice(callback: CallbackQuery, state: FSMContext, user: User):
    action = callback.data.split(":")[1]
    if action == "cancel":
        await state.clear()
        await callback.answer("❌ Bekor qilindi")
        await callback.message.answer("❌ Sotuv bekor qilindi.", reply_markup=get_main_menu(is_admin=user.is_admin))
        return

    data = await state.get_data()
    total = Decimal(data["total_amount"])

    if action == "full":
        await state.update_data(paid_amount=str(total))
        await callback.answer()
        await _prompt_payment_method(callback.message, state)
    elif action == "partial":
        await callback.answer()
        await callback.message.answer(
            f"💵 <b>To'langan summani kiriting (so'mda):</b>\n"
            f"<i>Jami: {format_money(total)} (Masalan: 280000)</i>",
            reply_markup=get_cancel_keyboard(),
            parse_mode="HTML",
        )


@router.message(ProductSellStates.waiting_paid_amount)
async def product_sell_paid_text(message: Message, state: FSMContext, user: User):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("❌ Sotuv bekor qilindi.", reply_markup=get_main_menu(is_admin=user.is_admin))
        return

    is_valid, paid, error = validate_amount(message.text)
    if not is_valid:
        await message.answer(error)
        return

    data = await state.get_data()
    total = Decimal(data["total_amount"])
    if paid > total:
        await message.answer(f"❌ To'langan summa jami xarid ({format_money(total)}) dan katta bo'lishi mumkin emas.")
        return

    await state.update_data(paid_amount=str(paid))
    await _prompt_payment_method(message, state)


async def _prompt_payment_method(message: Message, state: FSMContext):
    await state.set_state(ProductSellStates.waiting_payment_method)
    await message.answer(
        "💳 <b>To'lov turini tanlang:</b>",
        reply_markup=get_payment_method_keyboard(prefix="prod_sale_pm"),
        parse_mode="HTML",
    )


@router.callback_query(ProductSellStates.waiting_payment_method, F.data.startswith("prod_sale_pm:"))
async def product_sell_pm_selected(callback: CallbackQuery, state: FSMContext, user: User):
    method = callback.data.split(":")[1]
    await state.update_data(payment_method=method)
    await callback.answer()

    await state.set_state(ProductSellStates.waiting_description)
    await callback.message.answer(
        "📝 Izoh kiriting (ixtiyoriy):\n<i>O'tkazib yuborish mumkin</i>",
        reply_markup=get_skip_keyboard(),
        parse_mode="HTML",
    )


@router.message(ProductSellStates.waiting_description)
async def product_sell_desc(
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
    total = Decimal(data["total_amount"])
    paid = Decimal(data["paid_amount"])
    qty = Decimal(data["quantity"])
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

    await state.set_state(ProductSellStates.confirming)
    text_confirm = (
        f"📋 <b>Sotuvni tasdiqlang:</b>\n\n"
        f"👤 Mijoz: <b>{cust_name}</b>\n"
        f"📦 Mahsulot: <b>{data['product_name']}</b>\n"
        f"📊 Miqdor: <b>{qty} {data.get('unit', 'dona')}</b>\n"
        f"💰 Jami summa: <b>{format_money(total)}</b>\n"
        f"💵 To'langan: <b>{format_money(paid)}</b> ({pm})\n"
    )

    if new_debt > 0:
        text_confirm += (
            f"🔴 Bugungi qarz: <b>{format_money(new_debt)}</b>\n"
            f"🔴 Oldingi qarz: <b>{format_money(old_debt)}</b>\n"
            f"🔴 <b>Jami qarz: {format_money(total_debt)}</b>\n"
        )

    text_confirm += f"📝 Izoh: <i>{desc or '—'}</i>"

    await message.answer(
        text_confirm,
        reply_markup=get_confirm_inline("product_sale_confirm"),
        parse_mode="HTML",
    )


@router.callback_query(ProductSellStates.confirming, F.data.startswith("product_sale_confirm:"))
async def product_sale_confirm_execute(
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
        finance_svc = FinanceService(session)
        qty = Decimal(data["quantity"])
        paid = Decimal(data["paid_amount"])
        pm_str = data.get("payment_method", "cash")
        pm_enum = PaymentMethod(pm_str) if pm_str in PaymentMethod._value2member_map_ else PaymentMethod.CASH
        desc = data.get("description")
        seller_name = user.full_name or "Do'kon"

        res = await finance_svc.process_complete_sale(
            user_id=user.id,
            product_id=data["product_id"],
            quantity=qty,
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
            f"{cust_line}"
            f"📦 Mahsulot: <b>{res['product'].name}</b>\n"
            f"📊 Miqdor: <b>{qty} {res['product'].unit}</b>\n"
            f"💰 Jami: <b>{format_money(res['total_amount'])}</b>\n"
            f"💵 To'landi: <b>{format_money(paid)}</b>\n"
            f"{debt_line}"
            f"📦 Qolgan qoldiq: <b>{res['product'].quantity} {res['product'].unit}</b>"
            f"{notif_badge}",
            reply_markup=get_main_menu(is_admin=user.is_admin),
            parse_mode="HTML",
        )
        logger.info(f"Complete sale executed: user={user.id} product={data['product_id']} total={res['total_amount']}")

    except ValueError as e:
        await callback.answer(str(e), show_alert=True)
    except Exception as e:
        logger.error(f"Complete sale error for user {user.id}: {e}")
        await callback.answer("❌ Xatolik yuz berdi", show_alert=True)
        await state.clear()


# ============ PRODUCT RESTOCK / PURCHASE ============
@router.callback_query(F.data.startswith("product_purchase:"))
@router.callback_query(F.data == "products:purchase")
async def product_purchase_start(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, user: User
):
    """Start restocking product."""
    await callback.answer()
    if ":" in callback.data and callback.data != "products:purchase":
        product_id = int(callback.data.split(":")[1])
        await state.update_data(product_id=product_id)
        await state.set_state(ProductPurchaseStates.waiting_quantity)
        product_repo = ProductRepository(session)
        product = await product_repo.get_by_id_and_user(product_id, user.id)
        await callback.message.answer(
            f"📦 <b>{product.name}</b> kirim qilish\n\nQo'shiladigan miqdorni kiriting:",
            reply_markup=get_cancel_keyboard(),
            parse_mode="HTML",
        )
        return

    product_repo = ProductRepository(session)
    products = await product_repo.get_user_products(user.id)
    if not products:
        await callback.message.answer("📦 Mahsulotlar ro'yxati bo'sh.")
        return

    await state.set_state(ProductPurchaseStates.selecting_product)
    await callback.message.answer(
        "📦 Qaysi mahsulotni kirim qilmoqchisiz?",
        reply_markup=get_product_list_keyboard(products, action="purchase_choice"),
    )


@router.callback_query(ProductPurchaseStates.selecting_product, F.data.startswith("product_purchase_choice:"))
async def product_purchase_chosen(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, user: User
):
    action = callback.data.split(":")[1]
    if action == "cancel":
        await state.clear()
        await callback.answer()
        return

    product_id = int(action)
    await state.update_data(product_id=product_id)
    await state.set_state(ProductPurchaseStates.waiting_quantity)
    await callback.answer()
    product_repo = ProductRepository(session)
    product = await product_repo.get_by_id_and_user(product_id, user.id)
    await callback.message.answer(
        f"📦 <b>{product.name}</b> kirim qilish\n\nQo'shiladigan miqdorni kiriting:",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML",
    )


@router.message(ProductPurchaseStates.waiting_quantity)
async def product_purchase_qty(
    message: Message, state: FSMContext, session: AsyncSession, user: User
):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("❌ Amal bekor qilindi.", reply_markup=get_main_menu(is_admin=user.is_admin))
        return

    is_valid, qty, error = validate_quantity(message.text)
    if not is_valid:
        await message.answer(error)
        return

    data = await state.get_data()
    product_svc = ProductService(session)
    updated = await product_svc.restock(
        product_id=data["product_id"],
        user_id=user.id,
        quantity=qty,
    )

    await state.clear()
    await message.answer(
        f"✅ <b>Kirim muvaffaqiyatli saqlandi!</b>\n\n"
        f"📦 {updated.name}: +{qty} {updated.unit}\n"
        f"📊 Yangi ombor qoldig'i: <b>{updated.quantity} {updated.unit}</b>",
        reply_markup=get_main_menu(is_admin=user.is_admin),
        parse_mode="HTML",
    )


# ============ DELETE PRODUCT ============
@router.callback_query(F.data.startswith("product_delete:"))
async def product_delete(callback: CallbackQuery, session: AsyncSession, user: User):
    """Delete a product."""
    product_id = int(callback.data.split(":")[1])
    product_repo = ProductRepository(session)
    product = await product_repo.get_by_id_and_user(product_id, user.id)
    if not product:
        await callback.answer("❌ Topilmadi", show_alert=True)
        return
    await product_repo.deactivate(product)
    await callback.answer("🗑 O'chirildi!")
    await callback.message.answer(f"🗑 <b>{product.name}</b> o'chirildi.", parse_mode="HTML")
