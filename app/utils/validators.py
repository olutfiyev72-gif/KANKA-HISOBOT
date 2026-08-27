"""Input validation utilities."""
import re
from decimal import Decimal, InvalidOperation
from typing import Optional, Tuple


def validate_amount(text: str) -> Tuple[bool, Optional[Decimal], str]:
    """Validate and parse amount from user input.
    
    Returns: (is_valid, amount, error_message)
    
    Accepts: "250000", "250 000", "250,000", "250.5", "250_000", "100k", "1.5m"
    """
    if not text:
        return False, None, "❌ Summa kiritilmadi"
    
    cleaned = text.strip().lower()
    
    # Check 'k' (thousand) or 'm' (million) suffix
    multiplier = Decimal("1")
    if cleaned.endswith("k") or cleaned.endswith("к"):
        cleaned = cleaned[:-1].strip()
        multiplier = Decimal("1000")
    elif cleaned.endswith("m") or cleaned.endswith("м"):
        cleaned = cleaned[:-1].strip()
        multiplier = Decimal("1000000")
        
    # Remove currency suffixes
    suffixes = ["so'm", "som", "uzs", "sum", "s"]
    for suffix in suffixes:
        if cleaned.endswith(suffix):
            cleaned = cleaned[: -len(suffix)].strip()
            
    # Clean up separators
    cleaned = cleaned.replace(" ", "").replace("_", "")
    if "," in cleaned and "." in cleaned:
        # e.g. 1,500,000.50
        cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        # e.g. 250,5 or 250,000
        parts = cleaned.split(",")
        if len(parts) == 2 and len(parts[1]) <= 2:
            cleaned = cleaned.replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    
    try:
        amount = Decimal(cleaned) * multiplier
    except (InvalidOperation, ValueError):
        return False, None, "❌ Noto'g'ri summa. Faqat raqam kiriting.\nMasalan: 250000 yoki 100k"
    
    if amount <= 0:
        return False, None, "❌ Summa 0 dan katta bo'lishi kerak"
    
    if amount > Decimal("999999999999"):  # ~1 trillion
        return False, None, "❌ Summa juda katta"
    
    return True, amount, ""


def validate_quantity(text: str) -> Tuple[bool, Optional[Decimal], str]:
    """Validate and parse quantity from user input."""
    if not text:
        return False, None, "❌ Miqdor kiritilmadi"
    
    cleaned = text.strip().replace(" ", "").replace(",", ".")
    
    try:
        qty = Decimal(cleaned)
    except InvalidOperation:
        return False, None, "❌ Noto'g'ri miqdor. Masalan: 10 yoki 2.5"
    
    if qty <= 0:
        return False, None, "❌ Miqdor 0 dan katta bo'lishi kerak"
    
    return True, qty, ""


def validate_phone(text: str) -> Tuple[bool, Optional[str], str]:
    """Validate Uzbek phone number."""
    if not text:
        return True, None, ""  # Phone is optional
    
    cleaned = re.sub(r"[\s\-\(\)]", "", text.strip())
    
    # Normalize +998901234567 or 998901234567 or 901234567
    if cleaned.startswith("+998"):
        cleaned = cleaned[1:]  # Remove +
    if cleaned.startswith("998") and len(cleaned) == 12:
        pass  # Already in correct format
    elif len(cleaned) == 9 and cleaned[0] in "369789":
        cleaned = "998" + cleaned
    
    # Validate format
    pattern = r"^998[0-9]{9}$"
    if not re.match(pattern, cleaned):
        return False, None, "❌ Noto'g'ri telefon raqam. Masalan: +998901234567"
    
    # Format nicely
    formatted = f"+{cleaned[:3]} {cleaned[3:5]} {cleaned[5:8]} {cleaned[8:10]} {cleaned[10:]}"
    return True, formatted, ""


def validate_text(text: str, max_length: int = 500, min_length: int = 1) -> Tuple[bool, str]:
    """Validate general text input."""
    if not text or not text.strip():
        return False, "❌ Matn bo'sh bo'lishi mumkin emas"
    
    stripped = text.strip()
    if len(stripped) < min_length:
        return False, f"❌ Matn kamida {min_length} ta belgi bo'lishi kerak"
    
    if len(stripped) > max_length:
        return False, f"❌ Matn {max_length} ta belgidan oshmasligi kerak"
    
    return True, ""


def validate_sku(text: str) -> Tuple[bool, Optional[str], str]:
    """Validate product SKU."""
    if not text or text.strip().lower() in ("-", "yo'q", "yoq", "skip"):
        return True, None, ""  # SKU is optional
    
    cleaned = text.strip().upper()
    if len(cleaned) > 50:
        return False, None, "❌ SKU 50 ta belgidan oshmasligi kerak"
    
    if not re.match(r"^[A-Za-z0-9\-_]+$", cleaned):
        return False, None, "❌ SKU faqat harf, raqam, - va _ dan iborat bo'lishi kerak"
    
    return True, cleaned, ""
