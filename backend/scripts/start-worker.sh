#!/bin/sh

set -eu

alembic upgrade head
exec arq app.workers.arq_worker.WorkerSettings
