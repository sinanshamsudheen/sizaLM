"""
Application factory module that creates and configures the FastAPI app.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

from app.api.api import api_router
from config.settings import settings
from utils.logging import app_logger


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.
    
    Returns:
        Configured FastAPI application
    """
    # Create FastAPI app with metadata
    app = FastAPI(
        title="Telegram PDF Bot",
        description="A FastAPI service for processing PDFs and questions via Telegram",
        version="1.0.0",
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
    )
    
    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.DEBUG else ["https://yourfrontenddomain.com"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include API router
    app.include_router(api_router, prefix="/api")
    
    # Create uploads directory if it doesn't exist
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    
    # Startup and shutdown events
    @app.on_event("startup")
    async def startup_event():
        """Run startup tasks."""
        app_logger.info("Starting Telegram PDF Bot service")
    
    @app.on_event("shutdown")
    async def shutdown_event():
        """Run shutdown tasks."""
        app_logger.info("Shutting down WhatsApp PDF Bot service")
        
        # Clean up any temporary files in the uploads directory
        try:
            for file in os.listdir(settings.UPLOAD_DIR):
                file_path = os.path.join(settings.UPLOAD_DIR, file)
                if os.path.isfile(file_path):
                    os.unlink(file_path)
        except Exception as e:
            app_logger.error(f"Error cleaning up uploads directory: {str(e)}")
    
    return app
