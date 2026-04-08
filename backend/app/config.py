"""Application configuration using Pydantic Settings."""

from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    app_name: str = "Verida Compliance API"
    app_version: str = "2.0.0"
    debug: bool = False

    # Supabase
    supabase_url: str
    supabase_key: str          # anon key — used for client-facing auth operations
    supabase_service_key: str  # service role key — used for admin/backend operations

    # Anthropic
    anthropic_api_key: str
    claude_model: str = "claude-opus-4-6"

    # Storage
    storage_bucket: str = "documents"
    max_file_size_mb: int = 50
    allowed_extensions: List[str] = [".pdf", ".docx", ".txt"]

    # CORS — comma-separated in env, parsed as a list by Pydantic
    cors_origins: List[str] = [
        "https://veridahq.com",
        "https://www.veridahq.com",
        "https://api.veridahq.com",
        "https://project-wbinr.vercel.app",
        "https://api.veridahq.com",
        "https://project-wbinr.vercel.app",
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:8080",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8080",
    ]

    # Email (Resend)
    resend_api_key: str = ""
    from_email: str = "Verida <noreply@veridahq.com>"

    # API
    api_prefix: str = "/api"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


settings = Settings()
