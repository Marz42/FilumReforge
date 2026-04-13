from app.core.config import Settings
from app.schemas.health import HealthResponse


class HealthService:
  def __init__(self, settings: Settings) -> None:
    self._settings = settings

  def get_status(self) -> HealthResponse:
    return HealthResponse(
      status="ok",
      service=self._settings.app_name,
      phase="Phase A",
      environment=self._settings.app_env,
      version=self._settings.app_version,
    )
