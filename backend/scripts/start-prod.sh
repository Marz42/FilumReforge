#!/bin/sh
# Production backend startup.
# Runs Alembic migrations then starts uvicorn WITHOUT --reload.
#
# Environment variables (with defaults):
#   BIND_HOST  – listen address (default: 127.0.0.1 for systemd/host path)
#                Set BIND_HOST=0.0.0.0 when running inside a Docker container
#                where Nginx reaches the backend over the Docker network.
#   BIND_PORT  – listen port   (default: 8000)
#   WORKERS    – uvicorn worker count (default: 1; increase for multi-core)

set -eu

BIND_HOST="${BIND_HOST:-127.0.0.1}"
BIND_PORT="${BIND_PORT:-8000}"
WORKERS="${WORKERS:-1}"

alembic upgrade head

exec uvicorn app.main:app \
  --host "$BIND_HOST" \
  --port "$BIND_PORT" \
  --workers "$WORKERS" \
  --proxy-headers \
  --forwarded-allow-ips "*"
