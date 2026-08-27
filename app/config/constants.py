"""Business and system-wide constants and enums."""
from enum import Enum


class UserRole(str, Enum):
    """User access control roles."""
    OWNER = "owner"
    ADMIN = "admin"
    MANAGER = "manager"
    VIEWER = "viewer"


class TransactionType(str, Enum):
    """Type of financial transactions."""
    INCOME = "income"
    EXPENSE = "expense"
    TRANSFER = "transfer"


class PaymentMethod(str, Enum):
    """Payment channels."""
    CASH = "cash"
    CARD = "card"
    BANK = "bank"
    OTHER = "other"


class DebtType(str, Enum):
    """Type of debt."""
    RECEIVABLE = "receivable"  # Bizga berishlari kerak (Nasiya berdik)
    PAYABLE = "payable"        # Biz berishimiz kerak (Qarz oldik)


class DebtStatus(str, Enum):
    """Lifecycle status of a debt."""
    ACTIVE = "active"
    PARTIAL = "partial"
    PAID = "paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"


class InventoryAction(str, Enum):
    """Stock movement actions."""
    RESTOCK = "restock"
    SALE = "sale"
    WRITE_OFF = "write_off"
    RETURN = "return"
    ADJUSTMENT = "adjustment"


class ExportFormat(str, Enum):
    """Supported export file formats."""
    EXCEL = "excel"
    PDF = "pdf"
    CSV = "csv"


class SupportedMarketplace(str, Enum):
    """E-commerce & Marketplace platforms."""
    UZUM = "uzum"
    WILDBERRIES = "wildberries"
    YANDEX_MARKET = "yandex_market"
    TELEGRAM_SHOP = "telegram_shop"
