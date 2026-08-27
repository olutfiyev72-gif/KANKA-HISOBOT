"""Database seeder - inserts default categories."""
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.category import CategoryType, TransactionCategory


DEFAULT_INCOME_CATEGORIES = [
    {"name": "Mahsulot savdosi", "icon": "🛒", "is_default": True},
    {"name": "Xizmat", "icon": "🔧", "is_default": True},
    {"name": "Marketplace", "icon": "🌐", "is_default": True},
    {"name": "Boshqa", "icon": "📋", "is_default": True},
]

DEFAULT_EXPENSE_CATEGORIES = [
    {"name": "Mahsulot xaridi", "icon": "🛒", "is_default": True},
    {"name": "Reklama", "icon": "📢", "is_default": True},
    {"name": "Yetkazib berish", "icon": "🚚", "is_default": True},
    {"name": "Qadoqlash", "icon": "📦", "is_default": True},
    {"name": "Ijara", "icon": "🏢", "is_default": True},
    {"name": "Ish haqi", "icon": "👷", "is_default": True},
    {"name": "Soliq", "icon": "🏛", "is_default": True},
    {"name": "Komissiya", "icon": "💱", "is_default": True},
    {"name": "Boshqa", "icon": "📋", "is_default": True},
]


async def seed_categories(session: AsyncSession) -> None:
    """Insert default categories if they don't exist."""
    from sqlalchemy import select

    # Check if already seeded
    result = await session.execute(
        select(TransactionCategory).where(
            TransactionCategory.user_id.is_(None),
            TransactionCategory.is_default.is_(True),
        ).limit(1)
    )
    if result.scalar_one_or_none():
        return  # Already seeded

    for cat_data in DEFAULT_INCOME_CATEGORIES:
        cat = TransactionCategory(
            user_id=None,
            type=CategoryType.INCOME,
            **cat_data,
        )
        session.add(cat)

    for cat_data in DEFAULT_EXPENSE_CATEGORIES:
        cat = TransactionCategory(
            user_id=None,
            type=CategoryType.EXPENSE,
            **cat_data,
        )
        session.add(cat)

    await session.commit()
