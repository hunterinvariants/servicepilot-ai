from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    secret_key: str = "development-only-change-me"
    database_url: str = "sqlite:///./servicepilot.db"
    redis_url: str = "redis://localhost:6379/0"
    ai_provider: str = "mock"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4.1-mini"
    public_url: str = "http://localhost:8000"
    admin_email: str = "admin@servicepilot.local"
    admin_password: str = "change-me-now"
    api_key: str = "sp_demo_change_me"
    webhook_signing_secret: str = "development-webhook-secret"
    rate_limit_per_minute: int = 60
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    webhook_url: str = ""
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
