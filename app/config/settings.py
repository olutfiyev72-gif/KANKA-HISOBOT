"""Application configuration using pydantic-settings."""
from functools import lru_cache
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Bot
    bot_token: str = ""
    bot_name: str = "Biznes Hisob Bot"

    # Database
    database_url: str = "sqlite+aiosqlite:///biznes_bot.db"

    # Supabase (optional)
    supabase_url: str = ""
    supabase_key: str = ""

    # Admin
    admin_ids: str = ""

    # App
    environment: str = "development"
    default_timezone: str = "Asia/Tashkent"

    # Logging
    log_level: str = "INFO"
    log_file: str = "logs/bot.log"

    # Rate limiting
    throttle_rate: float = 0.5

    @field_validator("database_url", mode="before")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Ensure asyncpg driver is used for PostgreSQL or fallback to sqlite."""
        if not v:
            return "sqlite+aiosqlite:///biznes_bot.db"
        if v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql+asyncpg://", 1)
        return v

    def get_admin_ids(self) -> List[int]:
        """Parse admin IDs from comma-separated string."""
        if not self.admin_ids:
            return []
        return [int(id_.strip()) for id_ in self.admin_ids.split(",") if id_.strip()]

    @property
    def is_development(self) -> bool:
        return self.environment.lower() == "development"

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
