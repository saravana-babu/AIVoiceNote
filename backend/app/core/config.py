import os
from typing import List, Union, Optional
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "VoiceMind AI"
    
    # JWT Settings
    SECRET_KEY: str = "super_secret_voicemind_token_signing_key_change_in_prod"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15  # Reduced from 1 week to 15 mins for security
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    
    # Database Settings
    DATABASE_URL: str = "sqlite:///./voicemind.db"
    
    # Cloudflare R2 Settings
    R2_ACCOUNT_ID: Optional[str] = None
    R2_ACCESS_KEY_ID: Optional[str] = None
    R2_SECRET_ACCESS_KEY: Optional[str] = None
    R2_BUCKET_NAME: str = "voicemind-audio"
    
    # LLM Provider Settings
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    GOOGLE_API_KEY: Optional[str] = None
    LLM_DEFAULT_PROVIDER: str = "gemini"
    LLM_DEFAULT_MODEL: Optional[str] = "gemini-2.0-flash"
    LLM_MAX_TOKENS: int = 4096
    LLM_TEMPERATURE: float = 0.3
    EMBEDDING_MODEL: str = "text-embedding-004"
    
    # CORS Origins
    BACKEND_CORS_ORIGINS: List[str] = ["*"]

    # SMTP Settings
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM_EMAIL: str = "noreply@voicemind.ai"

    # Monitoring & Feature Flags & Sentry
    SENTRY_DSN: Optional[str] = None
    ENVIRONMENT: str = "development"  # development, staging, production
    ENABLE_PROMETHEUS: bool = True
    ANALYTICS_WRITE_KEY: Optional[str] = None

    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()

# Crash on startup in production if default secret is used
if settings.ENVIRONMENT == "production" or not settings.DATABASE_URL.startswith("sqlite"):
    if settings.SECRET_KEY == "super_secret_voicemind_token_signing_key_change_in_prod":
        raise ValueError("CRITICAL SECURITY ERROR: SECRET_KEY must be changed from the default value in production.")

