#!/bin/sh
set -eu

lock_hash="$(sha256sum package-lock.json | cut -d ' ' -f 1)"
lock_marker="node_modules/.filum-package-lock.sha256"

if [ ! -f "$lock_marker" ] || [ "$(cat "$lock_marker")" != "$lock_hash" ]; then
  echo "package-lock.json changed; synchronizing frontend dependencies..."
  npm ci --no-audit --no-fund
  printf '%s\n' "$lock_hash" > "$lock_marker"
fi

exec "$@"
