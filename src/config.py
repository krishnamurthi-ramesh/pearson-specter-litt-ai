"""
config.py
=========
Centralised configuration management using Pydantic BaseSettings.
Provides strict environment variable validation and defaults for
all subsystems in the platform.
"""

import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """
    Enterprise configuration parameters.
    Values can be overridden via environment variables or .env file.
    """
    # App details
    APP_NAME: str = "Pearson Specter Litt Document Intelligence"
    DEBUG: bool = False
    PORT: int = 8000
    HOST: str = "0.0.0.0"

    # Ingestion
    TESSERACT_CMD: Optional[str] = None
    UPLOAD_DIR: str = "./data/uploads"

    # Vector DB (ChromaDB)
    CHROMA_DB_PATH: str = "./data/chroma_db"
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"

    # Local Ollama LLM
    OLLAMA_HOST: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "mistral:7b"

    # Feedback Database
    FEEDBACK_DB_PATH: str = "./data/feedback.db"

    # Ensure we load from .env file automatically
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


# Instantiate a global singleton configuration object
settings = AppSettings()
