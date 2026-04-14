from fastapi import APIRouter

from app.api.routes.attachments import router as attachments_router
from app.api.routes.auth import router as auth_router
from app.api.routes.departments import router as departments_router
from app.api.routes.health import router as health_router
from app.api.routes.hr_governance import router as hr_governance_router
from app.api.routes.profiles import router as profiles_router
from app.api.routes.tasks import router as tasks_router
from app.api.routes.users import router as users_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(auth_router, tags=["auth"])
api_router.include_router(users_router, tags=["users"])
api_router.include_router(departments_router, tags=["departments"])
api_router.include_router(profiles_router, tags=["profiles"])
api_router.include_router(hr_governance_router, tags=["hr-governance"])
api_router.include_router(tasks_router, tags=["tasks"])
api_router.include_router(attachments_router, tags=["attachments"])
