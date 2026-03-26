from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "local"
    log_level: str = "INFO"
    database_url: str = "postgresql://paleo:change-me@postgres:5432/paleo"
    jwt_secret: str = "replace-with-very-long-random-secret"
    jwt_refresh_secret: str = "replace-with-another-very-long-random-secret"
    jwt_access_minutes: int = 30
    jwt_refresh_days: int = 30
    bootstrap_admin_username: str = "admin"
    bootstrap_admin_password: str = "replace-with-bootstrap-admin-password"
    bootstrap_admin_display_name: str = "Local Admin"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
