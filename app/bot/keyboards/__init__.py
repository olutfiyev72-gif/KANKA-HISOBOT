"""Keyboards package init."""
from app.bot.keyboards.main_menu import get_main_menu, MAIN_MENU_BUTTONS
from app.bot.keyboards.common_kb import (
    get_cancel_keyboard, get_confirm_inline, get_back_keyboard,
    get_skip_keyboard, get_today_keyboard, remove_keyboard,
)
from app.bot.keyboards.income_kb import (
    get_income_type_keyboard, get_payment_method_keyboard,
    get_expense_category_keyboard,
)
from app.bot.keyboards.report_kb import get_report_period_keyboard, get_report_actions_keyboard
from app.bot.keyboards.products_kb import (
    get_products_menu_keyboard, get_product_list_keyboard, get_product_actions_keyboard,
)
from app.bot.keyboards.debts_kb import (
    get_debt_menu_keyboard, get_debt_list_keyboard,
    get_debt_actions_keyboard, get_debt_type_keyboard,
)

__all__ = [
    "get_main_menu", "MAIN_MENU_BUTTONS",
    "get_cancel_keyboard", "get_confirm_inline", "get_back_keyboard",
    "get_skip_keyboard", "get_today_keyboard", "remove_keyboard",
    "get_income_type_keyboard", "get_payment_method_keyboard",
    "get_expense_category_keyboard",
    "get_report_period_keyboard", "get_report_actions_keyboard",
    "get_products_menu_keyboard", "get_product_list_keyboard", "get_product_actions_keyboard",
    "get_debt_menu_keyboard", "get_debt_list_keyboard",
    "get_debt_actions_keyboard", "get_debt_type_keyboard",
]
