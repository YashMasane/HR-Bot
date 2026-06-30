from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.core.config import settings
from backend.core.rate_limiter import setup_rate_limiting
from backend.api.api_router import api_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Update for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Set up Rate Limiting
setup_rate_limiting(app)

@app.get("/")
def root():
    return {"message": "Welcome to HR Bot API"}

# Include Routers
app.include_router(api_router, prefix=settings.API_V1_STR)
