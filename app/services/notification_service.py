"""Customer Telegram notification service with detailed API diagnostics and error capture."""
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
    async def send_direct_test_message(
        bot: Bot,
        chat_id: int,
        test_text: str = "🔔 <b>Test xabarnoma:</b> Telegram bot xabarnoma tizimi muvaffaqiyatli ishlamoqda!",
    ) -> dict:
        """Send direct test message to verify Bot connectivity and Telegram API credentials."""
        bot_id = getattr(bot, "id", None)
        logger.info(f"🧪 [DIAGNOSTIC TEST] Attempting direct send_message to chat_id={chat_id} (bot_id={bot_id})")

        try:
            msg = await bot.send_message(
                chat_id=chat_id,
                text=test_text,
                parse_mode="HTML",
            )
            logger.info(f"✅ [DIAGNOSTIC TEST SUCCESS] Message delivered successfully. msg_id={msg.message_id}")
            return {"success": True, "message_id": msg.message_id, "error": None}
        except TelegramForbiddenError as e:
            logger.error(f"❌ [DIAGNOSTIC TEST FAILED] Bot was blocked by user ({chat_id}): {e}")
            return {"success": False, "error": f"Bot was blocked by user: {e}"}
        except TelegramBadRequest as e:
            logger.error(f"❌ [DIAGNOSTIC TEST FAILED] Bad request (chat not found / not started by user): {e}")
            return {"success": False, "error": f"Chat not found or user hasn't started bot: {e}"}
        except TelegramAPIError as e:
            logger.error(f"❌ [DIAGNOSTIC TEST FAILED] Telegram API error: {type(e).__name__} - {e}")
            return {"success": False, "error": f"Telegram API error: {e}"}
        except Exception as e:
            logger.error(f"❌ [DIAGNOSTIC TEST FAILED] Unexpected error: {type(e).__name__} - {e}")
            return {"success": False, "error": f"Unexpected error: {e}"}

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
        bot_id = getattr(bot, "id", None)
        logger.info(
            f"🔔 [NOTIFICATION AUDIT] Checking sale delivery: customer_id={customer.id} | "
            f"tg_user_id={customer.telegram_user_id} (type={type(customer.telegram_user_id).__name__}) | "
            f"notifications_enabled={customer.notifications_enabled} | "
            f"new_debt={new_debt} | total_debt={total_debt} | "
            f"bot_id={bot_id}"
        )

        if not bot:
            logger.warning("❌ [NOTIFICATION SKIPPED] Bot instance is None.")
            return False

        if not customer.telegram_user_id:
            logger.warning(
                f"❌ [NOTIFICATION SKIPPED] Customer #{customer.id} ('{customer.name}') has no telegram_user_id. "
                "Telegram API requires numeric chat_id to deliver messages."
            )
            return False

        if not customer.notifications_enabled:
            logger.warning(
                f"❌ [NOTIFICATION SKIPPED] Customer #{customer.id} has notifications_enabled=False."
            )
            return False

        try:
            tg_user_id = int(str(customer.telegram_user_id).strip())
        except (ValueError, TypeError) as e:
            logger.error(f"❌ [NOTIFICATION SKIPPED] Cannot convert telegram_user_id '{customer.telegram_user_id}' to int: {e}")
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
                f"✅ [NOTIFICATION DELIVERED] Sale debt notification successfully delivered to customer #{customer.id} (chat_id={tg_user_id})"
            )
            return True
        except TelegramForbiddenError as e:
            logger.error(
                f"❌ [NOTIFICATION FAILED] Customer #{customer.id} (tg_id={tg_user_id}) has blocked the bot: {e}"
            )
            return False
        except TelegramBadRequest as e:
            logger.error(
                f"❌ [NOTIFICATION FAILED] Telegram Bad Request for customer #{customer.id} (tg_id={tg_user_id}): {e}. "
                "(User has not started the bot or chat was not found)"
            )
            return False
        except TelegramAPIError as e:
            logger.error(
                f"❌ [NOTIFICATION FAILED] Telegram API error delivering to customer #{customer.id} (tg_id={tg_user_id}): {type(e).__name__} - {e}"
            )
            return False
        except Exception as e:
            logger.error(
                f"❌ [NOTIFICATION FAILED] Unexpected error delivering notification to customer #{customer.id} (tg_id={tg_user_id}): {type(e).__name__} - {e}"
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
        bot_id = getattr(bot, "id", None)
        logger.info(
            f"🔔 [NOTIFICATION AUDIT] Checking payment delivery: customer_id={customer.id} | "
            f"tg_user_id={customer.telegram_user_id} | notifications_enabled={customer.notifications_enabled} | "
            f"paid_amount={paid_amount} | remaining_debt={remaining_debt} | bot_id={bot_id}"
        )

        if not bot:
            logger.warning("❌ [PAYMENT NOTIFICATION SKIPPED] Bot instance is None.")
            return False

        if not customer.telegram_user_id:
            logger.warning(
                f"❌ [PAYMENT NOTIFICATION SKIPPED] Customer #{customer.id} has no telegram_user_id."
            )
            return False

        if not customer.notifications_enabled:
            logger.warning(
                f"❌ [PAYMENT NOTIFICATION SKIPPED] Customer #{customer.id} has notifications_enabled=False."
            )
            return False

        try:
            tg_user_id = int(str(customer.telegram_user_id).strip())
        except (ValueError, TypeError) as e:
            logger.error(f"❌ [PAYMENT NOTIFICATION SKIPPED] Cannot convert telegram_user_id '{customer.telegram_user_id}' to int: {e}")
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
                f"✅ [PAYMENT NOTIFICATION DELIVERED] Debt repayment notification sent to customer #{customer.id} (chat_id={tg_user_id})"
            )
            return True
        except TelegramForbiddenError as e:
            logger.error(
                f"❌ [PAYMENT NOTIFICATION FAILED] Customer #{customer.id} (tg_id={tg_user_id}) has blocked the bot: {e}"
            )
            return False
        except TelegramBadRequest as e:
            logger.error(
                f"❌ [PAYMENT NOTIFICATION FAILED] Telegram Bad Request for customer #{customer.id} (tg_id={tg_user_id}): {e}. "
                "(User has not started the bot or chat was not found)"
            )
            return False
        except TelegramAPIError as e:
            logger.error(
                f"❌ [PAYMENT NOTIFICATION FAILED] Telegram API error delivering repayment to customer #{customer.id} (tg_id={tg_user_id}): {type(e).__name__} - {e}"
            )
            return False
        except Exception as e:
            logger.error(
                f"❌ [PAYMENT NOTIFICATION FAILED] Unexpected error delivering repayment notification to customer #{customer.id} (tg_id={tg_user_id}): {type(e).__name__} - {e}"
            )
            return False
