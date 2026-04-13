from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.schemas.health import HealthResponse
from app.services.health_service import HealthService

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def read_health(settings: Settings = Depends(get_settings)) -> HealthResponse:
  service = HealthService(settings)
  return service.get_status()
