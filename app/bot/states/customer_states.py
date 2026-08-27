"""FSM states for Customer CRM module."""
from aiogram.fsm.state import State, StatesGroup


class CustomerAddStates(StatesGroup):
    """States for adding a new customer."""
    waiting_name = State()
    waiting_phone = State()
    waiting_tg_username = State()
    waiting_tg_user_id = State()
    confirming = State()


class CustomerEditStates(StatesGroup):
    """States for editing a customer."""
    selecting_field = State()
    waiting_name = State()
    waiting_phone = State()
    waiting_tg_username = State()
    waiting_tg_user_id = State()


class CustomerSearchStates(StatesGroup):
    """States for customer search."""
    waiting_query = State()


class CustomerSaleStates(StatesGroup):
    """States for recording a sale with customer and partial payment/debt."""
    selecting_customer = State()
    waiting_total_amount = State()
    waiting_paid_amount = State()
    waiting_payment_method = State()
    waiting_description = State()
    confirming = State()


class CustomerDebtPaymentStates(StatesGroup):
    """States for customer debt repayment."""
    waiting_amount = State()
    waiting_payment_method = State()
    waiting_description = State()
    confirming = State()
