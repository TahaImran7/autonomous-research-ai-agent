#!/bin/bash
set -e

# 1. Background mein Celery Worker start karein
celery -A agent_service.app.worker.celery_app worker --loglevel=info --concurrency=2 &

# 2. Foreground mein FastAPI Gateway start karein
exec uvicorn agent_service.app.main:app --host 0.0.0.0 --port ${PORT:-7860}