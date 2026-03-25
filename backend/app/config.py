from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "local"
    log_level: str = "INFO"
    database_url: str = "postgresql://paleo:change-me@postgres:5432/paleo"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
