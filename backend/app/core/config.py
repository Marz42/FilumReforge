from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
  model_config = SettingsConfigDict(
    env_file=".env",
    env_file_encoding="utf-8",
    extra="ignore",
  )

  app_name: str = "Project Filum API"
  app_env: str = "development"
  app_version: str = "0.1.0"
  api_v1_prefix: str = "/api/v1"
  postgres_dsn: str = "postgresql+asyncpg://filum:filum@localhost:5432/filum"
  redis_dsn: str = "redis://localhost:6379/0"
  jwt_secret_key: str = "change-me-in-production"
  jwt_algorithm: str = "HS256"
  jwt_access_token_minutes: int = 30
  jwt_refresh_token_days: int = 7
  redis_notification_queue: str = "notification:outbox"
  openai_api_key: str | None = None
  openai_base_url: str | None = None
  storage_provider: str = "local"
  storage_bucket: str = "filum-dev"
  storage_base_path: str = "./.storage"


@lru_cache
def get_settings() -> Settings:
  return Settings()
