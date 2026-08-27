"""Report handler - financial reports for different periods."""
from datetime import datetime, timedelta

import pytz
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.common_kb import get_cancel_keyboard
from app.bot.keyboards.main_menu import get_main_menu
from app.bot.keyboards.report_kb import (
    get_report_actions_keyboard,
    get_report_period_keyboard,
)
from app.bot.states.debt_states import ReportCustomDateStates
from app.database.models.user import User
from app.services.report_service import ReportService
from app.utils.formatters import (
    format_money,
    format_percentage,
    format_profit_indicator,
    get_month_name,
    parse_date_input,
)

router = Router()


def get_period_dates(period: str, user_timezone: str) -> tuple[datetime, datetime]:
    """Get start and end dates for a period string."""
    tz = pytz.timezone(user_timezone)
    now = datetime.now(tz)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = now.replace(hour=23, minute=59, second=59, microsecond=999999)

    if period == "today":
        return today_start, today_end
    elif period == "yesterday":
        yesterday = today_start - timedelta(days=1)
        return yesterday, yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)
    elif period == "week":
        return today_start - timedelta(days=7), today_end
    elif period == "month":
        return today_start - timedelta(days=30), today_end
    elif period == "this_month":
        start = today_start.replace(day=1)
        return start, today_end
    elif period == "last_month":
        first_this = today_start.replace(day=1)
        last_month_end = first_this - timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)
        return last_month_start, last_month_end.replace(hour=23, minute=59, second=59, microsecond=999999)
    else:
        return today_start, today_end


def get_period_label(period: str, user_timezone: str) -> str:
    """Get human-readable period label."""
    tz = pytz.timezone(user_timezone)
    now = datetime.now(tz)
    labels = {
        "today": "BUGUN",
        "yesterday": "KECHA",
        "week": "OXIRGI 7 KUN",
        "month": "OXIRGI 30 KUN",
        "this_month": f"{get_month_name(now.month).upper()} {now.year}",
        "last_month": "O'TGAN OY",
    }
    return labels.get(period, "TANLANGAN DAVR")


@router.message(F.text == "📊 Hisobot")
async def report_start(message: Message, state: FSMContext, user: User):
    """Show report period selection."""
    await state.clear()
    await message.answer(
        "📊 <b>Moliyaviy Hisobot</b>\n\nQaysi davr uchun hisobot kerak?",
        reply_markup=get_report_period_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("report_period:"))
async def report_period_selected(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    user: User,
):
    """Handle period selection."""
    period = callback.data.split(":")[1]

    if period == "close":
        await callback.message.delete()
        await callback.answer()
        return

    if period == "back":
        await callback.message.edit_text(
            "📊 <b>Moliyaviy Hisobot</b>\n\nQaysi davr uchun hisobot kerak?",
            reply_markup=get_report_period_keyboard(),
            parse_mode="HTML",
        )
        await callback.answer()
        return

    if period == "custom":
        await callback.answer()
        await state.set_state(ReportCustomDateStates.waiting_start_date)
        await callback.message.answer(
            "📅 Boshlanish sanasini kiriting:\n<i>Masalan: 01.08.2024 yoki 01/08/2024</i>",
            reply_markup=get_cancel_keyboard(),
            parse_mode="HTML",
        )
        return

    await callback.answer("⏳ Hisobot tayyorlanmoqda...")

    try:
        start_date, end_date = get_period_dates(period, user.timezone)
        label = get_period_label(period, user.timezone)
        report_text = await generate_report_text(session, user, start_date, end_date, label)

        await callback.message.edit_text(
            report_text,
            reply_markup=get_report_actions_keyboard(period),
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"Report generation error for user {user.id}: {e}")
        await callback.message.answer("❌ Hisobot tayyorlashda xatolik yuz berdi.")


@router.message(ReportCustomDateStates.waiting_start_date)
async def report_custom_start(message: Message, state: FSMContext, user: User):
    """Get custom start date."""
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer(
            "❌ Amal bekor qilindi.",
            reply_markup=get_main_menu(is_admin=user.is_admin),
        )
        return

    date = parse_date_input(message.text, user.timezone)
    if not date:
        await message.answer(
            "❌ Noto'g'ri sana formati. Masalan: <code>01.08.2024</code>",
            parse_mode="HTML",
        )
        return

    await state.update_data(start_date=date.isoformat())
    await state.set_state(ReportCustomDateStates.waiting_end_date)
    await message.answer(
        "📅 Tugash sanasini kiriting:\n<i>Masalan: 31.08.2024</i>",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML",
    )


@router.message(ReportCustomDateStates.waiting_end_date)
async def report_custom_end(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    user: User,
):
    """Get custom end date and generate report."""
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer(
            "❌ Amal bekor qilindi.",
            reply_markup=get_main_menu(is_admin=user.is_admin),
        )
        return

    date = parse_date_input(message.text, user.timezone)
    if not date:
        await message.answer(
            "❌ Noto'g'ri sana formati. Masalan: <code>31.08.2024</code>",
            parse_mode="HTML",
        )
        return

    data = await state.get_data()
    start_date = datetime.fromisoformat(data["start_date"])
    end_date = date.replace(hour=23, minute=59, second=59, microsecond=999999)

    if end_date < start_date:
        await message.answer(
            "❌ Tugash sanasi boshlanish sanasidan oldin bo'lishi mumkin emas."
        )
        return

    await state.clear()

    try:
        label = f"{start_date.strftime('%d.%m.%Y')} — {end_date.strftime('%d.%m.%Y')}"
        report_text = await generate_report_text(
            session, user, start_date, end_date, label
        )
        await message.answer(
            report_text,
            reply_markup=get_report_actions_keyboard("custom"),
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"Custom report error for user {user.id}: {e}")
        await message.answer("❌ Hisobot tayyorlashda xatolik yuz berdi.")


async def generate_report_text(
    session: AsyncSession,
    user: User,
    start_date: datetime,
    end_date: datetime,
    label: str,
) -> str:
    """Generate formatted text report for the given period."""
    report_svc = ReportService(session)
    report = await report_svc.get_period_report(user.id, start_date, end_date)

    profit_emoji = format_profit_indicator(report.net_profit)

    text = (
        f"📊 <b>MOLIYAVIY HISOBOT — {label}</b>\n"
        f"{'─' * 30}\n\n"
        f"💰 Jami daromad: <b>+{format_money(report.total_income)}</b>\n"
        f"💸 Jami xarajat: <b>-{format_money(report.total_expense)}</b>\n"
        f"{profit_emoji} Sof foyda:    <b>{format_money(report.net_profit)}</b>\n"
        f"📈 Rentabellik:  <b>{format_percentage(report.profit_margin_percent)}</b>\n"
    )

    if report.top_income_categories:
        text += "\n<b>💰 Daromad turlari bo'yicha:</b>\n"
        for cat in report.top_income_categories[:5]:
            icon = cat.category_icon or "💼"
            text += f"  {icon} {cat.category_name}: <b>{format_money(cat.total_amount)}</b> (<i>{cat.percentage}%</i>)\n"

    if report.top_expense_categories:
        text += "\n<b>💸 Xarajat kategoriyalari bo'yicha:</b>\n"
        for cat in report.top_expense_categories[:5]:
            icon = cat.category_icon or "📁"
            text += f"  {icon} {cat.category_name}: <b>{format_money(cat.total_amount)}</b> (<i>{cat.percentage}%</i>)\n"

    text += (
        f"\n{'─' * 30}\n"
        f"📅 Davr: {start_date.strftime('%d.%m.%Y')} — {end_date.strftime('%d.%m.%Y')}"
    )

    return text
