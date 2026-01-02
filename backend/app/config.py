from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import List


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql://jarvis:jarvis_dev_password@localhost:5432/jarvis"

    # Ollama LLM
    ollama_url: str = "http://10.10.20.62:11434"
    ollama_model: str = "llama3.1:8b"

    # SearXNG
    searxng_url: str = "http://localhost:8888"

    # SSH Keys storage
    ssh_keys_path: str = "/app/ssh_keys"

    # App settings
    app_name: str = "Jarvis"
    debug: bool = True

    # CORS settings - restrict to known origins
    cors_origins: List[str] = [
        "https://10.10.20.235",
        "http://10.10.20.235",
        "http://localhost:3000",
        "http://localhost:5173",
    ]

    # Authentication settings
    jwt_secret_key: str = "change-me-in-production-use-a-strong-random-key"
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 24
    admin_username: str = "admin"
    # Default password hash for "admin" - CHANGE IN PRODUCTION
    # Generate with: python -c "from passlib.hash import bcrypt; print(bcrypt.hash('your-password'))"
    admin_password_hash: str = "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.qVQzFm1gH1sYmG"

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
