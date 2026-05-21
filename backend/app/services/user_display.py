from __future__ import annotations

from app.models import User


def user_display_label(user: User | None) -> str:
  if user is None:
    return "未知用户"
  if user.profile is not None and user.profile.real_name:
    return f"{user.profile.real_name}（{user.email}）"
  return user.email
