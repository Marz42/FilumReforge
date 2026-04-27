from __future__ import annotations


def validate_password_strength(value: str) -> str:
  categories = [
    any(character.islower() for character in value),
    any(character.isupper() for character in value),
    any(character.isdigit() for character in value),
    any(not character.isalnum() for character in value),
  ]
  if sum(categories) < 3:
    raise ValueError("密码至少需要包含大写字母、小写字母、数字、符号中的三类。")
  return value