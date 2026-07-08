"""
Central configuration for the AgriFund platform.
All environment-dependent values (DB URL, secrets, commission rate) live here
so the rest of the codebase never hardcodes them.
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "AgriFund"

    # Default: local SQLite for easy dev/testing.
    # In production, set DATABASE_URL to a PostgreSQL URL, e.g.:
    # postgresql+psycopg2://user:password@host:5432/agrifund
    DATABASE_URL: str = "sqlite:///./agrifund.db"

    JWT_SECRET: str = "CHANGE_ME_IN_PRODUCTION"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # Revenue model
    PLATFORM_COMMISSION_PERCENT: float = 2.5  # 1-3% range, configurable

    class Config:
        env_file = ".env"


settings = Settings()
