"""
Settings configuration module for the application.
Loads environment variables and provides configuration settings.
"""
import os
from typing import Literal, Optional
from pydantic import BaseSettings, Field

class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # LLM API Keys
    GROQ_API_KEY: str = Field(..., env="GROQ_API_KEY")
    COHERE_API_KEY: str = Field(..., env="COHERE_API_KEY")
    
    # Telegram Bot Configuration
    TELEGRAM_BOT_TOKEN: str = Field(..., env="TELEGRAM_BOT_TOKEN")
    
    # LLM Configuration
    LLM_PROVIDER: Literal["GROQ", "COHERE"] = Field("GROQ", env="LLM_PROVIDER")
    GROQ_MODEL: str = Field("llama3-70b-8192", env="GROQ_MODEL")
    COHERE_MODEL: str = Field("command-light", env="COHERE_MODEL")
    
    # App Configuration
    DEBUG: bool = Field(False, env="DEBUG")
    LOG_LEVEL: str = Field("INFO", env="LOG_LEVEL")
    APP_PORT: int = Field(8000, env="APP_PORT")
    APP_HOST: str = Field("0.0.0.0", env="APP_HOST")
    
    # Upload directory
    UPLOAD_DIR: str = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")

    class Config:
        """Pydantic config class."""
        env_file = ".env"
        case_sensitive = True


# Create settings instance
settings = Settings()
