"""Quick entry parser for natural language inputs like '+250000 savdo' or '-80000 reklama'."""
import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from app.database.models.transaction import TransactionType


@dataclass
class QuickEntry:
    """Parsed quick entry result."""
    type: TransactionType
    amount: Decimal
    description: Optional[str]
    raw_text: str


# Common income keywords
INCOME_KEYWORDS = {
    "savdo", "sotuv", "sotish", "kirim", "daromad", "tushum",
    "ish", "xizmat", "order", "buyurtma", "pul", "marketplace",
    "uzum", "oldi", "sotdi",
}

# Common expense keywords
EXPENSE_KEYWORDS = {
    "xarajat", "chiqim", "harida", "xarid", "sotib", "reklama",
    "ijara", "ish haqi", "maosh", "soliq", "komissiya", "yetkazish",
    "qadoq", "transport", "elektr", "gaz", "internet", "telefon",
}


def parse_quick_entry(text: str) -> Optional[QuickEntry]:
    """Parse natural language quick entry.
    
    Formats:
        +250000 savdo
        -80000 reklama  
        +250 000 so'm savdo
        250000 savdo (assumes income)
        
    Returns QuickEntry or None if not parseable.
    """
    text = text.strip()
    if not text:
        return None
    
    # Pattern: optional sign, amount, optional description
    # Handles: +250000, -250 000, 250,000, 250_000, +250k
    pattern = r"^([+-]?)\s*([0-9][0-9\s,._]*[kKmM]?)\s*(.*)$"
    match = re.match(pattern, text)
    
    if not match:
        return None
    
    sign_str, amount_str, description = match.groups()
    
    # Clean amount
    amount_str = amount_str.strip()
    multiplier = Decimal("1")
    if amount_str.lower().endswith("k"):
        multiplier = Decimal("1000")
        amount_str = amount_str[:-1]
    elif amount_str.lower().endswith("m"):
        multiplier = Decimal("1000000")
        amount_str = amount_str[:-1]

    amount_str = re.sub(r"[\s,_]", "", amount_str)
    
    try:
        amount = Decimal(amount_str) * multiplier
    except Exception:
        return None
    
    if amount <= 0:
        return None
    
    # Clean description
    description = description.strip()
    # Remove leading currency markers if present in description
    description = re.sub(r"^(so'?m|som|uzs|sum)\s*", "", description, flags=re.IGNORECASE).strip()
    
    if sign_str == "+":
        tx_type = TransactionType.INCOME
    elif sign_str == "-":
        tx_type = TransactionType.EXPENSE
    else:
        # Infer from description keywords
        desc_lower = description.lower()
        if any(kw in desc_lower for kw in EXPENSE_KEYWORDS):
            tx_type = TransactionType.EXPENSE
        else:
            # Default to income if no clear signal
            tx_type = TransactionType.INCOME
    
    return QuickEntry(
        type=tx_type,
        amount=amount,
        description=description if description else None,
        raw_text=text,
    )


def is_quick_entry(text: str) -> bool:
    """Check if text looks like a quick entry."""
    text = text.strip()
    if not text:
        return False
    if text[0] in ("+", "-"):
        rest = text[1:].lstrip()
        return len(rest) > 0 and rest[0].isdigit()
    return text[0].isdigit()
