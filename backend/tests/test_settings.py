import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings


def test_default_settings_align_with_phase_a_baseline() -> None:
  settings = get_settings()

  assert settings.api_v1_prefix == "/api/v1"
  assert settings.jwt_secret_key == "test-jwt-secret-key-for-suite-123456"
  assert settings.storage_provider == "local"
  assert settings.redis_dsn.startswith("redis://")
  assert "http://127.0.0.1:5173" in settings.cors_allowed_origins
  assert settings.cors_allow_credentials is True
  assert settings.auth_refresh_cookie_name == "filum_refresh_token"
  assert settings.auth_refresh_cookie_samesite == "strict"
  assert settings.auth_refresh_cookie_secure is False
  assert settings.auth_invitation_expiry_hours == 72
  assert settings.frontend_app_url == "http://localhost:5173"
  assert settings.workflow_graph_engine_enabled is True
  assert settings.task_center_v2_enabled is False
  assert settings.workflow_wait_any_enabled is False
  assert settings.workflow_deep_rejection_enabled is False
  assert settings.openai_chat_model == "gpt-5-mini"
  assert settings.openai_embedding_model == "text-embedding-3-small"
  assert settings.openai_embedding_dimensions == 1536
  assert settings.web_push_subject.startswith("mailto:")


def test_settings_require_explicit_non_placeholder_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.delenv("JWT_SECRET_KEY", raising=False)

  with pytest.raises(ValidationError):
    Settings()

  with pytest.raises(ValidationError):
    Settings(jwt_secret_key="change-me-in-production")

  with pytest.raises(ValidationError):
    Settings(jwt_secret_key="too-short")


def test_settings_parse_cors_lists_from_csv() -> None:
  settings = Settings(
    jwt_secret_key="test-jwt-secret-key-for-suite-123456",
    cors_allowed_origins="https://app.example.com, https://ops.example.com",
    cors_allowed_headers="Authorization, Content-Type",
  )

  assert settings.cors_allowed_origins == ["https://app.example.com", "https://ops.example.com"]
  assert settings.cors_allowed_headers == ["Authorization", "Content-Type"]


def test_settings_parse_cors_lists_from_dotenv_csv(tmp_path: pytest.TempPathFactory) -> None:
  env_file = tmp_path / ".env"
  env_file.write_text(
    "\n".join(
      [
        "JWT_SECRET_KEY=test-jwt-secret-key-for-suite-123456",
        "CORS_ALLOWED_ORIGINS=https://app.example.com, https://ops.example.com",
        "CORS_ALLOWED_HEADERS=Authorization, Content-Type",
      ]
    ),
    encoding="utf-8",
  )

  settings = Settings(_env_file=env_file)

  assert settings.cors_allowed_origins == ["https://app.example.com", "https://ops.example.com"]
  assert settings.cors_allowed_headers == ["Authorization", "Content-Type"]


def test_settings_parse_workflow_feature_flags() -> None:
  settings = Settings(
    jwt_secret_key="test-jwt-secret-key-for-suite-123456",
    workflow_graph_engine_enabled=True,
    task_center_v2_enabled=True,
    workflow_wait_any_enabled=True,
    workflow_deep_rejection_enabled=True,
  )

  assert settings.workflow_graph_engine_enabled is True
  assert settings.task_center_v2_enabled is True
  assert settings.workflow_wait_any_enabled is True
  assert settings.workflow_deep_rejection_enabled is True


def test_production_settings_do_not_fall_back_to_local_dev_cors_defaults() -> None:
  settings = Settings(
    _env_file=None,
    app_env="production",
    jwt_secret_key="test-jwt-secret-key-for-suite-123456",
  )

  assert settings.cors_allowed_origins == []
  assert settings.auth_refresh_cookie_secure is True


def test_settings_validate_refresh_cookie_options() -> None:
  with pytest.raises(ValidationError):
    Settings(
      jwt_secret_key="test-jwt-secret-key-for-suite-123456",
      auth_refresh_cookie_samesite="invalid",
    )

  with pytest.raises(ValidationError):
    Settings(
      jwt_secret_key="test-jwt-secret-key-for-suite-123456",
      auth_refresh_cookie_samesite="none",
      auth_refresh_cookie_secure=False,
    )


def test_settings_validate_invitation_options() -> None:
  with pytest.raises(ValidationError):
    Settings(
      jwt_secret_key="test-jwt-secret-key-for-suite-123456",
      auth_invitation_expiry_hours=0,
    )

  with pytest.raises(ValidationError):
    Settings(
      jwt_secret_key="test-jwt-secret-key-for-suite-123456",
      frontend_app_url="frontend.local",
    )
