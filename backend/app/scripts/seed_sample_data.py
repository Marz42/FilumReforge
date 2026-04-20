from __future__ import annotations

import argparse
import asyncio

from app.core.config import get_settings
from app.core.database import dispose_async_engine, get_session_factory
from app.services.sample_data_service import SampleDataService


async def run_seed(*, password: str) -> None:
  settings = get_settings()
  async with get_session_factory()() as session:
    result = await SampleDataService(session, settings).seed_manual_test_workspace(
      default_password=password,
    )

  print("测试工作台数据已准备完成。")
  if result.admin_bootstrapped:
    print(f"- 已初始化管理员账号：{result.admin_email}")
  else:
    print(f"- 复用现有管理员账号：{result.admin_email}")
  print(f"- 所有 demo 账号统一密码：{result.default_password}")
  print("- 已准备部门：")
  for department_code in result.departments:
    print(f"  - {department_code}")
  print("- 已准备 demo 账号：")
  for account in result.accounts:
    print(
      f"  - {account.email} | {account.real_name} | {account.role.value} | "
      f"{account.status.value} | {account.department_code} | {account.job_title}"
    )


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="生成 Project Filum 本地测试组织与账号数据。")
  parser.add_argument(
    "--password",
    default="FilumTest123!",
    help="所有 demo 账号统一使用的密码，默认值为 FilumTest123!。",
  )
  return parser.parse_args()


async def main() -> None:
  args = parse_args()
  try:
    await run_seed(password=args.password)
  finally:
    await dispose_async_engine()


if __name__ == "__main__":
  asyncio.run(main())
