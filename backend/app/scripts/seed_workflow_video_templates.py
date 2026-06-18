from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import dispose_async_engine, get_session_factory
from app.core.enums import UserRole
from app.models import Department, User
from app.services.workflow_video_template_seed_service import WorkflowVideoTemplateSeedService

# Keys expected by WorkflowVideoTemplateSeedService.seed_templates()
_COPYWRITING_POOL_KEY = "video-copywriting"
_VOICE_POOL_KEY = "video-voice"
_POST_POOL_KEY = "video-post"


async def _load_department_by_code(session, *, code: str) -> Department:
  department = await session.scalar(select(Department).where(Department.code == code))
  if department is None:
    raise SystemExit(f"未找到部门 code={code!r}，请先在组织管理中确认部门编码。")
  return department


async def run_seed(
  *,
  copy_dept_code: str | None,
  post_dept_code: str | None,
  voice_dept_code: str | None,
) -> None:
  _ = get_settings()
  async with get_session_factory()() as session:
    actor = await session.scalar(select(User).where(User.role == UserRole.ADMIN).order_by(User.created_at.asc()))
    if actor is None:
      raise SystemExit("未找到管理员账号。请先初始化管理员或运行 seed_sample_data。")

    if copy_dept_code and post_dept_code:
      copy_dept = await _load_department_by_code(session, code=copy_dept_code)
      post_dept = await _load_department_by_code(session, code=post_dept_code)
      voice_code = voice_dept_code or copy_dept_code
      voice_dept = await _load_department_by_code(session, code=voice_code)
      departments = {
        _COPYWRITING_POOL_KEY: copy_dept,
        _VOICE_POOL_KEY: voice_dept,
        _POST_POOL_KEY: post_dept,
      }
    else:
      demo_codes = (_COPYWRITING_POOL_KEY, _VOICE_POOL_KEY, _POST_POOL_KEY)
      departments = {
        department.code: department
        for department in (
          await session.scalars(select(Department).where(Department.code.in_(demo_codes)))
        ).all()
      }
      missing = [code for code in demo_codes if code not in departments]
      if missing:
        raise SystemExit(
          "缺少 demo 部门："
          f"{', '.join(missing)}。\n"
          "生产环境请指定现有部门编码，例如：\n"
          "  python -m app.scripts.seed_workflow_video_templates "
          "--copy-dept-code <文案部code> --post-dept-code <后期部code>\n"
          "（配音池在新版流程中未使用节点，可省略 --voice-dept-code，默认与文案部相同。）"
        )

    result = await WorkflowVideoTemplateSeedService(session).seed_templates(
      actor=actor,
      departments=departments,
    )

  print("视频工作流图模板种子已完成。")
  print(f"- 批次模板 topic_meeting_batch_v1: {result.batch_template_id}")
  print(f"- 制作模板 video_production_per_topic_v1: {result.production_template_id}")
  if copy_dept_code and post_dept_code:
    print(f"- 文案池 copywriters ← 部门 {copy_dept_code!r}")
    print(f"- 后期池 post_production ← 部门 {post_dept_code!r}")
    print(f"- 配音池 voice_over ← 部门 {(voice_dept_code or copy_dept_code)!r}（配置占位，N5 已合并至脚本作者）")


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(
    description="写入/刷新视频工作流 v1 双图模板（topic_meeting_batch_v1 + video_production_per_topic_v1）。",
  )
  parser.add_argument(
    "--copy-dept-code",
    help="文案负责人池绑定的部门 code（N1 参与人、N4/N12 文案会签经理）。多个文案部时选「主批次」那一支。",
  )
  parser.add_argument(
    "--post-dept-code",
    help="后期池绑定的部门 code（N7/N11/N12 后期主管节点）。",
  )
  parser.add_argument(
    "--voice-dept-code",
    help="配音池占位部门 code（新版 seed 无独立配音节点；默认与 --copy-dept-code 相同）。",
  )
  return parser.parse_args()


async def main() -> None:
  args = parse_args()
  if (args.copy_dept_code is None) ^ (args.post_dept_code is None):
    raise SystemExit("--copy-dept-code 与 --post-dept-code 必须同时指定。")
  try:
    await run_seed(
      copy_dept_code=args.copy_dept_code,
      post_dept_code=args.post_dept_code,
      voice_dept_code=args.voice_dept_code,
    )
  finally:
    await dispose_async_engine()


if __name__ == "__main__":
  asyncio.run(main())
