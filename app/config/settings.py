"""Application settings loaded via Pydantic v2 BaseSettings."""
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Global configuration settings for TutorBot."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000

    # WhatsApp Cloud API
    WHATSAPP_API_VERSION: str = "v19.0"
    WHATSAPP_PHONE_NUMBER_ID: str = "123456789012345"
    WHATSAPP_ACCESS_TOKEN: str = "test_access_token"
    WHATSAPP_APP_SECRET: str = "test_app_secret_123456"
    WHATSAPP_VERIFY_TOKEN: str = "tutorbot_verify_token_secure"

    # Operational Modes
    DRY_RUN: bool = True

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://tutorbot:tutorbot_secret@localhost:5432/tutorbot_db"
    SYNC_DATABASE_URL: str = "postgresql://tutorbot:tutorbot_secret@localhost:5432/tutorbot_db"

    # Redis / Queue
    REDIS_URL: str = "redis://localhost:6379/0"

    # Storage (S3 / MinIO)
    S3_ENDPOINT_URL: str = "http://localhost:9000"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"
    S3_BUCKET_NAME: str = "tutorbot-documents"
    S3_REGION: str = "us-east-1"

    # LLMs
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    OPENROUTER_API_KEY: Optional[str] = None

    # Langfuse
    LANGFUSE_PUBLIC_KEY: Optional[str] = None
    LANGFUSE_SECRET_KEY: Optional[str] = None
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"
    LANGFUSE_ENABLED: bool = False

    @property
    def whatsapp_api_base_url(self) -> str:
        return f"https://graph.facebook.com/{self.WHATSAPP_API_VERSION}/{self.WHATSAPP_PHONE_NUMBER_ID}"


settings = Settings()
