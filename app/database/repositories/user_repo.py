"""User repository."""
from datetime import datetime
from typing import List, Optional

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.user import User, UserStatus
from app.database.repositories.base_repo import BaseRepository


class UserRepository(BaseRepository[User]):
    """Repository for user operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(User, session)

    async def get_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """Get user by Telegram ID."""
        result = await self.session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()

    async def get_or_create(
        self, telegram_id: int, full_name: str, username: Optional[str] = None
    ) -> tuple[User, bool]:
        """Get existing user or create new one. Returns (user, created)."""
        user = await self.get_by_telegram_id(telegram_id)
        if user:
            # Update last active
            await self.session.execute(
                update(User)
                .where(User.telegram_id == telegram_id)
                .values(last_active_at=func.now(), full_name=full_name, username=username)
            )
            await self.session.flush()
            return user, False

        user = await self.create(
            telegram_id=telegram_id,
            full_name=full_name,
            username=username,
            status=UserStatus.PENDING,
        )
        return user, True

    async def activate_user(self, user: User) -> User:
        """Activate a pending user."""
        user.status = UserStatus.ACTIVE
        return await self.save(user)

    async def block_user(self, user: User) -> User:
        """Block a user."""
        user.status = UserStatus.BLOCKED
        return await self.save(user)

    async def get_all_pending(self) -> List[User]:
        """Get all pending users."""
        result = await self.session.execute(
            select(User).where(User.status == UserStatus.PENDING)
        )
        return list(result.scalars().all())

    async def get_all_active(self) -> List[User]:
        """Get all active users."""
        result = await self.session.execute(
            select(User).where(User.status == UserStatus.ACTIVE)
        )
        return list(result.scalars().all())

    async def count_by_status(self) -> dict:
        """Count users by status."""
        result = await self.session.execute(
            select(User.status, func.count(User.id))
            .group_by(User.status)
        )
        return {row[0]: row[1] for row in result.all()}

    async def set_admin(self, user: User, is_admin: bool = True) -> User:
        """Set admin status."""
        user.is_admin = is_admin
        return await self.save(user)

    async def update_timezone(self, user: User, timezone: str) -> User:
        """Update user timezone."""
        user.timezone = timezone
        return await self.save(user)

    async def get_stats(self) -> dict:
        """Get user statistics for admin."""
        total = await self.session.execute(select(func.count(User.id)))
        active = await self.session.execute(
            select(func.count(User.id)).where(User.status == UserStatus.ACTIVE)
        )
        pending = await self.session.execute(
            select(func.count(User.id)).where(User.status == UserStatus.PENDING)
        )
        # Active in last 7 days
        from datetime import timedelta
        from sqlalchemy import and_
        week_ago = datetime.now() - timedelta(days=7)
        recent = await self.session.execute(
            select(func.count(User.id)).where(
                and_(
                    User.last_active_at >= week_ago,
                    User.status == UserStatus.ACTIVE
                )
            )
        )
        return {
            "total": total.scalar() or 0,
            "active": active.scalar() or 0,
            "pending": pending.scalar() or 0,
            "recent_active": recent.scalar() or 0,
        }
