#!/bin/bash
set -e

echo "==> Running Alembic migrations..."
cd /app/packages/common
alembic upgrade head

echo "==> Seeding database from CSV files..."
cd /app
python -m common.seed

echo "==> Starting API server..."
exec uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
