#!/bin/bash
set -e

echo "Running database migrations..."
alembic upgrade head

echo "Starting CatSyphon API server..."
exec uvicorn catsyphon.api.app:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers "${API_WORKERS:-4}"
