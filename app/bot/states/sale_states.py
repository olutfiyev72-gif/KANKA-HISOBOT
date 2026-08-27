"""FSM states for the dedicated 🛒 Sotuvlar (Sales) module."""
from aiogram.fsm.state import State, StatesGroup


class SaleWizardStates(StatesGroup):
    """States for creating a multi-product sale."""
    selecting_customer = State()
    selecting_product = State()
    waiting_quantity = State()
    basket_menu = State()
    waiting_paid_amount = State()
    waiting_payment_method = State()
    waiting_description = State()
    confirming = State()


class SaleSearchStates(StatesGroup):
    """States for searching sales."""
    waiting_query = State()
