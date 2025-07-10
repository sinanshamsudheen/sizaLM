"""
API package initialization module that sets up FastAPI routers.
"""

from fastapi import APIRouter
from app.api.routes.telegram import router as telegram_router

# Create main API router
api_router = APIRouter()

# Include all route modules
api_router.include_router(telegram_router, prefix="/telegram", tags=["telegram"])
