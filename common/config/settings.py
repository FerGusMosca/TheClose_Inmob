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

    # ── OpenAI ────────────────────────────────────────────────────────────────
    openai_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("OPENAI_API_KEY", "OPENAI_API_KEY"))

    # ── LLM — dotted class path, same convention as INTENT_DETECTION_LOGIC ───
    # Examples:
    #   LLM_CLASS=common.llm_client.openai_llm.OpenAILLM   (full path)
    #   LLM_CLASS=openai                                     (alias)
    llm_class: str = Field(
        default="common.llm_client.openai_llm.OpenAILLM",
        validation_alias=AliasChoices("LLM_CLASS", "LLM_CLASS"))

    llm_model: str = Field(
        default="gpt-4o-mini",
        validation_alias=AliasChoices("LLM_MODEL", "LLM_MODEL"))

    llm_temperature: float = Field(
        default=0.0,
        validation_alias=AliasChoices("LLM_TEMPERATURE", "LLM_TEMPERATURE"))

    # ── Prompts ───────────────────────────────────────────────────────────────
    prompt_query_properties: str = Field(
        default="prompts/query_properties.txt",
        validation_alias=AliasChoices("PROMPT_QUERY_PROPERTIES", "PROMPT_QUERY_PROPERTIES"))


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()