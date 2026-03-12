from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://case:case@db:5432/case"
    base_url: str = "http://localhost:8000"

    model_config = {"env_prefix": ""}


settings = Settings()
