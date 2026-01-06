from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Environment
    environment: Literal["development", "staging", "production"] = "development"

    # Database
    database_url: str = "postgresql://jarvis:jarvis_dev_password@localhost:5432/jarvis"

    # Ollama LLM (legacy - keeping for reference)
    ollama_url: str = "http://10.10.20.62:11434"
    ollama_model: str = "llama3.1:8b"

    # OpenAI LLM (primary)
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"

    # SearXNG
    searxng_url: str = "http://localhost:8888"

    # SSH Keys storage
    ssh_keys_path: str = "/app/ssh_keys"

    # App settings
    app_name: str = "Jarvis"

    @property
    def debug(self) -> bool:
        """Debug mode is only enabled in development."""
        return self.environment == "development"

    # CORS settings - separate for dev and prod
    cors_origins_dev: list[str] = [
        "https://10.10.20.235",
        "http://10.10.20.235",
        "http://localhost:3000",
        "http://localhost:5173",
    ]
    cors_origins_prod: list[str] = [
        "https://10.10.20.235",
    ]

    @property
    def cors_origins(self) -> list[str]:
        """Return appropriate CORS origins based on environment."""
        if self.environment == "production":
            return self.cors_origins_prod
        return self.cors_origins_dev

    # Authentication settings
    jwt_secret_key: str = "change-me-in-production-use-a-strong-random-key"
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 24
    admin_username: str = "admin"
    # Default password hash for "admin" - CHANGE IN PRODUCTION
    # Generate with: python -c "import bcrypt; print(bcrypt.hashpw(b'your-password', bcrypt.gensalt()).decode())"
    admin_password_hash: str = "$2b$12$d8TIuKkqtAHu7xvg1bhxP.Ry7vZU7bLZOb9NiYZ7IW8iznHajHZGm"

    # Logging
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        extra = "ignore"

    def validate_production_secrets(self) -> None:
        """Validate that production secrets are properly configured."""
        if self.environment == "production":
            if self.jwt_secret_key == "change-me-in-production-use-a-strong-random-key":
                raise ValueError("JWT_SECRET_KEY must be changed in production")
            if len(self.jwt_secret_key) < 32:
                raise ValueError("JWT_SECRET_KEY must be at least 32 characters in production")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.validate_production_secrets()
    return settings
