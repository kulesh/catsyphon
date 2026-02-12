#!/bin/bash
set -e

echo "Running database migrations..."
alembic upgrade head

echo "Starting CatSyphon API server..."
API_WORKERS="${API_WORKERS:-1}"

# DaemonManager is process-local and watch daemons are managed in-memory.
# Multiple API workers can race and start duplicate watch daemons.
if [ "${API_WORKERS}" -gt 1 ]; then
    echo "WARNING: API_WORKERS=${API_WORKERS} is not supported with watch daemons; forcing API_WORKERS=1"
    API_WORKERS=1
fi

exec uvicorn catsyphon.api.app:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers "${API_WORKERS}"
