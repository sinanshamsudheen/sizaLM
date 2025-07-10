"""
Main entry point for the application.
"""

import asyncio
import uvicorn
from dotenv import load_dotenv
import threading
import os
import time

from app.app import create_app
from config.settings import settings
from services.telegram_handler import TelegramHandler
from utils.logging import app_logger


# Load environment variables
load_dotenv()

# Ensure upload directory exists
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
app_logger.info(f"Upload directory ensured at: {settings.UPLOAD_DIR}")

# Create FastAPI app
app = create_app()

# Create a TelegramHandler instance
telegram_handler = TelegramHandler()


async def start_telegram_bot():
    """Start the Telegram bot polling in a separate task."""
    try:
        app_logger.info(f"Starting Telegram bot polling with token: {settings.TELEGRAM_BOT_TOKEN[:5]}...{settings.TELEGRAM_BOT_TOKEN[-5:]}")
        await telegram_handler.start_polling()
    except Exception as e:
        app_logger.error(f"Error in Telegram bot polling: {str(e)}")
        # Retry after a short delay
        await asyncio.sleep(5)
        app_logger.info("Retrying Telegram bot polling...")
        await start_telegram_bot()


def run_telegram_bot():
    """Run the Telegram bot polling in a separate thread."""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(start_telegram_bot())
    except Exception as e:
        app_logger.error(f"Fatal error in Telegram bot thread: {str(e)}")


if __name__ == "__main__":
    """Run the application with uvicorn server and start the Telegram bot."""
    # Ensure we have a valid Telegram token
    if not settings.TELEGRAM_BOT_TOKEN or len(settings.TELEGRAM_BOT_TOKEN) < 20:
        app_logger.error("Invalid or missing Telegram bot token. Please check your .env file")
        exit(1)
        
    # Start the Telegram bot in a separate thread
    telegram_thread = threading.Thread(target=run_telegram_bot, daemon=True)
    telegram_thread.start()
    app_logger.info("Telegram bot thread started")
    
    # Give the bot a moment to initialize
    time.sleep(2)
    
    # Start the FastAPI server
    uvicorn.run(
        "main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.DEBUG
    )
