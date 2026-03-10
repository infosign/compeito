import os

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://case:case@db:5432/case"
    base_url: str = "http://localhost:8000"
    is_lambda: bool = bool(os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))
    admin_key: str = ""

    model_config = {"env_prefix": ""}


settings = Settings()
