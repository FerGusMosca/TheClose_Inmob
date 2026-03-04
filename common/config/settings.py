# common/config/settings.py
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, AliasChoices


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # ── Server ────────────────────────────────────────────────────────────────
    port: str | None = Field(
        default="9005",
        validation_alias=AliasChoices("PORT", "PORT"))

    session_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SESSION_KEY", "SESSION_KEY"))

    # ── PostgreSQL + pgvector ─────────────────────────────────────────────────
    database_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("DATABASE_URL", "DATABASE_URL"))

    # ── OpenAI (embeddings + chatbot) ─────────────────────────────────────────
    openai_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("OPENAI_API_KEY", "OPENAI_API_KEY"))


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()