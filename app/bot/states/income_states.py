"""FSM States for income entry flow."""
from aiogram.fsm.state import State, StatesGroup


class IncomeStates(StatesGroup):
    """States for income entry wizard."""
    waiting_amount = State()         # Step 1: Enter amount
    waiting_category = State()       # Step 2: Select income type
    waiting_new_category = State()   # Step 2b: Enter new category name
    waiting_payment_method = State() # Step 3: Select payment method
    waiting_description = State()    # Step 4: Enter description (optional)
    waiting_date = State()           # Step 5: Select date
    confirming = State()             # Final: Confirm before saving
