import json
from functools import lru_cache
from typing import Any

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _parse_list_setting(value: Any) -> list[str]:
  if value is None:
    return []
  if isinstance(value, str):
    normalized = value.strip()
    if not normalized:
      return []
    if normalized.startswith("["):
      parsed = json.loads(normalized)
      if not isinstance(parsed, list):
        raise ValueError("列表配置必须是 JSON 数组或逗号分隔字符串。")
      return [str(item).strip() for item in parsed if str(item).strip()]
    return [item.strip() for item in normalized.split(",") if item.strip()]
  if isinstance(value, (list, tuple, set)):
    return [str(item).strip() for item in value if str(item).strip()]
  raise ValueError("列表配置必须是 JSON 数组或逗号分隔字符串。")


DEFAULT_DEVELOPMENT_CORS_ORIGINS = [
  "http://localhost:5173",
  "http://127.0.0.1:5173",
  "http://localhost:4173",
  "http://127.0.0.1:4173",
]


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
  jwt_secret_key: str
  jwt_min_secret_length: int = 32
  jwt_algorithm: str = "HS256"
  jwt_access_token_minutes: int = 30
  jwt_refresh_token_days: int = 7
  auth_refresh_cookie_name: str = "filum_refresh_token"
  auth_refresh_cookie_path: str = "/api/v1/auth"
  auth_refresh_cookie_domain: str | None = None
  auth_refresh_cookie_samesite: str = "strict"
  auth_refresh_cookie_secure: bool | None = None
  cors_allowed_origins: list[str] = Field(default_factory=list)
  cors_allowed_origin_regex: str | None = None
  cors_allow_credentials: bool = True
  cors_allowed_methods: list[str] = Field(
    default_factory=lambda: ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
  )
  cors_allowed_headers: list[str] = Field(
    default_factory=lambda: ["Authorization", "Content-Type", "X-Request-ID"]
  )
  auth_rate_limit_window_seconds: int = 60
  auth_login_rate_limit: int = 10
  auth_refresh_rate_limit: int = 20
  auth_bootstrap_rate_limit: int = 5
  redis_notification_queue: str = "notification:outbox"
  openai_api_key: str | None = None
  openai_base_url: str | None = None
  openai_chat_model: str = "gpt-5-mini"
  openai_embedding_model: str = "text-embedding-3-small"
  openai_embedding_dimensions: int = 1536
  web_push_public_key: str | None = None
  web_push_private_key: str | None = None
  web_push_subject: str = "mailto:filum@example.com"
  storage_provider: str = "local"
  storage_bucket: str = "filum-dev"
  storage_base_path: str = "./.storage"

  @field_validator(
    "cors_allowed_origins",
    "cors_allowed_methods",
    "cors_allowed_headers",
    mode="before",
  )
  @classmethod
  def _normalize_list_settings(cls, value: Any) -> list[str]:
    return _parse_list_setting(value)

  @model_validator(mode="after")
  def _validate_security_settings(self) -> "Settings":
    normalized_secret = self.jwt_secret_key.strip()
    if not normalized_secret:
      raise ValueError("JWT_SECRET_KEY 不能为空。")
    if normalized_secret == "change-me-in-production":
      raise ValueError("JWT_SECRET_KEY 不能使用默认占位值。")
    if len(normalized_secret) < self.jwt_min_secret_length:
      raise ValueError(
        f"JWT_SECRET_KEY 至少需要 {self.jwt_min_secret_length} 个字符，请使用随机高熵密钥。"
      )
    self.jwt_secret_key = normalized_secret
    normalized_cookie_name = self.auth_refresh_cookie_name.strip()
    if not normalized_cookie_name:
      raise ValueError("AUTH_REFRESH_COOKIE_NAME 不能为空。")
    self.auth_refresh_cookie_name = normalized_cookie_name
    normalized_cookie_path = self.auth_refresh_cookie_path.strip()
    if not normalized_cookie_path.startswith("/"):
      raise ValueError("AUTH_REFRESH_COOKIE_PATH 必须以 / 开头。")
    self.auth_refresh_cookie_path = normalized_cookie_path
    if self.auth_refresh_cookie_domain is not None:
      normalized_cookie_domain = self.auth_refresh_cookie_domain.strip()
      self.auth_refresh_cookie_domain = normalized_cookie_domain or None
    normalized_samesite = self.auth_refresh_cookie_samesite.strip().lower()
    if normalized_samesite not in {"lax", "strict", "none"}:
      raise ValueError("AUTH_REFRESH_COOKIE_SAMESITE 仅支持 lax、strict、none。")
    self.auth_refresh_cookie_samesite = normalized_samesite
    if self.auth_refresh_cookie_secure is None:
      self.auth_refresh_cookie_secure = self.app_env != "development"
    if self.auth_refresh_cookie_samesite == "none" and not self.auth_refresh_cookie_secure:
      raise ValueError("SameSite=None 的 refresh cookie 必须启用 Secure。")
    if self.app_env == "development" and not self.cors_allowed_origins and self.cors_allowed_origin_regex is None:
      self.cors_allowed_origins = list(DEFAULT_DEVELOPMENT_CORS_ORIGINS)
    return self


@lru_cache
def get_settings() -> Settings:
  return Settings()
