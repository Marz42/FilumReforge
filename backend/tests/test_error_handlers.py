from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.error_handlers import register_exception_handlers


def test_timeout_error_returns_service_unavailable_message() -> None:
  application = FastAPI()
  register_exception_handlers(application)

  @application.get("/timeout")
  async def raise_timeout() -> None:
    raise TimeoutError()

  client = TestClient(application)

  response = client.get("/timeout")

  assert response.status_code == 503
  assert response.json() == {
    "detail": "数据库连接超时。请先启动 PostgreSQL，再重试登录或管理员初始化。",
  }
