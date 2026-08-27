"""Database base configuration and session management."""
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


# Module-level variables (lazily initialized)
_engine: Optional[AsyncEngine] = None
_session_maker: Optional[async_sessionmaker] = None


def get_engine() -> AsyncEngine:
    """Get or create the async engine."""
    global _engine
    if _engine is None:
        from app.config import settings
        _engine = create_async_engine(
            settings.database_url,
            echo=settings.is_development,
            pool_pre_ping=True,
        )
    return _engine


def get_session_maker() -> async_sessionmaker:
    """Get or create the session maker."""
    global _session_maker
    if _session_maker is None:
        _session_maker = async_sessionmaker(
            get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_maker


# Convenience accessor (lazy)
class _LazySessionMaker:
    """Proxy that lazily creates the session maker."""
    def __call__(self, *args, **kwargs):
        return get_session_maker()(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(get_session_maker(), name)


async_session_maker = _LazySessionMaker()


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get database session."""
    async with get_session_maker()() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def create_tables() -> None:
    """Create all tables and auto-migrate missing columns."""
    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        def _migrate_schema(sync_conn):
            dialect = sync_conn.dialect.name
            if dialect == "sqlite":
                try:
                    res_tx = sync_conn.exec_driver_sql("PRAGMA table_info(transactions)").fetchall()
                    if res_tx:
                        cols_tx = {row[1] for row in res_tx}
                        if "customer_id" not in cols_tx:
                            sync_conn.exec_driver_sql(
                                "ALTER TABLE transactions ADD COLUMN customer_id INTEGER REFERENCES customers(id) ON DELETE SET NULL"
                            )
                    res_debts = sync_conn.exec_driver_sql("PRAGMA table_info(debts)").fetchall()
                    if res_debts:
                        cols_debts = {row[1] for row in res_debts}
                        if "customer_id" not in cols_debts:
                            sync_conn.exec_driver_sql(
                                "ALTER TABLE debts ADD COLUMN customer_id INTEGER REFERENCES customers(id) ON DELETE SET NULL"
                            )
                except Exception:
                    pass
            elif dialect == "postgresql":
                try:
                    sync_conn.exec_driver_sql(
                        "ALTER TABLE transactions ADD COLUMN IF NOT EXISTS customer_id INTEGER REFERENCES customers(id) ON DELETE SET NULL;"
                    )
                    sync_conn.exec_driver_sql(
                        "ALTER TABLE debts ADD COLUMN IF NOT EXISTS customer_id INTEGER REFERENCES customers(id) ON DELETE SET NULL;"
                    )
                except Exception:
                    pass

        await conn.run_sync(_migrate_schema)


async def drop_tables() -> None:
    """Drop all tables (for testing)."""
    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

