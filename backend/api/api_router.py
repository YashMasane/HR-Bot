from fastapi import APIRouter
from backend.api.routes import auth, department, organization, user

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(organization.router, prefix="/organizations", tags=["organization"])
api_router.include_router(user.router, prefix="/users", tags=["users"])
api_router.include_router(department.router, prefix="/departments", tags=["departments"])
