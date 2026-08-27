"""FSM States for debt management."""
from aiogram.fsm.state import State, StatesGroup


class DebtAddStates(StatesGroup):
    """States for adding a new debt."""
    waiting_type = State()
    waiting_contact_name = State()
    waiting_phone = State()
    waiting_amount = State()
    waiting_description = State()
    waiting_date = State()
    waiting_due_date = State()
    confirming = State()


class DebtPaymentStates(StatesGroup):
    """States for recording a debt payment."""
    selecting_debt = State()
    waiting_amount = State()
    waiting_date = State()
    waiting_description = State()
    confirming = State()


class ReportCustomDateStates(StatesGroup):
    """States for custom date range report."""
    waiting_start_date = State()
    waiting_end_date = State()
