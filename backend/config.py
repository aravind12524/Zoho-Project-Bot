import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """Load configuration from .env and environment variables.

    All required secrets must be present in the .env file. Optional fields are marked as Optional.
    The Config allows extra environment variables so legacy variables (e.g., ollama) do not raise validation errors.
    """

    # Zoho OAuth
    zoho_client_id: str
    zoho_client_secret: str
    zoho_redirect_uri: str = "http://localhost:8000/auth/callback"
    zoho_api_base_url: str = "https://projectsapi.zoho.com/api/v3"

    # URLs
    backend_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:3000"

    # Database
    database_url: str = "sqlite:///./zoho_chatbot.db"
    session_secret_key: str

    # LLM API keys
    grok_api_key: str = ""
    gemini_api_key: Optional[str] = None

    # Legacy fields (unused)
    ollama_model: Optional[str] = None
    ollama_base_url: Optional[str] = None

    # Logging
    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="allow")

settings = Settings()
