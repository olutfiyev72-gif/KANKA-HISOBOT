"""FSM states for transaction editing and history."""
from aiogram.fsm.state import State, StatesGroup


class TransactionEditStates(StatesGroup):
    """States for editing an existing transaction."""
    waiting_amount = State()
    waiting_description = State()
    waiting_payment_method = State()
