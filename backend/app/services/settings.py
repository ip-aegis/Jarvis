"""Settings service for user preferences."""
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.logging import get_logger
from app.models import UserSetting

logger = get_logger(__name__)
settings = get_settings()

# Chat contexts that can have default models
CHAT_CONTEXTS = [
    "general",
    "monitoring",
    "projects",
    "network",
    "actions",
    "home",
    "journal",
    "work",
]


class SettingsService:
    """Service for managing user settings."""

    def __init__(self, db: Session):
        self.db = db

    def get_setting(self, key: str) -> Optional[str]:
        """Get a single setting value."""
        setting = self.db.query(UserSetting).filter(UserSetting.key == key).first()
        return setting.value if setting else None

    def set_setting(self, key: str, value: str) -> UserSetting:
        """Set a single setting value (upsert)."""
        setting = self.db.query(UserSetting).filter(UserSetting.key == key).first()
        if setting:
            setting.value = value
            setting.updated_at = datetime.utcnow()
        else:
            setting = UserSetting(key=key, value=value)
            self.db.add(setting)
        self.db.commit()
        self.db.refresh(setting)
        return setting

    def get_all_settings(self) -> dict[str, str]:
        """Get all settings as key-value dict."""
        settings_list = self.db.query(UserSetting).all()
        return {s.key: s.value for s in settings_list}

    def set_multiple_settings(self, settings_dict: dict[str, str]) -> None:
        """Set multiple settings at once."""
        for key, value in settings_dict.items():
            setting = self.db.query(UserSetting).filter(UserSetting.key == key).first()
            if setting:
                setting.value = value
                setting.updated_at = datetime.utcnow()
            else:
                setting = UserSetting(key=key, value=value)
                self.db.add(setting)
        self.db.commit()

    def get_default_model_for_context(self, context: str) -> str:
        """Get the default model for a chat context."""
        key = f"default_model_{context}"
        value = self.get_setting(key)
        # Fall back to global default if not set
        return value if value else settings.openai_model

    def get_all_model_defaults(self) -> dict[str, str]:
        """Get default models for all chat contexts."""
        result = {}
        for context in CHAT_CONTEXTS:
            result[context] = self.get_default_model_for_context(context)
        return result

    def set_model_default(self, context: str, model: str) -> None:
        """Set the default model for a chat context."""
        if context not in CHAT_CONTEXTS:
            raise ValueError(f"Invalid context: {context}")
        key = f"default_model_{context}"
        self.set_setting(key, model)
