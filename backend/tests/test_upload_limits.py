"""Nginx upload-limit consistency and attachment size-boundary tests.

Gateway `client_max_body_size` must stay aligned across the three nginx
configs so a file that passes the backend attachment policy is not rejected
by the reverse proxy with a generic 413. Application-layer limits remain
stricter (text 10MB / binary 25MB / audio 50MB); the gateway ceiling is 64MB.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.core.exceptions import AppValidationError
from app.services.attachment_service import (
  AUDIO_MAX_BYTES,
  OTHER_BINARY_MAX_BYTES,
  TEXT_CLASS_MAX_BYTES,
  AttachmentService,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
NGINX_DIR = REPO_ROOT / "infra" / "nginx"
NGINX_CONFIGS = (
  NGINX_DIR / "default.conf",
  NGINX_DIR / "nginx.compose.prod.conf",
  NGINX_DIR / "nginx.prod.conf",
)
BODY_SIZE_PATTERN = re.compile(r"client_max_body_size\s+64m\s*;")


def test_nginx_configs_declare_64m_upload_limit() -> None:
  missing: list[str] = []
  for path in NGINX_CONFIGS:
    assert path.is_file(), f"missing nginx config: {path}"
    text = path.read_text(encoding="utf-8")
    if BODY_SIZE_PATTERN.search(text) is None:
      missing.append(path.name)
  assert missing == [], (
    "nginx configs must declare `client_max_body_size 64m;` to keep "
    f"dev/prod upload behaviour aligned; missing in: {missing}"
  )


def test_dev_nginx_sets_body_size_at_server_scope() -> None:
  """Dev gateway should set the limit on the server block, not only /api/.

  Uploads currently go through `/api/`, but a server-level directive also
  covers any future upload path and matches the production intent.
  """
  text = (NGINX_DIR / "default.conf").read_text(encoding="utf-8")
  # The first directive occurrence should appear before any location block.
  body_pos = text.find("client_max_body_size 64m;")
  location_pos = text.find("location ")
  assert body_pos != -1
  assert location_pos != -1
  assert body_pos < location_pos


@pytest.mark.parametrize(
  ("mime", "filename", "size", "should_pass"),
  [
    ("text/plain", "note.txt", 1024 * 1024, True),  # 1 MB under 10 MB
    ("text/plain", "note.txt", TEXT_CLASS_MAX_BYTES, True),
    ("text/plain", "note.txt", TEXT_CLASS_MAX_BYTES + 1, False),
    ("audio/mpeg", "clip.mp3", AUDIO_MAX_BYTES, True),
    ("audio/mpeg", "clip.mp3", AUDIO_MAX_BYTES + 1, False),
    ("image/png", "shot.png", OTHER_BINARY_MAX_BYTES + 1, False),
  ],
)
def test_attachment_size_boundaries(
  mime: str,
  filename: str,
  size: int,
  should_pass: bool,
) -> None:
  if mime == "text/plain":
    content = b"a" * size
  elif mime == "image/png":
    # Size is checked before magic bytes; oversized payloads never reach
    # filetype validation, so a truncated signature is enough here.
    content = b"\x89PNG\r\n\x1a\n" + b"\x00" * max(0, size - 8)
  else:
    # ID3-framed MP3 signature so mime validation accepts the payload.
    content = b"ID3" + b"\x00" * max(0, size - 3)

  if should_pass:
    validated = AttachmentService._validate_attachment_content(
      filename=filename,
      content_type=mime,
      content=content,
    )
    assert validated == mime
  else:
    with pytest.raises(AppValidationError, match="附件超过允许大小"):
      AttachmentService._validate_attachment_content(
        filename=filename,
        content_type=mime,
        content=content,
      )


def test_attachment_accepts_small_valid_png() -> None:
  # 1x1 transparent PNG
  content = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
  )
  validated = AttachmentService._validate_attachment_content(
    filename="pixel.png",
    content_type="image/png",
    content=content,
  )
  assert validated == "image/png"


def test_gateway_ceiling_exceeds_application_limits() -> None:
  """64 MB gateway limit must remain above the strictest app-layer ceiling."""
  gateway_bytes = 64 * 1024 * 1024
  assert gateway_bytes > AUDIO_MAX_BYTES
  assert gateway_bytes > OTHER_BINARY_MAX_BYTES
  assert gateway_bytes > TEXT_CLASS_MAX_BYTES
