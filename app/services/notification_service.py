"""Customer Telegram notification service."""
from decimal import Decimal
from typing import Optional
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest, TelegramForbiddenError
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
        """Send automated Telegram receipt and debt accumulation notification after successful DB commit."""
        if not bot:
            logger.debug("Notification skipped: bot instance is None")
            return False

        if not customer.telegram_user_id:
            logger.debug(f"Notification skipped: customer #{customer.id} has no telegram_user_id")
            return False

        if not customer.notifications_enabled:
            logger.debug(f"Notification skipped: customer #{customer.id} notifications_enabled=False")
            return False

        if new_debt <= Decimal("0") and total_debt <= Decimal("0"):
            logger.debug(f"Notification skipped: customer #{customer.id} has no outstanding debt")
            return False

        try:
            tg_user_id = int(str(customer.telegram_user_id).strip())
        except (ValueError, TypeError):
            logger.warning(f"Invalid telegram_user_id for customer #{customer.id}: {customer.telegram_user_id}")
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
                chat_id=tg_user_id,
                text=message_text,
                parse_mode="HTML",
            )
            logger.info(
                f"✅ Sale debt notification sent to customer #{customer.id} (tg_id={tg_user_id})"
            )
            return True
        except TelegramForbiddenError as e:
            logger.warning(
                f"Customer #{customer.id} (tg_id={tg_user_id}) has blocked the bot: {e}"
            )
            return False
        except TelegramBadRequest as e:
            logger.warning(
                f"Customer #{customer.id} (tg_id={tg_user_id}) Telegram bad request (chat not found / not started): {e}"
            )
            return False
        except TelegramAPIError as e:
            logger.warning(
                f"Telegram API error delivering to customer #{customer.id} (tg_id={tg_user_id}): {e}"
            )
            return False
        except Exception as e:
            logger.error(
                f"Unexpected error delivering notification to customer #{customer.id}: {type(e).__name__} - {e}"
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
        """Send automated Telegram debt repayment confirmation after successful DB commit."""
        if not bot:
            logger.debug("Payment notification skipped: bot instance is None")
            return False

        if not customer.telegram_user_id:
            logger.debug(f"Payment notification skipped: customer #{customer.id} has no telegram_user_id")
            return False

        if not customer.notifications_enabled:
            logger.debug(f"Payment notification skipped: customer #{customer.id} notifications_enabled=False")
            return False

        try:
            tg_user_id = int(str(customer.telegram_user_id).strip())
        except (ValueError, TypeError):
            logger.warning(f"Invalid telegram_user_id for customer #{customer.id}: {customer.telegram_user_id}")
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
                chat_id=tg_user_id,
                text=message_text,
                parse_mode="HTML",
            )
            logger.info(
                f"✅ Debt payment notification sent to customer #{customer.id} (tg_id={tg_user_id})"
            )
            return True
        except TelegramForbiddenError as e:
            logger.warning(
                f"Customer #{customer.id} (tg_id={tg_user_id}) has blocked the bot: {e}"
            )
            return False
        except TelegramBadRequest as e:
            logger.warning(
                f"Customer #{customer.id} (tg_id={tg_user_id}) Telegram bad request (chat not found / not started): {e}"
            )
            return False
        except TelegramAPIError as e:
            logger.warning(
                f"Telegram API error delivering repayment to customer #{customer.id} (tg_id={tg_user_id}): {e}"
            )
            return False
        except Exception as e:
            logger.error(
                f"Unexpected error delivering repayment notification to customer #{customer.id}: {type(e).__name__} - {e}"
            )
            return False
