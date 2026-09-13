from fastapi import FastAPI
from backend.core.config import settings

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

@app.get("/")
def root():
    return {"message": "Welcome to HR Bot API"}

from backend.api.api_router import api_router
app.include_router(api_router, prefix=settings.API_V1_STR)
