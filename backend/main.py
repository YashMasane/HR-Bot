import logging
import time

from fastapi import FastAPI, Request

from backend.core.config import settings
from backend.core.logging_config import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)


@app.on_event("startup")
def on_startup():
    logger.info("HR Bot API starting up (log level=%s)", settings.LOG_LEVEL)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "%s %s -> %s (%.1fms)",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


@app.get("/")
def root():
    return {"message": "Welcome to HR Bot API"}

from backend.api.api_router import api_router
app.include_router(api_router, prefix=settings.API_V1_STR)
