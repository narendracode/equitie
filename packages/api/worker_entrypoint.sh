#!/bin/bash
set -e

echo "==> Starting Celery worker..."
exec celery -A api.celery_app worker --loglevel=info
