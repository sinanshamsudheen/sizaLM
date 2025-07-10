"""
Logging utility module for the application.
Provides asynchronous logging capabilities using loguru.
"""

import sys
import os
from loguru import logger
from config.settings import settings


# Configure logger
def configure_logger():
    """Configure the logger with appropriate settings."""
    log_level = settings.LOG_LEVEL

    # Remove default handlers
    logger.remove()
    
    # Add stdout handler
    logger.add(
        sys.stdout,
        level=log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        backtrace=True,
        diagnose=settings.DEBUG,
    )
    
    # Add file handler
    os.makedirs("logs", exist_ok=True)
    logger.add(
        "logs/app.log",
        rotation="10 MB",
        retention="1 week",
        level=log_level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        backtrace=True,
        diagnose=settings.DEBUG,
    )
    
    return logger


# Create and configure logger instance
app_logger = configure_logger()


class AsyncLoggerAdapter:
    """Adapter to provide async logging methods."""
    
    @staticmethod
    async def info(message: str):
        """Log info message asynchronously."""
        logger.info(message)
    
    @staticmethod
    async def error(message: str, exc_info=None):
        """Log error message asynchronously."""
        logger.error(message, exc_info=exc_info)
    
    @staticmethod
    async def debug(message: str):
        """Log debug message asynchronously."""
        logger.debug(message)
    
    @staticmethod
    async def warning(message: str):
        """Log warning message asynchronously."""
        logger.warning(message)


# Create async logger instance
async_logger = AsyncLoggerAdapter()
