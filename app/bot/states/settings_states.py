"""FSM States for settings."""
from aiogram.fsm.state import State, StatesGroup


class SettingsStates(StatesGroup):
    """Settings flow states."""
    main = State()
    waiting_timezone = State()
    waiting_category_name = State()
    waiting_category_type = State()
