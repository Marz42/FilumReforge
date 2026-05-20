from __future__ import annotations

from urllib.parse import quote
from uuid import UUID


def build_attachment_content_path(attachment_id: UUID) -> str:
  return f"/api/v1/attachments/{attachment_id}/content"


def build_content_disposition(*, disposition: str, filename: str) -> str:
  safe_ascii = "".join(char if ord(char) < 128 and char not in {'"', "\\"} else "_" for char in filename)
  if not safe_ascii.strip("._"):
    safe_ascii = "download"
  encoded = quote(filename)
  return f'{disposition}; filename="{safe_ascii}"; filename*=UTF-8\'\'{encoded}'
