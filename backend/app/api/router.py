from fastapi import APIRouter

from app.api.routes.ai_router import router as ai_router_router
from app.api.routes.attachments import router as attachments_router
from app.api.routes.auth import router as auth_router
from app.api.routes.departments import router as departments_router
from app.api.routes.documents import router as documents_router
from app.api.routes.health import router as health_router
from app.api.routes.hr_governance import router as hr_governance_router
from app.api.routes.knowledge import router as knowledge_router
from app.api.routes.messages import router as messages_router
from app.api.routes.overview import router as overview_router
from app.api.routes.people_management import router as people_management_router
from app.api.routes.profiles import router as profiles_router
from app.api.routes.push_subscriptions import router as push_subscriptions_router
from app.api.routes.report_center import router as report_center_router
from app.api.routes.tasks import router as tasks_router
from app.api.routes.task_templates import router as task_templates_router
from app.api.routes.task_center import router as task_center_router
from app.api.routes.users import router as users_router
from app.api.routes.workflows import router as workflows_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(auth_router, tags=["auth"])
api_router.include_router(users_router, tags=["users"])
api_router.include_router(departments_router, tags=["departments"])
api_router.include_router(profiles_router, tags=["profiles"])
api_router.include_router(hr_governance_router, tags=["hr-governance"])
api_router.include_router(tasks_router, tags=["tasks"])
api_router.include_router(task_templates_router, tags=["task-templates"])
api_router.include_router(task_center_router, tags=["task-center"])
api_router.include_router(report_center_router, tags=["report-center"])
api_router.include_router(workflows_router, tags=["workflows"])
api_router.include_router(messages_router, tags=["messages"])
api_router.include_router(overview_router, tags=["overview"])
api_router.include_router(people_management_router, tags=["people-management"])
api_router.include_router(attachments_router, tags=["attachments"])
api_router.include_router(documents_router, tags=["documents"])
api_router.include_router(knowledge_router, tags=["knowledge"])
api_router.include_router(ai_router_router, tags=["ai"])
api_router.include_router(push_subscriptions_router, tags=["push-subscriptions"])
