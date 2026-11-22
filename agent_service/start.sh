#!/bin/bash
set -e

# 1. Single-process lightweight Celery worker (512MB RAM safe)
celery -A agent_service.app.worker.celery_app worker --loglevel=info --pool=solo &

# 2. Single-worker FastAPI server
exec uvicorn agent_service.app.main:app --host 0.0.0.0 --port ${PORT:-7860} --workers 1