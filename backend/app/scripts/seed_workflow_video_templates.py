from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import dispose_async_engine, get_session_factory
from app.core.enums import UserRole
from app.models import Department, User
from app.services.workflow_video_template_seed_service import (
  VIDEO_DEPARTMENT_CODES,
  WorkflowVideoTemplateSeedService,
)


async def run_seed() -> None:
  settings = get_settings()
  async with get_session_factory()() as session:
    actor = await session.scalar(select(User).where(User.role == UserRole.ADMIN).order_by(User.created_at.asc()))
    if actor is None:
      raise SystemExit("未找到管理员账号。请先运行 seed_sample_data。")

    departments = {
      department.code: department
      for department in (
        await session.scalars(select(Department).where(Department.code.in_(VIDEO_DEPARTMENT_CODES)))
      ).all()
    }
    missing = [code for code in VIDEO_DEPARTMENT_CODES if code not in departments]
    if missing:
      raise SystemExit(
        f"缺少部门：{', '.join(missing)}。请先执行：python -m app.scripts.seed_sample_data"
      )

    result = await WorkflowVideoTemplateSeedService(session).seed_templates(
      actor=actor,
      departments=departments,
    )

  print("视频工作流图模板种子已完成。")
  print(f"- 批次模板 topic_meeting_batch_v1: {result.batch_template_id}")
  print(f"- 制作模板 video_production_per_topic_v1: {result.production_template_id}")


def parse_args() -> argparse.Namespace:
  return argparse.ArgumentParser(description="写入视频工作流 v1 双图模板种子（需先 seed_sample_data）").parse_args()


async def main() -> None:
  parse_args()
  try:
    await run_seed()
  finally:
    await dispose_async_engine()


if __name__ == "__main__":
  asyncio.run(main())
