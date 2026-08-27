"""Test configuration and fixtures."""
import asyncio
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.database.base import Base
from app.database.models import User, UserStatus
from app.database.seeder import seed_categories

# Use in-memory SQLite for tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for session scope."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def engine():
    """Create test database engine per test for complete isolation."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def session(engine) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session with seed categories."""
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    async with session_maker() as session:
        await seed_categories(session)
        yield session
        await session.close()


@pytest_asyncio.fixture
async def test_user(session: AsyncSession) -> User:
    """Create a test user."""
    user = User(
        telegram_id=123456789,
        full_name="Test User",
        username="testuser",
        status=UserStatus.ACTIVE,
        timezone="Asia/Tashkent",
    )
    session.add(user)
    await session.commit()
    return user


@pytest_asyncio.fixture
async def test_user_2(session: AsyncSession) -> User:
    """Create a second test user for isolation testing."""
    user = User(
        telegram_id=987654321,
        full_name="Test User 2",
        username="testuser2",
        status=UserStatus.ACTIVE,
        timezone="Asia/Tashkent",
    )
    session.add(user)
    await session.commit()
    return user
