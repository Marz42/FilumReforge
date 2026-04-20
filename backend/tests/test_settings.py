from app.core.config import get_settings


def test_default_settings_align_with_phase_a_baseline() -> None:
  settings = get_settings()

  assert settings.api_v1_prefix == "/api/v1"
  assert settings.storage_provider == "local"
  assert settings.redis_dsn.startswith("redis://")
  assert settings.openai_chat_model == "gpt-5-mini"
  assert settings.openai_embedding_model == "text-embedding-3-small"
  assert settings.openai_embedding_dimensions == 1536
  assert settings.web_push_subject.startswith("mailto:")
