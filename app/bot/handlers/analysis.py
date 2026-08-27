"""Analysis handler - business analytics."""
from datetime import datetime, timedelta

import pytz
from aiogram import F, Router
from aiogram.types import Message, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.transaction import TransactionType
from app.database.models.user import User
from app.database.repositories.product_repo import ProductRepository
from app.database.repositories.transaction_repo import TransactionRepository
from app.utils.formatters import format_money, format_percentage, format_profit_indicator

router = Router()


def get_analysis_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📅 Bu oy", callback_data="analysis:this_month")
    builder.button(text="📆 O'tgan oy", callback_data="analysis:last_month")
    builder.button(text="🔙 Yopish", callback_data="analysis:close")
    builder.adjust(2, 1)
    return builder.as_markup()


@router.message(F.text == "📈 Tahlil")
async def analysis_start(message: Message, session: AsyncSession, user: User):
    """Show business analytics."""
    tz = pytz.timezone(user.timezone)
    now = datetime.now(tz)
    
    # This month
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end = now

    try:
        tx_repo = TransactionRepository(session)
        product_repo = ProductRepository(session)

        summary = await tx_repo.get_summary(user.id, start, end)
        
        # Daily average
        days_elapsed = max((now - start).days + 1, 1)
        daily_avg = summary["income"] / days_elapsed if days_elapsed > 0 else 0

        # Category analytics
        expense_by_cat = await tx_repo.get_by_category(
            user.id, start, end, TransactionType.EXPENSE
        )
        income_by_cat = await tx_repo.get_by_category(
            user.id, start, end, TransactionType.INCOME
        )
        
        # Best sellers
        best_sellers = await product_repo.get_best_sellers(user.id, limit=3)
        
        # Most profitable
        most_profitable = await product_repo.get_most_profitable(user.id, limit=3)

        profit_emoji = format_profit_indicator(summary["profit"])
        month_name = ["Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
                      "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr"][now.month - 1]

        text = (
            f"📈 <b>TAHLIL — {month_name.upper()} {now.year}</b>\n"
            f"{'─' * 28}\n\n"
            f"💰 Daromad: <b>{format_money(summary['income'])}</b>\n"
            f"💸 Xarajat: <b>{format_money(summary['expense'])}</b>\n"
            f"{profit_emoji} Sof foyda: <b>{format_money(summary['profit'])}</b>\n"
            f"📊 Foyda marjasi: <b>{format_percentage(summary['margin'])}</b>\n"
            f"📅 Kunlik o'rtacha: <b>{format_money(daily_avg)}</b>\n"
        )

        if income_by_cat:
            top_income = income_by_cat[0]
            text += (
                f"\n💰 <b>Eng yaxshi daromad:</b>\n"
                f"   {top_income.icon or '📌'} {top_income.name or 'Noaniq'}: "
                f"{format_money(top_income.total)}\n"
            )

        if expense_by_cat:
            top_expense = expense_by_cat[0]
            text += (
                f"\n💸 <b>Eng katta xarajat:</b>\n"
                f"   {top_expense.icon or '📌'} {top_expense.name or 'Noaniq'}: "
                f"{format_money(top_expense.total)}\n"
            )

        if best_sellers:
            text += "\n🏆 <b>Ko'p sotiladigan mahsulotlar:</b>\n"
            for i, item in enumerate(best_sellers, 1):
                text += f"   {i}. {item.name}: {item.total_sold:.0f} dona\n"

        if most_profitable:
            text += "\n💚 <b>Eng foydali mahsulotlar:</b>\n"
            for p in most_profitable:
                text += (
                    f"   📦 {p.name}: {format_money(p.profit_per_unit)}/dona "
                    f"({format_percentage(p.profit_margin)})\n"
                )

        if expense_by_cat:
            total_exp = summary["expense"]
            text += "\n📊 <b>Xarajatlar taqsimoti:</b>\n"
            for row in expense_by_cat[:5]:
                if total_exp > 0:
                    from decimal import Decimal
                    pct = (row.total / total_exp * 100).quantize(Decimal("0.1"))
                    text += f"   {row.icon or '📁'} {row.name or 'Noaniq'}: {pct}%\n"

        text += f"\n{'─' * 28}\n📅 {start.strftime('%d.%m')} — {end.strftime('%d.%m.%Y')}"

        await message.answer(text, reply_markup=get_analysis_keyboard(), parse_mode="HTML")

    except Exception as e:
        logger.error(f"Analysis error for user {user.id}: {e}")
        await message.answer("❌ Tahlil yuklashda xatolik yuz berdi.")
