from fastapi import FastAPI

from app.api.error_handlers import register_exception_handlers
from app.api.router import api_router
from app.core.config import get_settings


def create_app() -> FastAPI:
  settings = get_settings()

  application = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
  )
  register_exception_handlers(application)
  application.include_router(api_router, prefix=settings.api_v1_prefix)

  @application.get("/healthz", include_in_schema=False)
  async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}

  return application


app = create_app()
