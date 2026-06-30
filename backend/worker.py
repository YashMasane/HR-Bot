from backend.core.celery_app import celery_app

# This file serves as the entry point for starting the celery worker.
# Run it using: celery -A backend.worker.celery_app worker --loglevel=info
