from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://case:case@db:5432/case"
    base_url: str = "http://localhost:8000"

    # `.env` is read for local native development (e.g., DATABASE_URL pointing to localhost).
    # Real environment variables (set by docker compose etc.) take precedence over `.env`.
    model_config = SettingsConfigDict(env_file=".env", env_prefix="", extra="ignore")


settings = Settings()
