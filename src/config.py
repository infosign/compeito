from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://case:case@db:5432/case"
    base_url: str = "http://localhost:8000"

    # CASE API output shape when the request asks for neither ?strict=1 nor
    # ?compat=1. "compat" is today's default (OpenSALT-style wrappers, null
    # echo); flipping this to "strict" is the planned major-version change that
    # makes official-schema output the default. See
    # docs/dev/designs/strict-output.md.
    case_output_default: Literal["compat", "strict"] = "compat"

    # `.env` is read for local native development (e.g., DATABASE_URL pointing to localhost).
    # Real environment variables (set by docker compose etc.) take precedence over `.env`.
    model_config = SettingsConfigDict(env_file=".env", env_prefix="", extra="ignore")


settings = Settings()
