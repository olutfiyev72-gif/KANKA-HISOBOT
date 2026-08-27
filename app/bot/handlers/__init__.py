"""Handlers package init - registers all routers."""
from aiogram import Router

from app.bot.handlers import (
    admin,
    analysis,
    cash,
    customers,
    debts,
    expense,
    history,
    income,
    products,
    quick_entry,
    report,
    sales,
    settings,
    start,
)

# Explicit router names for clear logging and debugging
start.router.name = "Start/Menu"
admin.router.name = "Admin"
income.router.name = "Daromad (Income)"
expense.router.name = "Xarajat (Expense)"
sales.router.name = "Sotuvlar (Sales)"
report.router.name = "Hisobot (Reports)"
cash.router.name = "Kassa (Cash)"
products.router.name = "Mahsulotlar (Products)"
customers.router.name = "Mijozlar (CRM)"
debts.router.name = "Qarzdorlik (Debts)"
analysis.router.name = "Tahlil (Analytics)"
settings.router.name = "Sozlamalar (Settings)"
history.router.name = "Tarix (History)"
quick_entry.router.name = "Tezkor Yozuv (Quick Entry)"


def get_all_routers() -> list[Router]:
    """Return all routers in priority order."""
    return [
        start.router,
        admin.router,        # Admin before quick_entry to avoid conflicts
        income.router,
        expense.router,
        sales.router,
        report.router,
        cash.router,
        products.router,
        customers.router,
        debts.router,
        analysis.router,
        settings.router,
        history.router,
        quick_entry.router,  # Must be last - catches any text
    ]
