from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal

class Settings(BaseSettings):
    API_KEY : SecretStr
    MODEL : str
    FRONTEND_DIR : str
    DATABASE_PATH : str
    SYSTEM_PROMPT_PATH : str
    OUTPUT_MODALITIES: list[Literal["text", "image"]] | None = None
    OPENROUTER_API_MODE: Literal["auto", "chat", "images"] = "auto"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

@lru_cache
def get_settings() -> Settings:
    return Settings() # type: ignore
