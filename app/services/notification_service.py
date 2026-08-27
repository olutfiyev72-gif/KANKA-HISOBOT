"""Customer Telegram notification service."""
from decimal import Decimal
from typing import Optional
from aiogram import Bot
from loguru import logger

from app.database.models.customer import Customer
from app.utils.formatters import format_money


class NotificationService:
    """Service to deliver transaction & debt notifications to customers via Telegram."""

    @staticmethod
    async def send_sale_debt_notification(
        bot: Optional[Bot],
        customer: Customer,
        purchase_amount: Decimal,
        paid_amount: Decimal,
        new_debt: Decimal,
        old_debt: Decimal,
        total_debt: Decimal,
        seller_name: str = "Do'kon",
    ) -> bool:
        """Send automated Telegram receipt and debt accumulation notification."""
        if not bot or not customer.telegram_user_id or not customer.notifications_enabled:
            return False

        message_text = (
            "🛍 <b>Xaridingiz uchun rahmat!</b>\n\n"
            f"Xarid: <b>{format_money(purchase_amount)}</b>\n"
            f"To'langan: <b>{format_money(paid_amount)}</b>\n"
            f"Bugungi qarz: <b>{format_money(new_debt)}</b>\n"
            f"Oldingi qarz: <b>{format_money(old_debt)}</b>\n\n"
            f"🔴 <b>Jami qarz: {format_money(total_debt)}</b>\n\n"
            f"<b>{seller_name}</b>"
        )

        try:
            await bot.send_message(
                chat_id=customer.telegram_user_id,
                text=message_text,
                parse_mode="HTML",
            )
            logger.info(
                f"Sale notification sent to customer {customer.id} (tg={customer.telegram_user_id})"
            )
            return True
        except Exception as e:
            logger.warning(
                f"Failed to send sale notification to customer {customer.id} (tg={customer.telegram_user_id}): {e}"
            )
            return False

    @staticmethod
    async def send_debt_payment_notification(
        bot: Optional[Bot],
        customer: Customer,
        paid_amount: Decimal,
        old_debt: Decimal,
        remaining_debt: Decimal,
        seller_name: str = "Do'kon",
    ) -> bool:
        """Send automated Telegram debt repayment confirmation."""
        if not bot or not customer.telegram_user_id or not customer.notifications_enabled:
            return False

        status_emoji = "🟢" if remaining_debt <= Decimal("0") else "🟡"
        message_text = (
            "💵 <b>Qarz to'lovi qabul qilindi!</b>\n\n"
            f"To'langan summa: <b>{format_money(paid_amount)}</b>\n"
            f"Oldingi qarz: <b>{format_money(old_debt)}</b>\n"
            f"{status_emoji} <b>Qolgan qarz: {format_money(remaining_debt)}</b>\n\n"
            f"<b>{seller_name}</b>"
        )

        try:
            await bot.send_message(
                chat_id=customer.telegram_user_id,
                text=message_text,
                parse_mode="HTML",
            )
            logger.info(
                f"Debt payment notification sent to customer {customer.id} (tg={customer.telegram_user_id})"
            )
            return True
        except Exception as e:
            logger.warning(
                f"Failed to send debt payment notification to customer {customer.id} (tg={customer.telegram_user_id}): {e}"
            )
            return False
