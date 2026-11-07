"""Application Configuration using Pydantic Settings v2"""

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ENVIRONMENT: str = Field(default="development", description="Runtime environment")
    DEBUG: bool = Field(default=False, description="Debug mode")
    APP_NAME: str = "Smart Family Budget Manager"
    APP_VERSION: str = "0.1.0"

    HOST: str = "127.0.0.1"
    PORT: int = 8000

    SECRET_KEY: str = Field(
        default="insecure-dev-secret-key-must-be-changed-in-production-0123456789abcdef",
        description="Core secret key for session hashing and cryptographic operations",
    )
    FIELD_ENCRYPTION_KEY: str = Field(
        default="insecure-dev-32-byte-aes-encryption-key-for-credentials!",
        description="32-byte key for AES-256-GCM field level encryption",
    )

    # Session & Cookie Configuration
    SESSION_COOKIE_NAME: str = "sfbm_session"
    SESSION_EXPIRE_SECONDS: int = 604800  # 7 days
    SESSION_IDLE_TIMEOUT_SECONDS: int = 7200  # 2 hours
    COOKIE_SECURE: bool = False
    COOKIE_SAME_SITE: str = "lax"

    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///:memory:",
        description="Async SQLAlchemy database URL",
    )
    DATABASE_SYNC_URL: str = Field(
        default="sqlite:///:memory:",
        description="Sync SQLAlchemy database URL for migrations",
    )

    ALLOWED_CORS_ORIGINS: str = Field(
        default="http://localhost:5173,http://localhost:3000",
        description="Comma-separated allowed CORS origins",
    )

    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL for Celery and caching",
    )

    DEFAULT_CURRENCY: str = "INR"
    DEFAULT_TIMEZONE: str = "Asia/Kolkata"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.ALLOWED_CORS_ORIGINS.split(",") if origin.strip()]

    @field_validator("ENVIRONMENT")
    @classmethod
    def validate_env(cls, v: str) -> str:
        valid_envs = {"development", "test", "production", "staging"}
        if v.lower() not in valid_envs:
            raise ValueError(f"Invalid ENVIRONMENT: {v}. Must be one of {valid_envs}")
        return v.lower()


settings = Settings()
