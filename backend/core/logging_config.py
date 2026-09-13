"""Application-wide logging setup: console + rotating file, shared by both
the FastAPI process (wired in main.py) and the Celery worker process (wired
in celery_app.py) - they're separate Python processes, so each needs its own
call, but the config is defined once here.
"""

import logging
import logging.handlers
import os

from backend.core.config import settings

LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "app.log")


def setup_logging() -> None:
    root_logger = logging.getLogger()
    if root_logger.handlers:
        # Already configured - e.g. uvicorn --reload re-imports this module,
        # or main.py and celery_app.py both ran in the same process. Adding
        # handlers again would duplicate every log line.
        return

    os.makedirs(LOG_DIR, exist_ok=True)
    root_logger.setLevel(settings.LOG_LEVEL)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # SQLAlchemy's own logger is chatty at INFO (echoes every SQL statement) -
    # keep it at WARNING so it doesn't drown out application logs.
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
