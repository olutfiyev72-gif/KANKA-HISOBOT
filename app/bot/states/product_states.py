"""FSM States for product management."""
from aiogram.fsm.state import State, StatesGroup


class ProductAddStates(StatesGroup):
    """States for adding a new product."""
    waiting_name = State()
    waiting_sku = State()
    waiting_cost_price = State()
    waiting_selling_price = State()
    waiting_quantity = State()
    waiting_unit = State()
    confirming = State()


class ProductSellStates(StatesGroup):
    """States for selling a product with customer, stock and debt integration."""
    selecting_customer = State()
    selecting_product = State()
    waiting_quantity = State()
    waiting_paid_amount = State()
    waiting_payment_method = State()
    waiting_description = State()
    confirming = State()


class ProductPurchaseStates(StatesGroup):
    """States for purchasing/restocking a product."""
    selecting_product = State()
    waiting_quantity = State()
    waiting_price = State()
    confirming = State()


class ProductEditStates(StatesGroup):
    """States for editing a product."""
    selecting_product = State()
    selecting_field = State()
    waiting_value = State()
    confirming = State()
